#!/usr/bin/env python3
"""Migrate all data from DuckDB to PostgreSQL.

Usage:
    python scripts/migrate_duckdb_to_pg.py

Prerequisites:
    1. PostgreSQL schema created: psql -U weather -d weathercloud -f scripts/pg_schema.sql
    2. pip install psycopg2-binary (or psycopg[binary])
"""

import sys
import os

import duckdb
import psycopg2
from psycopg2.extras import execute_values

DUCKDB_PATH = "data/weather.duckdb"
PG_DSN = "host=localhost dbname=weathercloud user=weather password=weather options=-csearch_path=weather"

# Column renames between DuckDB and PostgreSQL (DuckDB name → PG name)
COLUMN_RENAMES = {
    "recovery_queue": {"current_date": "recovery_current_date"},
}

# Tables to migrate in order (respects no FK dependencies, but logical order)
TABLES = [
    "station_registry",
    "rapid_observations",
    "hourly_observations",
    "daily_observations",
    "sync_log",
    "recovery_queue",
    "recovery_log",
]

BATCH_SIZE = 1000


def get_columns(duck_con, table: str) -> list[str]:
    """Get column names from DuckDB table."""
    rows = duck_con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return [r[0] for r in rows]


def migrate_table(duck_con, pg_con, table: str):
    """Migrate a single table from DuckDB to PostgreSQL."""
    columns = get_columns(duck_con, table)
    if not columns:
        print(f"  SKIP {table}: no columns found in DuckDB")
        return

    # For tables with SERIAL PKs, exclude 'id' to let PostgreSQL auto-generate
    serial_tables = {"sync_log", "recovery_log"}
    if table in serial_tables and "id" in columns:
        columns = [c for c in columns if c != "id"]

    # Apply column renames for PostgreSQL
    renames = COLUMN_RENAMES.get(table, {})
    pg_columns = [renames.get(c, c) for c in columns]

    col_names = ", ".join(pg_columns)
    placeholders = ", ".join(["%s"] * len(columns))

    # Read all rows from DuckDB (using original DuckDB column names)
    duck_col_names = ", ".join(columns)
    rows = duck_con.execute(f"SELECT {duck_col_names} FROM {table}").fetchall()
    total = len(rows)

    if total == 0:
        print(f"  {table}: 0 rows (empty)")
        return

    # Build ON CONFLICT clause for upsert
    conflict_clause = _conflict_clause(table, columns)

    insert_sql = f"INSERT INTO {table} ({col_names}) VALUES %s {conflict_clause}"

    pg_cur = pg_con.cursor()
    try:
        # Convert DuckDB values to Python-native types for psycopg2
        clean_rows = []
        for row in rows:
            clean = []
            for val in row:
                if val is not None and hasattr(val, 'isoformat'):
                    clean.append(val.isoformat() if hasattr(val, 'isoformat') else str(val))
                else:
                    clean.append(val)
            clean_rows.append(tuple(clean))

        # Insert in batches
        migrated = 0
        for i in range(0, len(clean_rows), BATCH_SIZE):
            batch = clean_rows[i:i + BATCH_SIZE]
            execute_values(pg_cur, insert_sql, batch, page_size=BATCH_SIZE)
            migrated += len(batch)

        pg_con.commit()
        print(f"  {table}: {migrated}/{total} rows migrated")

        # Reset serial sequence for tables with auto-increment
        if table in serial_tables:
            pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
            pg_con.commit()

    except Exception as e:
        pg_con.rollback()
        print(f"  {table}: ERROR — {e}")
        raise
    finally:
        pg_cur.close()


def _conflict_clause(table: str, columns: list[str]) -> str:
    """Build ON CONFLICT DO NOTHING for tables with PKs."""
    pk_map = {
        "rapid_observations": "(station_id, observed_at)",
        "hourly_observations": "(station_id, observed_at)",
        "daily_observations": "(station_id, obs_date)",
        "station_registry": "(station_id)",
        "recovery_queue": "(station_id)",
        "sync_log": "",  # no conflict, SERIAL PK excluded
        "recovery_log": "",  # no conflict, SERIAL PK excluded
    }
    pk = pk_map.get(table, "")
    if pk:
        return f"ON CONFLICT {pk} DO NOTHING"
    return ""


def main():
    if not os.path.exists(DUCKDB_PATH):
        print(f"ERROR: DuckDB file not found at {DUCKDB_PATH}")
        sys.exit(1)

    print(f"Connecting to DuckDB: {DUCKDB_PATH}")
    duck_con = duckdb.connect(DUCKDB_PATH, read_only=True)

    print(f"Connecting to PostgreSQL: {PG_DSN}")
    pg_con = psycopg2.connect(PG_DSN)

    print()
    print("Starting migration...")
    print("=" * 50)

    for table in TABLES:
        migrate_table(duck_con, pg_con, table)

    print("=" * 50)
    print("Migration complete!")

    # Verify counts
    print()
    print("Verification:")
    pg_cur = pg_con.cursor()
    for table in TABLES:
        duck_count = duck_con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
        pg_count = pg_cur.fetchone()[0]
        status = "OK" if pg_count >= duck_count else "MISMATCH"
        print(f"  {table:30s} DuckDB={duck_count:>8d}  PG={pg_count:>8d}  [{status}]")
    pg_cur.close()

    duck_con.close()
    pg_con.close()


if __name__ == "__main__":
    main()
