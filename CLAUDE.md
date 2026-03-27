# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeatherStation PWS — a Python/Flask web app for monitoring, storing, and analyzing weather data from a personal weather station (PWS) registered on Weather Underground (WU). The full specification is in `weathercloud spec.md`.

## Tech Stack

- **Backend:** Python 3.13 / Flask
- **Database:** DuckDB (embedded, single file at `data/weather.duckdb`)
- **Frontend:** HTML5/CSS3/JS with Plotly.js (charts) and DataTables.js (tables)
- **Scheduler:** APScheduler (integrated in Flask)
- **Config:** YAML (`config.yaml`) — contains API keys, must be in `.gitignore`

## Development Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

The app runs on `http://0.0.0.0:5000` by default. On first run, it creates the DuckDB database and tables automatically.

## Architecture

The project follows a Flask app-factory pattern:

- `run.py` — entry point
- `app/__init__.py` — Flask app factory
- `app/config.py` — loads `config.yaml`
- `app/database.py` — DuckDB connection, schema init, query utilities
- `app/models.py` — API-to-DB field mapping
- `app/api_client.py` — Weather Underground API client
- `app/scheduler.py` — APScheduler setup and job definitions
- `app/sync/` — sync jobs: `rapid.py` (every 4h), `hourly.py` (every 12h), `historical.py` (manual backfill)
- `app/routes/` — Flask route blueprints for views and JSON API endpoints
- `app/templates/` — Jinja2 templates
- `app/static/` — CSS and JS assets

## Key Data Flow

1. **Sync jobs** fetch data from WU APIs and store in DuckDB tables (`rapid_observations`, `hourly_observations`, `daily_observations`). Jobs use INSERT OR REPLACE for idempotent upserts.
2. **Missing timestamps** are filled with NULL-valued rows to preserve time grids (5-min for rapid, 1-hour for hourly, daily for historical).
3. **Frontend views** call `/api/*` JSON endpoints which query DuckDB directly. The dashboard (`/api/current`) proxies live data from the WU API.
4. **Historical backfill** is user-triggered, iterates day-by-day with 500ms throttling, and reports progress via SSE.

## Important Conventions

- All timestamps in DB are UTC; local timestamps stored separately in `observed_at_local`.
- API field names vary between rapid/hourly/current responses — mapping must handle both variants with fallbacks (see spec "Mapping Campi API → Database").
- The spec is written in Italian; code and comments should be in English.
- `config.yaml` must never be committed. Use `config.yaml.example` as template.
