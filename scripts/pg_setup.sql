-- ==========================================================================
-- WeatherStation PWS — PostgreSQL Setup (run as superuser postgres)
-- Run: sudo -u postgres psql -d weathercloud -f scripts/pg_setup.sql
-- ==========================================================================

-- Create schema owned by weather user
CREATE SCHEMA IF NOT EXISTS weather AUTHORIZATION weather;

-- Set default search_path so weather user finds tables without prefix
ALTER ROLE weather SET search_path TO weather;
