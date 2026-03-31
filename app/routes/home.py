import json
import time

from flask import Blueprint, Response, current_app, jsonify, render_template

from ..api_client import WUClient
from ..config import get_all_stations, get_primary_station_id
from ..database import get_connection, upsert_station_registry
from ..models import map_current_conditions
from ..sync.gap_fill import haversine_km

INTER_STATION_DELAY = 5  # seconds between API calls to avoid rate limits

bp = Blueprint("home", __name__)


@bp.route("/")
def home_view():
    return render_template("home.html")


@bp.route("/api/stations/current")
def api_stations_current():
    """Return current conditions for all configured stations, with distance from primary."""
    cfg = current_app.config["WS"]
    client = WUClient(cfg)
    stations = get_all_stations(cfg)
    primary_id = get_primary_station_id(cfg)
    primary_coords = _get_station_coords(primary_id)

    results = []
    for i, s in enumerate(stations):
        if i > 0:
            time.sleep(INTER_STATION_DELAY)
        result = _fetch_station(client, s, primary_id, primary_coords)
        results.append(result)

    return jsonify(results)


@bp.route("/api/stations/stream")
def api_stations_stream():
    """SSE endpoint: stream each station's data as it becomes available."""
    cfg = current_app.config["WS"]
    stations = get_all_stations(cfg)
    primary_id = get_primary_station_id(cfg)

    def generate():
        client = WUClient(cfg)
        primary_coords = _get_station_coords(primary_id)
        total = len(stations)

        for i, s in enumerate(stations):
            if i > 0:
                time.sleep(INTER_STATION_DELAY)
            result = _fetch_station(client, s, primary_id, primary_coords)
            event_data = json.dumps({
                "index": i,
                "total": total,
                "station": result,
            })
            yield f"data: {event_data}\n\n"

        yield "event: done\ndata: {}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _fetch_station(client, station_cfg, primary_id, primary_coords):
    """Fetch current conditions for a single station and return a result dict."""
    obs = client.get_current_conditions(station_cfg["id"])
    conditions = map_current_conditions(obs) if obs else None

    if conditions and conditions.get("lat") is not None:
        upsert_station_registry(
            station_id=station_cfg["id"],
            lat=conditions["lat"],
            lon=conditions["lon"],
            name=station_cfg["name"],
            country=conditions.get("country"),
            neighborhood=conditions.get("neighborhood"),
        )

    distance_km = None
    if primary_coords and conditions and conditions.get("lat") is not None:
        distance_km = round(haversine_km(
            primary_coords[0], primary_coords[1],
            conditions["lat"], conditions["lon"],
        ), 1)
    elif primary_coords:
        coords = _get_station_coords(station_cfg["id"])
        if coords:
            distance_km = round(haversine_km(
                primary_coords[0], primary_coords[1], coords[0], coords[1],
            ), 1)

    return {
        "station_id": station_cfg["id"],
        "name": station_cfg["name"],
        "is_primary": station_cfg["is_primary"],
        "distance_km": distance_km,
        "conditions": conditions,
    }


def _get_station_coords(station_id: str) -> tuple[float, float] | None:
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT latitude, longitude FROM station_registry WHERE station_id = %s",
            [station_id],
        )
        row = cur.fetchone()
        cur.close()
        if row and row[0] is not None:
            return (row[0], row[1])
        return None
    except Exception:
        return None
    finally:
        con.close()
