-- ==========================================================================
-- WeatherStation PWS — PostgreSQL Schema (schema: weather)
-- Prerequisites: run pg_setup.sql as superuser first
-- Run as: psql -U weather -d weathercloud -f scripts/pg_schema.sql
-- ==========================================================================

SET search_path TO weather;

-- Rapid observations (5-min intervals)
CREATE TABLE IF NOT EXISTS rapid_observations (
    station_id          VARCHAR(30) NOT NULL,
    observed_at         TIMESTAMPTZ NOT NULL,
    observed_at_local   TIMESTAMP,
    temp_c              DOUBLE PRECISION,
    heat_index_c        DOUBLE PRECISION,
    dew_point_c         DOUBLE PRECISION,
    wind_chill_c        DOUBLE PRECISION,
    humidity_pct        DOUBLE PRECISION,
    pressure_hpa        DOUBLE PRECISION,
    wind_speed_kmh      DOUBLE PRECISION,
    wind_gust_kmh       DOUBLE PRECISION,
    wind_dir_deg        INTEGER,
    precip_rate_mmh     DOUBLE PRECISION,
    precip_total_mm     DOUBLE PRECISION,
    solar_radiation_wm2 DOUBLE PRECISION,
    uv_index            DOUBLE PRECISION,
    synced_at           TIMESTAMPTZ DEFAULT now(),
    source              VARCHAR(20) DEFAULT 'rapid',
    PRIMARY KEY (station_id, observed_at)
);

-- Hourly observations
CREATE TABLE IF NOT EXISTS hourly_observations (
    station_id          VARCHAR(30) NOT NULL,
    observed_at         TIMESTAMPTZ NOT NULL,
    observed_at_local   TIMESTAMP,
    temp_c              DOUBLE PRECISION,
    heat_index_c        DOUBLE PRECISION,
    dew_point_c         DOUBLE PRECISION,
    wind_chill_c        DOUBLE PRECISION,
    humidity_pct        DOUBLE PRECISION,
    pressure_hpa        DOUBLE PRECISION,
    wind_speed_kmh      DOUBLE PRECISION,
    wind_gust_kmh       DOUBLE PRECISION,
    wind_dir_deg        INTEGER,
    precip_rate_mmh     DOUBLE PRECISION,
    precip_total_mm     DOUBLE PRECISION,
    solar_radiation_wm2 DOUBLE PRECISION,
    uv_index            DOUBLE PRECISION,
    synced_at           TIMESTAMPTZ DEFAULT now(),
    source              VARCHAR(20) DEFAULT 'hourly',
    PRIMARY KEY (station_id, observed_at)
);

-- Daily observations (historical summaries)
CREATE TABLE IF NOT EXISTS daily_observations (
    station_id          VARCHAR(30) NOT NULL,
    obs_date            DATE NOT NULL,
    temp_avg_c          DOUBLE PRECISION,
    temp_high_c         DOUBLE PRECISION,
    temp_low_c          DOUBLE PRECISION,
    humidity_avg_pct    DOUBLE PRECISION,
    humidity_high_pct   DOUBLE PRECISION,
    humidity_low_pct    DOUBLE PRECISION,
    dew_point_avg_c     DOUBLE PRECISION,
    dew_point_high_c    DOUBLE PRECISION,
    dew_point_low_c     DOUBLE PRECISION,
    pressure_avg_hpa    DOUBLE PRECISION,
    pressure_max_hpa    DOUBLE PRECISION,
    pressure_min_hpa    DOUBLE PRECISION,
    wind_speed_avg_kmh  DOUBLE PRECISION,
    wind_speed_high_kmh DOUBLE PRECISION,
    wind_gust_high_kmh  DOUBLE PRECISION,
    precip_total_mm     DOUBLE PRECISION,
    data_source         VARCHAR(20) DEFAULT 'station',
    synced_at           TIMESTAMPTZ DEFAULT now(),
    source              VARCHAR(20) DEFAULT 'historical',
    PRIMARY KEY (station_id, obs_date)
);

-- Station registry (cached metadata from WU API)
CREATE TABLE IF NOT EXISTS station_registry (
    station_id          VARCHAR(30) PRIMARY KEY,
    name                VARCHAR(100),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    country             VARCHAR(10),
    neighborhood        VARCHAR(100),
    first_seen_at       TIMESTAMPTZ DEFAULT now(),
    last_seen_at        TIMESTAMPTZ DEFAULT now()
);

-- Sync log
CREATE TABLE IF NOT EXISTS sync_log (
    id                  SERIAL PRIMARY KEY,
    started_at          TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ,
    job_type            VARCHAR(30) NOT NULL,
    status              VARCHAR(30) NOT NULL,
    records_fetched     INTEGER DEFAULT 0,
    records_inserted    INTEGER DEFAULT 0,
    records_updated     INTEGER DEFAULT 0,
    date_range_start    TIMESTAMPTZ,
    date_range_end      TIMESTAMPTZ,
    error_message       TEXT,
    api_calls_made      INTEGER DEFAULT 0,
    station_id          VARCHAR(30)
);

-- Recovery queue
CREATE TABLE IF NOT EXISTS recovery_queue (
    station_id          VARCHAR(30) PRIMARY KEY,
    status              VARCHAR(30) NOT NULL DEFAULT 'pending',
    detected_start      DATE,
    recovery_current_date DATE,
    end_date            DATE,
    days_total          INTEGER DEFAULT 0,
    days_done           INTEGER DEFAULT 0,
    days_skipped        INTEGER DEFAULT 0,
    api_calls_used      INTEGER DEFAULT 0,
    last_run_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    error_message       TEXT
);

-- Recovery log
CREATE TABLE IF NOT EXISTS recovery_log (
    id                  SERIAL PRIMARY KEY,
    run_date            DATE NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ,
    stations_processed  INTEGER DEFAULT 0,
    api_calls_used      INTEGER DEFAULT 0,
    days_recovered      INTEGER DEFAULT 0,
    days_skipped        INTEGER DEFAULT 0,
    new_stations_found  INTEGER DEFAULT 0,
    status              VARCHAR(30) NOT NULL DEFAULT 'running',
    error_message       TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rapid_station_time ON rapid_observations (station_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_hourly_station_time ON hourly_observations (station_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_daily_station_date ON daily_observations (station_id, obs_date DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_started ON sync_log (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_station ON sync_log (station_id);
CREATE INDEX IF NOT EXISTS idx_recovery_log_date ON recovery_log (run_date DESC);
