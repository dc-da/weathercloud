"""Gap-fill engine: fills missing daily data on the primary station
using distance-weighted averages from secondary gap-fill stations.

All work is done locally on DB data — zero API calls.
"""

import logging
import math
from datetime import datetime, timezone

from ..database import get_connection

logger = logging.getLogger(__name__)

# Fields to gap-fill with weighted average
AVG_FIELDS = [
    "temp_avg_c", "temp_high_c", "temp_low_c",
    "humidity_avg_pct", "humidity_high_pct", "humidity_low_pct",
    "dew_point_avg_c", "dew_point_high_c", "dew_point_low_c",
    "pressure_avg_hpa", "pressure_max_hpa", "pressure_min_hpa",
    "wind_speed_avg_kmh", "wind_speed_high_kmh", "wind_gust_high_kmh",
]

# Fields to gap-fill with max (precipitation is too local for averaging)
MAX_FIELDS = [
    "precip_total_mm",
]

ALL_FIELDS = AVG_FIELDS + MAX_FIELDS


# ---------------------------------------------------------------------------
#  Haversine distance
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
#  Station scoring
# ---------------------------------------------------------------------------

def score_station(distance_km: float) -> float:
    """Score a station based on distance. 0-100, higher = better."""
    K = 5  # decay factor: -5 points per km
    return max(0.0, 100.0 - distance_km * K)


