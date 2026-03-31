import logging

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_DB_CFG: dict | None = None


def init_db(db_cfg: dict):
    """Store DB config and verify connection."""
    global _DB_CFG
    _DB_CFG = db_cfg
    con = get_connection()
    try:
        con.cursor().execute("SELECT 1")
        con.commit()
        logger.info("Database connected: %s@%s/%s (schema: %s)",
                     db_cfg["user"], db_cfg["host"], db_cfg["name"], db_cfg.get("schema", "weather"))
    finally:
        con.close()


def get_connection():
    """Return a new psycopg2 connection with search_path set to the configured schema."""
    schema = _DB_CFG.get("schema", "weather")
    con = psycopg2.connect(
        host=_DB_CFG["host"],
        port=_DB_CFG.get("port", 5432),
        dbname=_DB_CFG["name"],
        user=_DB_CFG["user"],
        password=_DB_CFG["password"],
        options=f"-csearch_path={schema}",
    )
    con.autocommit = True
    return con


def upsert_station_registry(station_id: str, lat: float | None, lon: float | None,
                            name: str | None = None, country: str | None = None,
                            neighborhood: str | None = None):
    """Update or insert station metadata. Called on every current-conditions fetch."""
    if lat is None or lon is None:
        return
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO station_registry (station_id, name, latitude, longitude, country, neighborhood)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (station_id) DO UPDATE SET
                   latitude = EXCLUDED.latitude,
                   longitude = EXCLUDED.longitude,
                   name = COALESCE(EXCLUDED.name, station_registry.name),
                   country = COALESCE(EXCLUDED.country, station_registry.country),
                   neighborhood = COALESCE(EXCLUDED.neighborhood, station_registry.neighborhood),
                   last_seen_at = now()""",
            [station_id, name, lat, lon, country, neighborhood],
        )
    finally:
        con.close()


def get_station_registry() -> list[dict]:
    """Return all stations from the registry."""
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM station_registry ORDER BY station_id")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()
