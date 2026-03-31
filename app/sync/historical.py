import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from ..api_client import WUClient
from ..database import get_connection
from ..models import map_daily_observation

logger = logging.getLogger(__name__)

API_CALL_DELAY = 5        # seconds between API calls (WU limit: 30/min)
MAX_DAILY_API_CALLS = 1300  # safety margin on 1500/day WU limit

# Global state for the running backfill job
_backfill_lock = threading.Lock()
_backfill_state = {
    "running": False,
    "stop_requested": False,
    "progress": 0,
    "total": 0,
    "current_date": None,
    "error": None,
}


def get_backfill_state() -> dict:
    with _backfill_lock:
        return dict(_backfill_state)


def request_stop():
    with _backfill_lock:
        _backfill_state["stop_requested"] = True


def get_dates_with_data(station_id: str, start: date, end: date) -> set[str]:
    """Return a set of ISO date strings that already have real (non-null) data."""
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT obs_date FROM daily_observations
               WHERE station_id = %s
                 AND obs_date >= %s AND obs_date <= %s
                 AND temp_avg_c IS NOT NULL""",
            [station_id, start.isoformat(), end.isoformat()],
        )
        rows = cur.fetchall()
        cur.close()
        return {str(r[0])[:10] for r in rows}
    finally:
        con.close()


def get_last_synced_date(station_id: str) -> date | None:
    """Find the most recent obs_date in daily_observations for auto-resume."""
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT MAX(obs_date) FROM daily_observations WHERE station_id = %s",
            [station_id],
        )
        result = cur.fetchone()
        cur.close()
        if result and result[0]:
            val = result[0]
            if isinstance(val, str):
                return date.fromisoformat(val)
            if isinstance(val, datetime):
                return val.date()
            return val
        return None
    finally:
        con.close()


def start_backfill(cfg: dict, station_id: str, start_date: date | None = None, end_date: date | None = None):
    """Start the historical backfill in a background thread.

    If start_date is None, auto-resume from the day after the last synced date.
    If no data exists at all, start_date must be provided by the user.
    If end_date is None, defaults to today.
    """
    with _backfill_lock:
        if _backfill_state["running"]:
            return False
        _backfill_state.update(
            running=True, stop_requested=False, progress=0, total=0,
            current_date=None, error=None, station_id=station_id,
        )

    thread = threading.Thread(target=_run_backfill, args=(cfg, station_id, start_date, end_date), daemon=True)
    thread.start()
    return True


def _run_backfill(cfg: dict, station_id: str, start_date: date | None = None, end_date: date | None = None):
    client = WUClient(cfg)
    con = get_connection()
    cur = con.cursor()
    started_at = datetime.now(timezone.utc)

    # Determine start date: user-provided or auto-resume
    if start_date is None:
        last = get_last_synced_date(station_id)
        if last:
            start_date = last + timedelta(days=1)
        else:
            with _backfill_lock:
                _backfill_state.update(
                    running=False,
                    error="No existing data found. Please provide a start date.",
                )
            cur.close()
            con.close()
            return

    if end_date is None:
        end_date = date.today()

    if start_date > end_date:
        with _backfill_lock:
            _backfill_state.update(running=False, error=None, progress=0, total=0)
        cur.close()
        con.close()
        logger.info("Historical backfill: already up to date")
        return

    total_days = (end_date - start_date).days + 1

    with _backfill_lock:
        _backfill_state["total"] = total_days

    # Sync log entry
    cur.execute(
        "INSERT INTO sync_log (started_at, job_type, status, date_range_start, date_range_end, station_id) "
        "VALUES (%s, 'historical', 'running', %s, %s, %s)",
        [started_at, start_date.isoformat(), end_date.isoformat(), station_id],
    )
    cur.execute("SELECT max(id) FROM sync_log")
    log_id = cur.fetchone()[0]

    # Pre-load dates that already have real data — skip them to save API calls
    existing_dates = get_dates_with_data(station_id, start_date, end_date)
    skipped = 0

    fetched = 0
    inserted = 0
    api_calls = 0
    current = start_date

    try:
        while current <= end_date:
            with _backfill_lock:
                if _backfill_state["stop_requested"]:
                    logger.info("Historical backfill stopped by user at %s", current)
                    break
                _backfill_state["current_date"] = current.isoformat()

            # Skip days that already have real data in DB
            if current.isoformat() in existing_dates:
                skipped += 1
                with _backfill_lock:
                    _backfill_state["progress"] += 1
                current += timedelta(days=1)
                continue

            # Daily API call limit (WU allows ~1500/day, keep margin)
            if api_calls >= MAX_DAILY_API_CALLS:
                logger.warning(
                    "Daily API call limit reached (%d calls). Stopping to protect API key.",
                    api_calls,
                )
                with _backfill_lock:
                    _backfill_state["error"] = (
                        f"Limite giornaliero di {MAX_DAILY_API_CALLS} chiamate API raggiunto. "
                        "Riavvia domani con 'Riprendi dall'ultimo dato'."
                    )
                break

            date_str = current.strftime("%Y%m%d")
            obs = client.get_historical_daily(station_id, date_str)
            api_calls += 1

            if obs:
                record = map_daily_observation(obs, station_id, current.isoformat())
                fetched += 1
            else:
                # Insert NULL row to mark the date as processed
                record = {
                    "station_id": station_id,
                    "obs_date": current.isoformat(),
                    "temp_avg_c": None, "temp_high_c": None, "temp_low_c": None,
                    "humidity_avg_pct": None, "humidity_high_pct": None, "humidity_low_pct": None,
                    "dew_point_avg_c": None, "dew_point_high_c": None, "dew_point_low_c": None,
                    "pressure_avg_hpa": None, "pressure_max_hpa": None, "pressure_min_hpa": None,
                    "wind_speed_avg_kmh": None, "wind_speed_high_kmh": None,
                    "wind_gust_high_kmh": None, "precip_total_mm": None,
                }

            _upsert_daily(con, record)
            inserted += 1

            with _backfill_lock:
                _backfill_state["progress"] += 1

            current += timedelta(days=1)
            time.sleep(API_CALL_DELAY)  # Rate limiting

        status = "success"
        error_msg = None
        with _backfill_lock:
            if _backfill_state["stop_requested"]:
                status = "stopped"
            elif api_calls >= MAX_DAILY_API_CALLS:
                status = "api_limit"
                error_msg = _backfill_state.get("error")

    except Exception as e:
        logger.exception("Historical backfill failed")
        status = "error"
        error_msg = str(e)
        with _backfill_lock:
            _backfill_state["error"] = str(e)

    finally:
        cur.execute(
            """UPDATE sync_log
               SET completed_at=%s, status=%s,
                   records_fetched=%s, records_inserted=%s,
                   api_calls_made=%s, error_message=%s
               WHERE id=%s""",
            [datetime.now(timezone.utc), status, fetched, inserted, api_calls, error_msg, log_id],
        )
        cur.close()
        con.close()
        with _backfill_lock:
            _backfill_state["running"] = False

        logger.info(
            "Historical backfill %s: %d days processed, %d with data, %d skipped (already in DB)",
            status, inserted, fetched, skipped,
        )


def _upsert_daily(con, record: dict):
    cols = [
        "station_id", "obs_date",
        "temp_avg_c", "temp_high_c", "temp_low_c",
        "humidity_avg_pct", "humidity_high_pct", "humidity_low_pct",
        "dew_point_avg_c", "dew_point_high_c", "dew_point_low_c",
        "pressure_avg_hpa", "pressure_max_hpa", "pressure_min_hpa",
        "wind_speed_avg_kmh", "wind_speed_high_kmh", "wind_gust_high_kmh",
        "precip_total_mm",
    ]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)

    # Columns to update on conflict (all except PK columns)
    update_cols = [c for c in cols if c not in ("station_id", "obs_date")]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

    values = [record.get(c) for c in cols]
    cur = con.cursor()
    cur.execute(
        f"INSERT INTO daily_observations ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT (station_id, obs_date) DO UPDATE SET {update_clause}",
        values,
    )
    cur.close()
