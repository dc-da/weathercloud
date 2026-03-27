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
            synced_at           TIMESTAMP DEFAULT current_timestamp,
            source              VARCHAR DEFAULT 'historical',
            PRIMARY KEY (station_id, obs_date)
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
            api_calls_made      INTEGER DEFAULT 0
        )
    """)
