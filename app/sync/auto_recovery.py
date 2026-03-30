"""Autonomous historical data recovery for all configured stations.

Runs once a day (configurable), checks for new stations, detects their
data start date, and recovers historical data day-by-day within a daily
API call budget.  All state is persisted in the DB so the process survives
app restarts without repeating work.

IMPORTANT: This module is designed to never interfere with the rapid/hourly
sync jobs.  It uses short-lived DB connections (open-query-close) and sleeps
between API calls to stay well within rate limits.
"""

import logging
import time
from datetime import date, datetime, timedelta, timezone

from ..api_client import WUClient
from ..config import get_all_stations
from ..database import get_connection
from ..models import map_daily_observation

logger = logging.getLogger(__name__)

API_CALL_DELAY = 5  # seconds between API calls


# ---------------------------------------------------------------------------
#  DB helpers — each opens and closes its own connection
# ---------------------------------------------------------------------------

def _get_queue_entry(station_id: str) -> dict | None:
    con = get_connection()
    try:
        row = con.execute(
            "SELECT * FROM recovery_queue WHERE station_id = ?", [station_id]
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in con.description]
        return dict(zip(cols, row))
    finally:
        con.close()


def _upsert_queue(station_id: str, **fields):
    con = get_connection()
    try:
        existing = con.execute(
            "SELECT 1 FROM recovery_queue WHERE station_id = ?", [station_id]
        ).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [station_id]
            con.execute(f"UPDATE recovery_queue SET {sets} WHERE station_id = ?", vals)
        else:
            fields["station_id"] = station_id
            cols = ", ".join(fields.keys())
            placeholders = ", ".join(["?"] * len(fields))
            con.execute(
                f"INSERT INTO recovery_queue ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
    finally:
        con.close()


def _get_all_queue_entries() -> list[dict]:
    con = get_connection()
    try:
        rows = con.execute("SELECT * FROM recovery_queue ORDER BY created_at").fetchall()
        cols = [d[0] for d in con.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


def _insert_recovery_log(run_date: date) -> int:
    con = get_connection()
    try:
        con.execute(
            "INSERT INTO recovery_log (run_date, started_at, status) VALUES (?, ?, 'running')",
            [run_date, datetime.now(timezone.utc)],
        )
        log_id = con.execute("SELECT max(id) FROM recovery_log").fetchone()[0]
        return log_id
    finally:
        con.close()


def _update_recovery_log(log_id: int, **fields):
    con = get_connection()
    try:
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [log_id]
        con.execute(f"UPDATE recovery_log SET {sets} WHERE id = ?", vals)
    finally:
        con.close()


def _upsert_daily_record(record: dict):
    """Insert or replace a single daily observation — short-lived connection."""
    con = get_connection()
    try:
        cols = [
            "station_id", "obs_date",
            "temp_avg_c", "temp_high_c", "temp_low_c",
            "humidity_avg_pct", "humidity_high_pct", "humidity_low_pct",
            "dew_point_avg_c", "dew_point_high_c", "dew_point_low_c",
            "pressure_avg_hpa", "pressure_max_hpa", "pressure_min_hpa",
            "wind_speed_avg_kmh", "wind_speed_high_kmh", "wind_gust_high_kmh",
            "precip_total_mm",
        ]
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        values = [record.get(c) for c in cols]
        con.execute(
            f"INSERT OR REPLACE INTO daily_observations ({col_names}) VALUES ({placeholders})",
            values,
        )
    finally:
        con.close()


def _get_existing_data_dates(station_id: str, start: date, end: date) -> set[str]:
    """Return set of ISO date strings with real (non-null) data."""
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT obs_date FROM daily_observations
               WHERE station_id = ? AND obs_date >= ? AND obs_date <= ?
               AND temp_avg_c IS NOT NULL""",
            [station_id, start.isoformat(), end.isoformat()],
        ).fetchall()
        return {str(r[0])[:10] for r in rows}
    finally:
        con.close()


# ---------------------------------------------------------------------------
#  Auto-detect start date (cached in recovery_queue.detected_start)
# ---------------------------------------------------------------------------

def _detect_start_date(client: WUClient, station_id: str) -> tuple[date | None, int]:
    """Binary search for earliest date with data. Returns (date, api_calls_used)."""
    today = date.today()
    api_calls = 0

    # Phase 1: find a year with data
    has_any = False
    hi_years = 10
    for years_back in range(10, -1, -1):
        probe = today - timedelta(days=years_back * 365)
        api_calls += 1
        if client.has_data_on_date(station_id, probe):
            hi_years = years_back
            has_any = True
            break
        time.sleep(API_CALL_DELAY)

    if not has_any:
        return None, api_calls

    # Phase 2: expand back from known date
    search_start = today - timedelta(days=hi_years * 365)
    step = 30
    while step >= 1:
        probe = search_start - timedelta(days=step)
        if probe < today - timedelta(days=3660):
            break
        api_calls += 1
        if client.has_data_on_date(station_id, probe):
            search_start = probe
            step = step * 2
        else:
            break
        time.sleep(API_CALL_DELAY)

    # Phase 3: binary search
    no_data_date = search_start - timedelta(days=max(step, 1))
    has_data_date = search_start

    while (has_data_date - no_data_date).days > 1:
        mid = no_data_date + timedelta(days=(has_data_date - no_data_date).days // 2)
        api_calls += 1
        if client.has_data_on_date(station_id, mid):
            has_data_date = mid
        else:
            no_data_date = mid
        time.sleep(API_CALL_DELAY)

    return has_data_date, api_calls


# ---------------------------------------------------------------------------
#  Main recovery orchestrator
# ---------------------------------------------------------------------------

def run_auto_recovery(cfg: dict):
    """Main entry point — called by the scheduler once a day.

    1. Re-reads stations from config, enqueues new ones.
    2. Processes queue (primary first) within daily API budget.
    3. Logs everything.
    """
    sched_cfg = cfg.get("scheduler", {}).get("auto_recovery", {})
    daily_budget = sched_cfg.get("daily_api_budget", 1000)

    logger.info("Auto-recovery started (budget: %d calls)", daily_budget)

    today = date.today()
    log_id = _insert_recovery_log(today)

    total_api_calls = 0
    total_days_recovered = 0
    total_days_skipped = 0
    new_stations = 0
    stations_processed = 0

    try:
        # --- Step 1: fix any stale in_progress from crashed runs ---
        _fix_stale_entries()

        # --- Step 2: enqueue new stations ---
        new_stations = _enqueue_new_stations(cfg)

        # --- Step 3: recheck completed stations (extend end_date to today) ---
        _recheck_completed(today)

        # --- Step 4: get ordered queue (primary first) ---
        queue = _build_ordered_queue(cfg)

        if not queue:
            logger.info("Auto-recovery: nothing to process")
            _update_recovery_log(log_id,
                completed_at=datetime.now(timezone.utc),
                status="success", new_stations_found=new_stations)
            return

        # --- Step 5: process queue within budget ---
        client = WUClient(cfg)

        for entry in queue:
            if total_api_calls >= daily_budget:
                logger.info("Auto-recovery: daily budget exhausted (%d calls)", total_api_calls)
                break

            sid = entry["station_id"]
            remaining = daily_budget - total_api_calls

            # Need to detect start date first?
            if entry["detected_start"] is None:
                logger.info("Auto-recovery: detecting start date for %s", sid)
                _upsert_queue(sid, status="detecting")

                detected, detect_calls = _detect_start_date(client, sid)
                total_api_calls += detect_calls

                if detected is None:
                    logger.warning("Auto-recovery: no data found for %s", sid)
                    _upsert_queue(sid,
                        status="no_data",
                        api_calls_used=(entry.get("api_calls_used") or 0) + detect_calls,
                        last_run_at=datetime.now(timezone.utc))
                    continue

                end = today
                days_total = (end - detected).days + 1
                _upsert_queue(sid,
                    detected_start=detected.isoformat(),
                    current_date=detected.isoformat(),
                    end_date=end.isoformat(),
                    days_total=days_total,
                    status="in_progress",
                    api_calls_used=(entry.get("api_calls_used") or 0) + detect_calls)

                remaining = daily_budget - total_api_calls
                # Re-read entry after update
                entry = _get_queue_entry(sid)

            if remaining <= 0:
                break

            # Process days for this station
            calls, recovered, skipped = _process_station(
                client, cfg, entry, remaining,
            )
            total_api_calls += calls
            total_days_recovered += recovered
            total_days_skipped += skipped
            stations_processed += 1

        status = "success" if total_api_calls < daily_budget else "budget_exhausted"
        _update_recovery_log(log_id,
            completed_at=datetime.now(timezone.utc),
            stations_processed=stations_processed,
            api_calls_used=total_api_calls,
            days_recovered=total_days_recovered,
            days_skipped=total_days_skipped,
            new_stations_found=new_stations,
            status=status)

        logger.info(
            "Auto-recovery finished: %s, %d calls, %d days recovered, %d skipped, %d new stations",
            status, total_api_calls, total_days_recovered, total_days_skipped, new_stations,
        )

    except Exception as e:
        logger.exception("Auto-recovery failed")
        _update_recovery_log(log_id,
            completed_at=datetime.now(timezone.utc),
            stations_processed=stations_processed,
            api_calls_used=total_api_calls,
            days_recovered=total_days_recovered,
            days_skipped=total_days_skipped,
            new_stations_found=new_stations,
            status="error",
            error_message=str(e))


def _fix_stale_entries():
    """Reset entries stuck in 'in_progress' or 'detecting' from a crashed run."""
    con = get_connection()
    try:
        con.execute(
            "UPDATE recovery_queue SET status = 'paused' "
            "WHERE status IN ('in_progress', 'detecting')"
        )
    finally:
        con.close()


def _enqueue_new_stations(cfg: dict) -> int:
    """Add any stations from config that aren't in the queue yet."""
    stations = get_all_stations(cfg)
    count = 0
    for s in stations:
        existing = _get_queue_entry(s["id"])
        if existing is None:
            _upsert_queue(s["id"],
                status="pending",
                created_at=datetime.now(timezone.utc).isoformat())
            count += 1
            logger.info("Auto-recovery: new station enqueued: %s (%s)", s["id"], s["name"])
    return count


def _recheck_completed(today: date):
    """For completed stations, extend end_date to today if there are new days."""
    entries = _get_all_queue_entries()
    for e in entries:
        if e["status"] == "completed" and e["end_date"]:
            end = e["end_date"]
            if isinstance(end, str):
                end = date.fromisoformat(end[:10])
            if end < today:
                new_total = (e.get("days_total") or 0) + (today - end).days
                _upsert_queue(e["station_id"],
                    end_date=today.isoformat(),
                    days_total=new_total,
                    status="in_progress")
                logger.info("Auto-recovery: extended %s to %s (+%d days)",
                    e["station_id"], today.isoformat(), (today - end).days)


def _build_ordered_queue(cfg: dict) -> list[dict]:
    """Return queue entries ordered: primary station first, then by created_at.
    Only entries that need work (pending, in_progress, paused)."""
    stations = get_all_stations(cfg)
    primary_id = stations[0]["id"] if stations else None

    entries = _get_all_queue_entries()
    active = [e for e in entries if e["status"] in ("pending", "in_progress", "paused")]

    # Sort: primary first, then by created_at
    def sort_key(e):
        is_primary = 0 if e["station_id"] == primary_id else 1
        return (is_primary, e.get("created_at") or "")

    active.sort(key=sort_key)
    return active


def _process_station(client: WUClient, cfg: dict, entry: dict, budget: int) -> tuple[int, int, int]:
    """Process days for a single station within the given call budget.

    Returns (api_calls, days_recovered, days_skipped).
    """
    sid = entry["station_id"]
    current = entry["current_date"]
    end = entry["end_date"]

    if isinstance(current, str):
        current = date.fromisoformat(current[:10])
    if isinstance(end, str):
        end = date.fromisoformat(end[:10])

    if current > end:
        _upsert_queue(sid, status="completed", last_run_at=datetime.now(timezone.utc).isoformat())
        return 0, 0, 0

    _upsert_queue(sid, status="in_progress", last_run_at=datetime.now(timezone.utc).isoformat())

    # Pre-load existing data dates to skip
    existing = _get_existing_data_dates(sid, current, end)

    api_calls = 0
    recovered = 0
    skipped = 0
    days_done_delta = 0

    while current <= end and api_calls < budget:
        # Skip days with existing real data
        if current.isoformat() in existing:
            skipped += 1
            days_done_delta += 1
            current += timedelta(days=1)
            continue

        # Fetch from API
        date_str = current.strftime("%Y%m%d")
        obs = client.get_historical_daily(sid, date_str)
        api_calls += 1

        if obs:
            record = map_daily_observation(obs, sid, current.isoformat())
            recovered += 1
        else:
            record = {
                "station_id": sid,
                "obs_date": current.isoformat(),
                "temp_avg_c": None, "temp_high_c": None, "temp_low_c": None,
                "humidity_avg_pct": None, "humidity_high_pct": None, "humidity_low_pct": None,
                "dew_point_avg_c": None, "dew_point_high_c": None, "dew_point_low_c": None,
                "pressure_avg_hpa": None, "pressure_max_hpa": None, "pressure_min_hpa": None,
                "wind_speed_avg_kmh": None, "wind_speed_high_kmh": None,
                "wind_gust_high_kmh": None, "precip_total_mm": None,
            }

        _upsert_daily_record(record)
        days_done_delta += 1
        current += timedelta(days=1)

        time.sleep(API_CALL_DELAY)

    # Update queue state
    new_status = "completed" if current > end else "paused"
    prev_done = entry.get("days_done") or 0
    prev_skipped = entry.get("days_skipped") or 0
    prev_calls = entry.get("api_calls_used") or 0

    _upsert_queue(sid,
        current_date=current.isoformat(),
        days_done=prev_done + days_done_delta,
        days_skipped=prev_skipped + skipped,
        api_calls_used=prev_calls + api_calls,
        status=new_status,
        last_run_at=datetime.now(timezone.utc).isoformat(),
        error_message=None)

    logger.info(
        "Auto-recovery %s: %s — %d calls, %d recovered, %d skipped, status=%s",
        sid, "done" if new_status == "completed" else "paused",
        api_calls, recovered, skipped, new_status,
    )

    return api_calls, recovered, skipped


# ---------------------------------------------------------------------------
#  Public helpers for the web UI
# ---------------------------------------------------------------------------

def get_recovery_status() -> dict:
    """Return current recovery state for the web UI."""
    entries = _get_all_queue_entries()

    con = get_connection()
    try:
        logs = con.execute(
            "SELECT * FROM recovery_log ORDER BY started_at DESC LIMIT 20"
        ).fetchall()
        log_cols = [d[0] for d in con.description]
        log_list = [dict(zip(log_cols, r)) for r in logs]
    finally:
        con.close()

    return {
        "queue": entries,
        "recent_runs": log_list,
    }
