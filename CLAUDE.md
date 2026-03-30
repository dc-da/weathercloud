# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeatherStation PWS — a Python/Flask web app for monitoring, storing, and analyzing weather data from multiple personal weather stations (PWS) registered on Weather Underground (WU). One station is designated as "primary"; secondary stations can be used for gap-filling missing data. The full specification is in `weathercloud spec.md`.

## Tech Stack

- **Backend:** Python 3.13 / Flask
- **Database:** DuckDB (embedded, single file at `data/weather.duckdb`)
- **Frontend:** HTML5/CSS3/JS with Plotly.js (charts) and DataTables.js (tables), dark Anthracite theme
- **Scheduler:** APScheduler (integrated in Flask)
- **Config:** YAML (`config.yaml`) — contains API keys, must be in `.gitignore`

## Development Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

The app runs on `http://0.0.0.0:5001` by default. On first run, it creates the DuckDB database and tables automatically.

## Architecture

The project follows a Flask app-factory pattern with multi-station support:

- `run.py` — entry point
- `app/__init__.py` — Flask app factory, `before_request` station validation, `context_processor`, legacy URL redirects
- `app/config.py` — loads `config.yaml`, normalizes legacy single-station format, provides `get_all_stations()`, `get_station_by_id()`, `get_primary_station_id()`
- `app/database.py` — DuckDB connection, schema init, `upsert_station_registry()`, `get_station_registry()`
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
  - `dashboard.py`, `daily.py`, `historical.py`, `reports.py`, `sync_api.py`, `export.py` — station-scoped under `/station/<station_id>/`
- `app/templates/` — Jinja2 templates
- `app/static/` — CSS (Anthracite theme) and JS assets

## Database Tables

| Table | Purpose |
|---|---|
| `rapid_observations` | 5-min data, PK: `(station_id, observed_at)` |
| `hourly_observations` | Hourly data, PK: `(station_id, observed_at)` |
| `daily_observations` | Daily summaries, PK: `(station_id, obs_date)`. Has `data_source` column (`'station'` or `'gap_fill'`) |
| `station_registry` | Cached lat/lon/metadata per station, populated from API current conditions |
| `sync_log` | Log of all sync operations (rapid, hourly, historical) |
| `recovery_queue` | Tracks autonomous recovery state per station |
| `recovery_log` | Daily auto-recovery run history |

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
- `/station/<station_id>/gap-fill` — gap-fill page (primary station only)
- `/recovery` — global auto-recovery status page
- Legacy URLs (`/dashboard`, `/daily`, etc.) redirect to the primary station (301)

All station-scoped JS files use `window.WS_API_PREFIX` (set in `base.html`) to prefix API calls.

## Key Data Flow

1. **Sync jobs** fetch data from WU APIs for all configured stations and store in DuckDB tables. Jobs use INSERT OR REPLACE for idempotent upserts.
2. **Missing timestamps** are filled with NULL-valued rows to preserve time grids (5-min for rapid, 1-hour for hourly, daily for historical).
3. **Frontend views** call `/station/<id>/api/*` JSON endpoints which query DuckDB directly. The dashboard proxies live data from the WU API.
4. **Station registry** is populated automatically whenever current conditions are fetched (homepage or dashboard). Stores lat/lon for distance calculations.
5. **Historical backfill** (manual) is user-triggered per station, iterates day-by-day with 5s delay, skips days already in DB, and has a 1300-call daily limit. Reports progress via SSE.
6. **Auto-recovery** runs daily (configurable, default 03:00), processes all stations autonomously within a 1000-call budget. State is persisted in `recovery_queue` table. Primary station gets priority.
7. **Gap-fill** reconstructs missing daily data on the primary station using distance-weighted averages from secondary stations marked `use_for_gap_fill: true`. Uses Haversine distance for scoring (100 - km*5). Precipitation uses max instead of average. Zero API calls — pure DB operations. Records are marked with `data_source='gap_fill'`.

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

- All timestamps in DB are UTC; local timestamps stored separately in `observed_at_local`.
- All DB tables have `station_id` in their primary key — data from different stations coexists safely.
- API field names vary between rapid/hourly/current responses — mapping must handle both variants with fallbacks (see spec "Mapping Campi API → Database").
- All API fields are displayed raw in tables (no aggregations outside reports tab).
- The spec is written in Italian; code and comments should be in English.
- `config.yaml` must never be committed. Use `config.yaml.example` as template.
- DB connections in `auto_recovery.py` and `gap_fill.py` are opened and closed per operation to avoid blocking rapid/hourly sync.
