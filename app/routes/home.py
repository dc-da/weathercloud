from flask import Blueprint, current_app, jsonify, render_template

from ..api_client import WUClient
from ..config import get_all_stations, get_primary_station_id
from ..database import get_connection, upsert_station_registry
from ..models import map_current_conditions
from ..sync.gap_fill import haversine_km

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

    # Get primary coords from registry for distance calculation
    primary_coords = _get_station_coords(primary_id)

    results = []
    for s in stations:
        obs = client.get_current_conditions(s["id"])
        conditions = map_current_conditions(obs) if obs else None

        # Populate station registry with lat/lon from API response
        if conditions and conditions.get("lat") is not None:
            upsert_station_registry(
                station_id=s["id"],
                lat=conditions["lat"],
                lon=conditions["lon"],
                name=s["name"],
                country=conditions.get("country"),
                neighborhood=conditions.get("neighborhood"),
            )

        # Calculate distance from primary
        distance_km = None
        if primary_coords and conditions and conditions.get("lat") is not None:
            distance_km = round(haversine_km(
                primary_coords[0], primary_coords[1],
                conditions["lat"], conditions["lon"],
            ), 1)
        elif primary_coords:
            # Try registry for stations without current conditions
            coords = _get_station_coords(s["id"])
            if coords:
                distance_km = round(haversine_km(
                    primary_coords[0], primary_coords[1], coords[0], coords[1],
                ), 1)

        results.append({
            "station_id": s["id"],
            "name": s["name"],
            "is_primary": s["is_primary"],
            "distance_km": distance_km,
            "conditions": conditions,
        })

    return jsonify(results)


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