def get_gap_fill_stations(primary_station_id: str, cfg: dict) -> list[dict]:
    """Return scored gap-fill stations with their lat/lon and distance from primary."""
    from ..config import get_all_stations

    stations = get_all_stations(cfg)
    gap_fill_ids = [s["id"] for s in stations if s.get("use_for_gap_fill")]

    if not gap_fill_ids:
        return []

    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT latitude, longitude FROM station_registry WHERE station_id = %s",
            [primary_station_id],
        )
        primary = cur.fetchone()
        if not primary or primary[0] is None:
            cur.close()
            return []

        p_lat, p_lon = primary

        result = []
        for sid in gap_fill_ids:
            cur.execute(
                "SELECT latitude, longitude, name, neighborhood FROM station_registry WHERE station_id = %s",
                [sid],
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                continue

            s_lat, s_lon = row[0], row[1]
            dist = haversine_km(p_lat, p_lon, s_lat, s_lon)
            sc = score_station(dist)

            station_cfg = next((s for s in stations if s["id"] == sid), {})

            result.append({
                "station_id": sid,
                "name": station_cfg.get("name", row[2] or sid),
                "latitude": s_lat,
                "longitude": s_lon,
                "distance_km": round(dist, 2),
                "score": round(sc, 1),
            })

        cur.close()
        result.sort(key=lambda s: s["distance_km"])
        return result
    finally:
        con.close()


# ---------------------------------------------------------------------------
#  Gap-fill execution
# ---------------------------------------------------------------------------

def find_missing_days(primary_station_id: str) -> list[str]:
    """Find days where the primary station has NULL data (or no row)."""
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT obs_date FROM daily_observations
               WHERE station_id = %s
                 AND temp_avg_c IS NULL
               ORDER BY obs_date""",
            [primary_station_id],
        )
        rows = cur.fetchall()
        cur.close()
        return [str(r[0])[:10] for r in rows]
    finally:
        con.close()


def run_gap_fill(primary_station_id: str, cfg: dict) -> dict:
    """Execute gap-fill for all missing days on the primary station."""
    scored_stations = get_gap_fill_stations(primary_station_id, cfg)
    usable = [s for s in scored_stations if s["score"] > 0]

    if not usable:
        return {
            "status": "no_stations",
            "message": "No usable gap-fill stations (all too far or missing coordinates)",
            "days_filled": 0,
            "days_unfillable": 0,
        }

    weights = {s["station_id"]: s["score"] for s in usable}
    station_ids = list(weights.keys())

    missing_days = find_missing_days(primary_station_id)
    if not missing_days:
        return {
            "status": "no_gaps",
            "message": "No missing days found on the primary station",
            "days_filled": 0,
            "days_unfillable": 0,
        }

    logger.info("Gap-fill: %d missing days, %d usable stations", len(missing_days), len(usable))

    days_filled = 0
    days_unfillable = 0

    con = get_connection()
    try:
        cur = con.cursor()
        for day in missing_days:
            record = _compute_weighted_day(cur, day, station_ids, weights)
            if record is None:
                days_unfillable += 1
                continue

            record["station_id"] = primary_station_id
            record["obs_date"] = day
            record["data_source"] = "gap_fill"
            _upsert_gap_fill_record(cur, record)
            days_filled += 1

        cur.close()
    finally:
        con.close()

    logger.info("Gap-fill complete: %d filled, %d unfillable", days_filled, days_unfillable)

    return {
        "status": "success",
        "message": f"{days_filled} days filled, {days_unfillable} unfillable",
        "days_filled": days_filled,
        "days_unfillable": days_unfillable,
        "total_missing": len(missing_days),
        "stations_used": len(usable),
    }


def _compute_weighted_day(cur, day: str, station_ids: list[str],
                          weights: dict[str, float]) -> dict | None:
    """Compute weighted average for a single day from multiple stations."""
    placeholders = ", ".join(["%s"] * len(station_ids))
    cols = ", ".join(ALL_FIELDS)
    cur.execute(
        f"""SELECT station_id, {cols}
            FROM daily_observations
            WHERE obs_date = %s
              AND station_id IN ({placeholders})
              AND temp_avg_c IS NOT NULL""",
        [day] + station_ids,
    )
    rows = cur.fetchall()

    if not rows:
        return None

    result = {}

    for field_idx, field in enumerate(ALL_FIELDS):
        col_idx = field_idx + 1
        values_weights = []
        for row in rows:
            val = row[col_idx]
            sid = row[0]
            if val is not None:
                values_weights.append((val, weights[sid]))

        if not values_weights:
            result[field] = None
            continue

        if field in MAX_FIELDS:
            result[field] = max(v for v, _ in values_weights)
        else:
            total_weight = sum(w for _, w in values_weights)
            if total_weight > 0:
                result[field] = sum(v * w for v, w in values_weights) / total_weight
            else:
                result[field] = None

    if all(v is None for v in result.values()):
        return None

    return result


def _upsert_gap_fill_record(cur, record: dict):
    """Insert or update a gap-filled daily record."""
    cols = [
        "station_id", "obs_date", "data_source",
        "temp_avg_c", "temp_high_c", "temp_low_c",
        "humidity_avg_pct", "humidity_high_pct", "humidity_low_pct",
        "dew_point_avg_c", "dew_point_high_c", "dew_point_low_c",
        "pressure_avg_hpa", "pressure_max_hpa", "pressure_min_hpa",
        "wind_speed_avg_kmh", "wind_speed_high_kmh", "wind_gust_high_kmh",
        "precip_total_mm",
    ]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    update_cols = [c for c in cols if c not in ("station_id", "obs_date")]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    values = [record.get(c) for c in cols]
    cur.execute(
        f"INSERT INTO daily_observations ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT (station_id, obs_date) DO UPDATE SET {update_clause}",
        values,
    )


# ---------------------------------------------------------------------------
#  Public API for web UI
# ---------------------------------------------------------------------------

def get_gap_fill_summary(primary_station_id: str, cfg: dict) -> dict:
    """Return summary info for the gap-fill UI page."""
    scored = get_gap_fill_stations(primary_station_id, cfg)
    missing = find_missing_days(primary_station_id)

    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM daily_observations WHERE station_id = %s AND data_source = 'gap_fill'",
            [primary_station_id],
        )
        filled_count = cur.fetchone()[0]
        cur.close()
    finally:
        con.close()

    return {
        "stations": scored,
        "missing_days_count": len(missing),
        "gap_filled_count": filled_count,
        "missing_days_sample": missing[:30],
    }
