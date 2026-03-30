from flask import Blueprint, current_app, jsonify, render_template

from ..api_client import WUClient
from ..config import get_all_stations
from ..models import map_current_conditions

bp = Blueprint("home", __name__)


@bp.route("/")
def home_view():
    return render_template("home.html")


@bp.route("/api/stations/current")
def api_stations_current():
    """Return current conditions for all configured stations."""
    cfg = current_app.config["WS"]
    client = WUClient(cfg)
    stations = get_all_stations(cfg)

    results = []
    for s in stations:
        obs = client.get_current_conditions(s["id"])
        conditions = map_current_conditions(obs) if obs else None
        results.append({
            "station_id": s["id"],
            "name": s["name"],
            "is_primary": s["is_primary"],
            "conditions": conditions,
        })

    return jsonify(results)
