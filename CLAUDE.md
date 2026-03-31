# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeatherStation PWS — a Python/Flask web app for monitoring, storing, and analyzing weather data from multiple personal weather stations (PWS) registered on Weather Underground (WU). One station is designated as "primary"; secondary stations can be used for gap-filling missing data. The full specification is in `weathercloud spec.md`.

## Tech Stack

- **Backend:** Python 3.13 / Flask
- **Database:** PostgreSQL 16+ (schema `weather` in database `weathercloud`, user `weather`)
- **DB Driver:** psycopg2 (`psycopg2-binary`)
- **Frontend:** HTML5/CSS3/JS with Plotly.js (charts) and DataTables.js (tables), dark Anthracite theme
- **Scheduler:** APScheduler (integrated in Flask)
- **Config:** YAML (`config.yaml`) — contains API keys and DB credentials, must be in `.gitignore`

## Development Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

PostgreSQL must be running with database `weathercloud`, schema `weather`, user `weather`.
Schema creation: `scripts/pg_setup.sql` (as superuser), then `scripts/pg_schema.sql` (as weather user).
The app runs on `http://0.0.0.0:5001` by default.

## Database

- **Engine:** PostgreSQL with dedicated schema `weather` (not `public`)
- **Connection:** psycopg2 with `autocommit=True` and `search_path=weather` set via connection options
- **Driver pattern:** `get_connection()` returns a new connection each time; callers use `cur = con.cursor()` for all queries
- **Upserts:** `INSERT ... ON CONFLICT (pk_cols) DO UPDATE SET col = EXCLUDED.col` (PostgreSQL native)
- **Placeholders:** `%s` (psycopg2 style, NOT `?`)
- **Casting:** `column::date` for date casts (PostgreSQL style, NOT `CAST(x AS DATE)`)
- **Schema script:** `scripts/pg_schema.sql` — all tables, indexes, sequences
- **Migration from DuckDB:** `scripts/migrate_duckdb_to_pg.py` (one-time, historical)
- **Reserved word:** `current_date` is reserved in PostgreSQL — the recovery_queue column is named `recovery_current_date`

### Config

```yaml
database:
  host: "localhost"
  port: 5432
  name: "weathercloud"
  user: "weather"
  password: "weather"
  schema: "weather"
```

### Tables

| Table | Purpose |
|---|---|
| `rapid_observations` | 5-min data, PK: `(station_id, observed_at)` |
| `hourly_observations` | Hourly data, PK: `(station_id, observed_at)` |
| `daily_observations` | Daily summaries, PK: `(station_id, obs_date)`. Has `data_source` column (`'station'` or `'gap_fill'`) |
| `station_registry` | Cached lat/lon/metadata per station, populated from API current conditions |
| `sync_log` | Log of all sync operations (SERIAL PK) |
| `recovery_queue` | Tracks autonomous recovery state per station |
| `recovery_log` | Daily auto-recovery run history (SERIAL PK) |

## Architecture

The project follows a Flask app-factory pattern with multi-station support:

- `run.py` — entry point
- `app/__init__.py` — Flask app factory, `before_request` station validation, `context_processor`, legacy URL redirects
- `app/config.py` — loads `config.yaml`, normalizes legacy single-station format, provides `get_all_stations()`, `get_station_by_id()`, `get_primary_station_id()`
- `app/database.py` — PostgreSQL connection (`psycopg2`), `upsert_station_registry()`, `get_station_registry()`
- `app/models.py` — API-to-DB field mapping (extracts lat/lon from current conditions)
- `app/api_client.py` — Weather Underground API client (`station_id` passed per-method, not stored in constructor)
- `app/scheduler.py` — APScheduler: rapid sync, hourly sync, daily auto-recovery jobs
- `app/sync/` — sync modules:
  - `rapid.py` — 5-min observations (every 4h, all stations)
  - `hourly.py` — hourly observations (every 12h, all stations)
  - `historical.py` — manual backfill (user-triggered per station, with API budget limit)
  - `auto_recovery.py` — autonomous daily historical recovery for all stations
  - `gap_fill.py` — fills missing daily data on primary station using distance-weighted averages from secondary stations
- `app/routes/` — Flask route blueprints:
  - `home.py` — homepage (`/`) and `/api/stations/current` (also populates `station_registry`)
  - `recovery.py` — recovery recap page (`/recovery`) and `/api/recovery/*`
  - `gap_fill.py` — gap-fill page and API (`/station/<id>/gap-fill`, primary station only)
  - `forecast.py` — 5-day forecast page and API (`/station/<id>/forecast`)
  - `dashboard.py`, `daily.py`, `historical.py`, `reports.py`, `sync_api.py`, `export.py` — station-scoped under `/station/<station_id>/`
- `app/templates/` — Jinja2 templates
- `app/static/` — CSS (Anthracite theme) and JS assets

## Multi-Station Config

```yaml
wu:
  api_key: "KEY"
  units: "m"
  primary_station:
    id: "ISANVI15"
    name: "San Vito Romano"
  secondary_stations:
    - id: "IROCCA85"
      name: "Rocca Santo Stefano"
      use_for_gap_fill: false
scheduler:
  auto_recovery:
    enabled: true
    daily_api_budget: 1000
    run_at: "03:00"
```

Legacy format (`wu.station_id` as flat string) is auto-normalized at load time.

## URL Structure

