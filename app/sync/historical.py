import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

from ..api_client import WUClient
from ..database import get_connection
from ..models import map_daily_observation

logger = logging.getLogger(__name__)

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


def get_last_synced_date(station_id: str) -> date | None:
    """Find the most recent obs_date in daily_observations for auto-resume."""
    con = get_connection()
    try:
        result = con.execute(
            "SELECT MAX(obs_date) FROM daily_observations WHERE station_id = ?",
            [station_id],
        ).fetchone()
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


def start_backfill(cfg: dict, start_date: date | None = None):
    """Start the historical backfill in a background thread.

    If start_date is None, auto-resume from the day after the last synced date.
    If no data exists at all, start_date must be provided by the user.
    """
    with _backfill_lock:
        if _backfill_state["running"]:
            return False
        _backfill_state.update(
            running=True, stop_requested=False, progress=0, total=0,
            current_date=None, error=None,
        )

    thread = threading.Thread(target=_run_backfill, args=(cfg, start_date), daemon=True)
    thread.start()
    return True


def _run_backfill(cfg: dict, start_date: date | None):
    client = WUClient(cfg)
    station_id = cfg["wu"]["station_id"]
    con = get_connection()
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
            con.close()
            return

    end_date = date.today()

    if start_date > end_date:
        with _backfill_lock:
            _backfill_state.update(running=False, error=None, progress=0, total=0)
        con.close()
        logger.info("Historical backfill: already up to date")
        return

    total_days = (end_date - start_date).days + 1

    with _backfill_lock:
        _backfill_state["total"] = total_days

    # Sync log entry
    con.execute(
        "INSERT INTO sync_log (started_at, job_type, status, date_range_start, date_range_end) "
        "VALUES (?, 'historical', 'running', ?, ?)",
        [started_at, start_date.isoformat(), end_date.isoformat()],
    )
    log_id = con.execute("SELECT max(id) FROM sync_log").fetchone()[0]

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

            date_str = current.strftime("%Y%m%d")
            obs = client.get_historical_daily(date_str)
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
            time.sleep(0.5)  # Rate limiting

        status = "success"
        error_msg = None
        with _backfill_lock:
            if _backfill_state["stop_requested"]:
                status = "stopped"

    except Exception as e:
        logger.exception("Historical backfill failed")
        status = "error"
        error_msg = str(e)
        with _backfill_lock:
            _backfill_state["error"] = str(e)

    finally:
        con.execute(
            """UPDATE sync_log
               SET completed_at=?, status=?,
                   records_fetched=?, records_inserted=?,
                   api_calls_made=?, error_message=?
               WHERE id=?""",
            [datetime.now(timezone.utc), status, fetched, inserted, api_calls, error_msg, log_id],
        )
        con.close()
        with _backfill_lock:
            _backfill_state["running"] = False

        logger.info(
            "Historical backfill %s: %d days processed, %d with data",
            status, inserted, fetched,
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
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    values = [record.get(c) for c in cols]
    con.execute(
        f"INSERT OR REPLACE INTO daily_observations ({col_names}) VALUES ({placeholders})",
        values,
    )
