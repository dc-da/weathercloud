import logging
from datetime import datetime, timedelta, timezone

from ..api_client import WUClient
from ..database import get_connection
from ..models import map_hourly_observation

logger = logging.getLogger(__name__)


def sync_hourly(cfg: dict, station_id: str):
    """Fetch hourly observations for the last 7 days and upsert into DB."""
    client = WUClient(cfg)
    con = get_connection()
    started_at = datetime.now(timezone.utc)

    con.execute(
        "INSERT INTO sync_log (started_at, job_type, status, station_id) VALUES (?, 'hourly', 'running', ?)",
        [started_at, station_id],
    )
    log_id = con.execute("SELECT max(id) FROM sync_log").fetchone()[0]

    try:
        observations = client.get_hourly_history_7day(station_id)
        if not observations:
            con.execute(
                "UPDATE sync_log SET completed_at=?, status='success', records_fetched=0, api_calls_made=1 WHERE id=?",
                [datetime.now(timezone.utc), log_id],
            )
            con.close()
            logger.info("Hourly sync: no data returned")
            return

        records = [map_hourly_observation(obs, station_id) for obs in observations]

        timestamps = [r["observed_at"] for r in records if r["observed_at"]]
        if timestamps:
            records = _fill_time_grid(records, station_id, interval_minutes=60)

        inserted = _upsert_records(con, records)

        con.execute(
            """UPDATE sync_log
               SET completed_at=?, status='success',
                   records_fetched=?, records_inserted=?, api_calls_made=1,
                   date_range_start=?, date_range_end=?
               WHERE id=?""",
            [
                datetime.now(timezone.utc),
                len(observations),
                inserted,
                min(timestamps) if timestamps else None,
                max(timestamps) if timestamps else None,
                log_id,
            ],
        )
        logger.info("Hourly sync complete: %d fetched, %d upserted", len(observations), inserted)

    except Exception as e:
        logger.exception("Hourly sync failed")
        con.execute(
            "UPDATE sync_log SET completed_at=?, status='error', error_message=?, api_calls_made=1 WHERE id=?",
            [datetime.now(timezone.utc), str(e), log_id],
        )
    finally:
        con.close()


def _fill_time_grid(records: list[dict], station_id: str, interval_minutes: int) -> list[dict]:
    from datetime import datetime as dt

    existing = {}
    for r in records:
        ts = r["observed_at"]
        if ts:
            if isinstance(ts, str):
                ts_parsed = dt.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                ts_parsed = ts
            rounded = ts_parsed.replace(minute=0, second=0, microsecond=0)
            existing[rounded] = r

    if not existing:
        return records

    ts_min = min(existing.keys())
    ts_max = max(existing.keys())

    filled = []
    current = ts_min
    while current <= ts_max:
        if current in existing:
            filled.append(existing[current])
        else:
            filled.append({
                "station_id": station_id,
                "observed_at": current.isoformat(),
                "observed_at_local": None,
                "temp_c": None, "heat_index_c": None, "dew_point_c": None,
                "wind_chill_c": None, "humidity_pct": None, "pressure_hpa": None,
                "wind_speed_kmh": None, "wind_gust_kmh": None, "wind_dir_deg": None,
                "precip_rate_mmh": None, "precip_total_mm": None,
                "solar_radiation_wm2": None, "uv_index": None,
            })
        current += timedelta(minutes=interval_minutes)

    return filled


def _upsert_records(con, records: list[dict]) -> int:
    if not records:
        return 0

    cols = [
        "station_id", "observed_at", "observed_at_local",
        "temp_c", "heat_index_c", "dew_point_c", "wind_chill_c",
        "humidity_pct", "pressure_hpa",
        "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg",
        "precip_rate_mmh", "precip_total_mm",
        "solar_radiation_wm2", "uv_index",
    ]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)

    count = 0
    for r in records:
        values = [r.get(c) for c in cols]
        con.execute(
            f"INSERT OR REPLACE INTO hourly_observations ({col_names}) VALUES ({placeholders})",
            values,
        )
        count += 1

    return count
