# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeatherStation PWS — a Python/Flask web app for monitoring, storing, and analyzing weather data from multiple personal weather stations (PWS) registered on Weather Underground (WU). The full specification is in `weathercloud spec.md`.

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
- `app/database.py` — DuckDB connection, schema init (includes `recovery_queue` and `recovery_log` tables)
- `app/models.py` — API-to-DB field mapping
- `app/api_client.py` — Weather Underground API client (`station_id` passed per-method, not stored in constructor)
- `app/scheduler.py` — APScheduler: rapid sync, hourly sync, and daily auto-recovery jobs
- `app/sync/` — sync modules:
  - `rapid.py` — 5-min observations (every 4h, all stations)
  - `hourly.py` — hourly observations (every 12h, all stations)
  - `historical.py` — manual backfill (user-triggered per station, with API budget limit)
  - `auto_recovery.py` — autonomous daily historical recovery for all stations
- `app/routes/` — Flask route blueprints:
  - `home.py` — homepage (`/`) and `/api/stations/current`
  - `recovery.py` — recovery recap page (`/recovery`) and `/api/recovery/*`
  - `dashboard.py`, `daily.py`, `historical.py`, `reports.py`, `sync_api.py`, `export.py` — station-scoped under `/station/<station_id>/`
- `app/templates/` — Jinja2 templates (including `home.html`, `recovery.html`)
- `app/static/` — CSS (Anthracite theme) and JS assets

## Multi-Station Config

```yaml
wu:
  api_key: "KEY"
  units: "m"
  primary_station:
    id: "ISANVI15"
    name: "San Vito al Tagliamento"
  secondary_stations:
    - id: "IPORDENONE42"
      name: "Pordenone Centro"
      use_for_gap_fill: true
```

Legacy format (`wu.station_id` as flat string) is auto-normalized at load time.

## URL Structure

- `/` — homepage: overview of all stations with live conditions
- `/station/<station_id>/dashboard` — per-station instantaneous view
- `/station/<station_id>/daily` — per-station daily detail
- `/station/<station_id>/historical` — per-station historical data + manual backfill
- `/station/<station_id>/reports` — per-station reports
- `/station/<station_id>/sync-status` — per-station sync status
- `/recovery` — global auto-recovery status page
- Legacy URLs (`/dashboard`, `/daily`, etc.) redirect to the primary station (301)

All station-scoped JS files use `window.WS_API_PREFIX` (set in `base.html`) to prefix API calls.

## Key Data Flow

1. **Sync jobs** fetch data from WU APIs for all configured stations and store in DuckDB tables (`rapid_observations`, `hourly_observations`, `daily_observations`). Jobs use INSERT OR REPLACE for idempotent upserts.
2. **Missing timestamps** are filled with NULL-valued rows to preserve time grids (5-min for rapid, 1-hour for hourly, daily for historical).
3. **Frontend views** call `/station/<id>/api/*` JSON endpoints which query DuckDB directly. The dashboard proxies live data from the WU API.
4. **Historical backfill** (manual) is user-triggered per station, iterates day-by-day with 5s delay, skips days already in DB, and has a 1300-call daily limit. Reports progress via SSE.
5. **Auto-recovery** runs daily (configurable, default 03:00), processes all stations autonomously within a 1000-call budget. State is persisted in `recovery_queue` table. Primary station gets priority.

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
- The spec is written in Italian; code and comments should be in English.
- `config.yaml` must never be committed. Use `config.yaml.example` as template.
- DB connections in `auto_recovery.py` are opened and closed per operation to avoid blocking rapid/hourly sync.