- `/` — homepage: overview of all stations with live conditions and coordinates
- `/station/<station_id>/dashboard` — per-station instantaneous view
- `/station/<station_id>/daily` — per-station daily detail (all fields visible: temp, heat index, dew point, wind chill, humidity, pressure, wind, gust, direction, precip, solar, UV)
- `/station/<station_id>/historical` — per-station historical data + manual backfill (all daily fields visible in table and chart, gap-filled rows highlighted in amber)
- `/station/<station_id>/reports` — per-station reports
- `/station/<station_id>/sync-status` — per-station sync status
- `/station/<station_id>/forecast` — 5-day weather forecast (uses lat/lon from `station_registry`, calls WU v3 forecast API)
- `/station/<station_id>/gap-fill` — gap-fill page (primary station only)
- `/recovery` — global auto-recovery status page
- Legacy URLs (`/dashboard`, `/daily`, etc.) redirect to the primary station (301)

All station-scoped JS files use `window.WS_API_PREFIX` (set in `base.html`) to prefix API calls.

## Key Data Flow

1. **Sync jobs** fetch data from WU APIs for all configured stations and store in PostgreSQL tables. Jobs use `INSERT ... ON CONFLICT ... DO UPDATE` for idempotent upserts.
2. **Missing timestamps** are filled with NULL-valued rows to preserve time grids (5-min for rapid, 1-hour for hourly, daily for historical).
3. **Frontend views** call `/station/<id>/api/*` JSON endpoints which query PostgreSQL directly. The dashboard proxies live data from the WU API.
4. **Station registry** is populated automatically whenever current conditions are fetched (homepage or dashboard). Stores lat/lon for distance calculations.
5. **Historical backfill** (manual) is user-triggered per station, iterates day-by-day with 5s delay, skips days already in DB, and has a 1300-call daily limit. Reports progress via SSE.
6. **Auto-recovery** runs daily (configurable, default 03:00), processes all stations autonomously within a 1000-call budget. State is persisted in `recovery_queue` table. Primary station gets priority.
7. **Forecast** fetches 5-day daily forecast from WU v3 API using station lat/lon from the registry. Returns day/night split with temp, precip chance, wind, humidity, UV, cloud cover, moon phase, sunrise/sunset. WU icon codes mapped to Bootstrap Icons.
8. **Gap-fill** reconstructs missing daily data on the primary station using distance-weighted averages from secondary stations marked `use_for_gap_fill: true`. Uses Haversine distance for scoring (100 - km*5). Precipitation uses max instead of average. Zero API calls — pure DB operations. Records are marked with `data_source='gap_fill'`.

## Gap-Fill Details

- **Scoring**: `score = max(0, 100 - distance_km * 5)` — stations beyond 20km score 0
- **Weighted average**: `value = sum(val_i * score_i) / sum(score_i)` for all fields except precipitation
- **Precipitation**: uses `max()` across stations (too local for averaging)
- **Visual distinction**: table rows have amber background + icon; chart points shown as amber diamonds
- **WU elevation data is unreliable** (tested: reports 219m for a 700m station) — only lat/lon are used

## WU API Rate Limits

- 30 calls/minute, 1500 calls/day
- Sync delay: 5s between historical API calls
- Manual backfill budget: 1300 calls/day
- Auto-recovery budget: configurable (default 1000 calls/day)
- Rapid/hourly sync: ~1 call per station per run (negligible)

## Important Conventions

- All timestamps in DB are UTC (`TIMESTAMPTZ`); local timestamps stored separately in `observed_at_local`.
- All DB tables have `station_id` in their primary key — data from different stations coexists safely.
- API field names vary between rapid/hourly/current responses — mapping must handle both variants with fallbacks (see spec "Mapping Campi API → Database").
- All API fields are displayed raw in tables (no aggregations outside reports tab).
- The spec is written in Italian; code and comments should be in English.
- `config.yaml` must never be committed. Use `config.yaml.example` as template.
- DB connections use `autocommit=True` — no explicit `commit()` needed. Short-lived connections (open-query-close) in background jobs to avoid contention.

## Known PostgreSQL Pitfalls

- **`current_date` is reserved** — cannot be used as a column name. The recovery_queue column is `recovery_current_date`. The `_upsert_queue()` function in `auto_recovery.py` remaps `current_date` → `recovery_current_date` automatically.
- **Schema isolation** — all tables live in schema `weather`, not `public`. Connection sets `search_path=weather` via options. The schema must be created by a superuser first (`scripts/pg_setup.sql`).
- **`%s` placeholders** — psycopg2 uses `%s` for all parameter types (not `?` like DuckDB/sqlite). Never use f-strings for user values.
- **`INSERT ... ON CONFLICT`** — replaces DuckDB's `INSERT OR REPLACE`. Requires explicit PK columns and `EXCLUDED.col` references.

## Frontend Pitfalls

- **DataTables column count** — The number of `<th>` elements in the HTML `<thead>` MUST match the number of columns in the JS `TABLE_COLUMNS` array, or the table silently fails to render.
- **Plotly all-null traces** — A trace where every y-value is `null` can break axis scaling. Always filter: `if (yValues.every(v => v == null)) return;` before adding a trace.

## Homepage Layout

- **Primary station**: full-width card (`col-12`) with hero temperature + all metrics in grid with colored icons
- **Secondary stations**: compact cards (`col-xl-3`) sorted by online status then distance from primary (Haversine)
- **Offline stations**: faded (opacity 0.45), grouped at bottom
- **Search bar**: filters by station name or ID in real-time
