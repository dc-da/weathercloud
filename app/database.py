import duckdb
import logging

logger = logging.getLogger(__name__)

_DB_PATH: str | None = None


def init_db(db_path: str):
    global _DB_PATH
    _DB_PATH = db_path
    con = duckdb.connect(db_path)
    try:
        _create_schema(con)
        logger.info("Database initialized at %s", db_path)
    finally:
        con.close()


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(_DB_PATH)


def upsert_station_registry(station_id: str, lat: float | None, lon: float | None,
                            name: str | None = None, country: str | None = None,
                            neighborhood: str | None = None):
    """Update or insert station metadata. Called on every current-conditions fetch."""
    if lat is None or lon is None:
        return
    con = get_connection()
    try:
        existing = con.execute(
            "SELECT 1 FROM station_registry WHERE station_id = ?", [station_id]
        ).fetchone()
        now = "current_timestamp"
        if existing:
            con.execute(
                f"""UPDATE station_registry
                    SET latitude = ?, longitude = ?, name = COALESCE(?, name),
                        country = COALESCE(?, country), neighborhood = COALESCE(?, neighborhood),
                        last_seen_at = {now}
                    WHERE station_id = ?""",
                [lat, lon, name, country, neighborhood, station_id],
            )
        else:
            con.execute(
                f"""INSERT INTO station_registry
                    (station_id, name, latitude, longitude, country, neighborhood)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                [station_id, name, lat, lon, country, neighborhood],
            )
    finally:
        con.close()


def get_station_registry() -> list[dict]:
    """Return all stations from the registry."""
    con = get_connection()
    try:
        rows = con.execute("SELECT * FROM station_registry ORDER BY station_id").fetchall()
        cols = [d[0] for d in con.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


def _create_schema(con: duckdb.DuckDBPyConnection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS rapid_observations (
            station_id          VARCHAR NOT NULL,
            observed_at         TIMESTAMP NOT NULL,
            observed_at_local   TIMESTAMP,
            temp_c              DOUBLE,
            heat_index_c        DOUBLE,
            dew_point_c         DOUBLE,
            wind_chill_c        DOUBLE,
            humidity_pct        DOUBLE,
            pressure_hpa        DOUBLE,
            wind_speed_kmh      DOUBLE,
            wind_gust_kmh       DOUBLE,
            wind_dir_deg        INTEGER,
            precip_rate_mmh     DOUBLE,
            precip_total_mm     DOUBLE,
            solar_radiation_wm2 DOUBLE,
            uv_index            DOUBLE,
            synced_at           TIMESTAMP DEFAULT current_timestamp,
            source              VARCHAR DEFAULT 'rapid',
            PRIMARY KEY (station_id, observed_at)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS hourly_observations (
            station_id          VARCHAR NOT NULL,
            observed_at         TIMESTAMP NOT NULL,
            observed_at_local   TIMESTAMP,
            temp_c              DOUBLE,
            heat_index_c        DOUBLE,
            dew_point_c         DOUBLE,
            wind_chill_c        DOUBLE,
            humidity_pct        DOUBLE,
            pressure_hpa        DOUBLE,
            wind_speed_kmh      DOUBLE,
            wind_gust_kmh       DOUBLE,
            wind_dir_deg        INTEGER,
            precip_rate_mmh     DOUBLE,
            precip_total_mm     DOUBLE,
            solar_radiation_wm2 DOUBLE,
            uv_index            DOUBLE,
            synced_at           TIMESTAMP DEFAULT current_timestamp,
            source              VARCHAR DEFAULT 'hourly',
            PRIMARY KEY (station_id, observed_at)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS daily_observations (
            station_id          VARCHAR NOT NULL,
            obs_date            DATE NOT NULL,
            temp_avg_c          DOUBLE,
            temp_high_c         DOUBLE,
            temp_low_c          DOUBLE,
            humidity_avg_pct    DOUBLE,
            humidity_high_pct   DOUBLE,
            humidity_low_pct    DOUBLE,
            dew_point_avg_c     DOUBLE,
            dew_point_high_c    DOUBLE,
            dew_point_low_c     DOUBLE,
            pressure_avg_hpa    DOUBLE,
            pressure_max_hpa    DOUBLE,
            pressure_min_hpa    DOUBLE,
            wind_speed_avg_kmh  DOUBLE,
            wind_speed_high_kmh DOUBLE,
            wind_gust_high_kmh  DOUBLE,
            precip_total_mm     DOUBLE,
            data_source         VARCHAR DEFAULT 'station',
            synced_at           TIMESTAMP DEFAULT current_timestamp,
            source              VARCHAR DEFAULT 'historical',
            PRIMARY KEY (station_id, obs_date)
        )
    """)

    # Migration: add data_source column if missing (existing databases)
    daily_cols = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'daily_observations'"
    ).fetchall()}
    if "data_source" not in daily_cols:
        con.execute("ALTER TABLE daily_observations ADD COLUMN data_source VARCHAR DEFAULT 'station'")

    # Station registry — caches lat/lon and metadata from API
    con.execute("""
        CREATE TABLE IF NOT EXISTS station_registry (
            station_id          VARCHAR PRIMARY KEY,
            name                VARCHAR,
            latitude            DOUBLE,
            longitude           DOUBLE,
            country             VARCHAR,
            neighborhood        VARCHAR,
            first_seen_at       TIMESTAMP DEFAULT current_timestamp,
            last_seen_at        TIMESTAMP DEFAULT current_timestamp
        )
    """)

    con.execute("""
        CREATE SEQUENCE IF NOT EXISTS sync_log_id_seq START 1
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id                  INTEGER DEFAULT nextval('sync_log_id_seq') PRIMARY KEY,
            started_at          TIMESTAMP NOT NULL,
            completed_at        TIMESTAMP,
            job_type            VARCHAR NOT NULL,
            status              VARCHAR NOT NULL,
            records_fetched     INTEGER DEFAULT 0,
            records_inserted    INTEGER DEFAULT 0,
            records_updated     INTEGER DEFAULT 0,
            date_range_start    TIMESTAMP,
            date_range_end      TIMESTAMP,
            error_message       TEXT,
            api_calls_made      INTEGER DEFAULT 0,
            station_id          VARCHAR
        )
    """)

    # Migration: add station_id column if missing (existing databases)
    cols = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'sync_log'").fetchall()}
    if "station_id" not in cols:
        con.execute("ALTER TABLE sync_log ADD COLUMN station_id VARCHAR")

    # Recovery queue — tracks autonomous historical recovery per station
    con.execute("""
        CREATE TABLE IF NOT EXISTS recovery_queue (
            station_id          VARCHAR PRIMARY KEY,
            status              VARCHAR NOT NULL DEFAULT 'pending',
            detected_start      DATE,
            current_date        DATE,
            end_date            DATE,
            days_total          INTEGER DEFAULT 0,
            days_done           INTEGER DEFAULT 0,
            days_skipped        INTEGER DEFAULT 0,
            api_calls_used      INTEGER DEFAULT 0,
            last_run_at         TIMESTAMP,
            created_at          TIMESTAMP DEFAULT current_timestamp,
            error_message       TEXT
        )
    """)

    # Recovery daily runs log
    con.execute("""
        CREATE SEQUENCE IF NOT EXISTS recovery_log_id_seq START 1
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS recovery_log (
            id                  INTEGER DEFAULT nextval('recovery_log_id_seq') PRIMARY KEY,
            run_date            DATE NOT NULL,
            started_at          TIMESTAMP NOT NULL,
            completed_at        TIMESTAMP,
            stations_processed  INTEGER DEFAULT 0,
            api_calls_used      INTEGER DEFAULT 0,
            days_recovered      INTEGER DEFAULT 0,
            days_skipped        INTEGER DEFAULT 0,
            new_stations_found  INTEGER DEFAULT 0,
            status              VARCHAR NOT NULL DEFAULT 'running',
            error_message       TEXT
        )
    """)
