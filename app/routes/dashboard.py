from flask import Blueprint, current_app, jsonify, render_template

from ..api_client import WUClient
from ..database import get_connection
from ..models import map_current_conditions

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
def dashboard_view():
    return render_template("dashboard.html")


@bp.route("/api/current")
def api_current():
    cfg = current_app.config["WS"]
    client = WUClient(cfg)
    obs = client.get_current_conditions()
    if obs is None:
        return jsonify({"error": "No data available"}), 503
    return jsonify(map_current_conditions(obs))


@bp.route("/api/rapid/last24h")
def api_rapid_last24h():
    """Return rapid observations for the last 24 hours (for dashboard sparkline)."""
    cfg = current_app.config["WS"]
    station_id = cfg["wu"]["station_id"]
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT observed_at_local, temp_c, humidity_pct
               FROM rapid_observations
               WHERE station_id = ?
                 AND observed_at >= now() - INTERVAL '24 hours'
               ORDER BY observed_at""",
            [station_id],
        ).fetchall()
        data = [
            {"time": str(r[0]), "temp_c": r[1], "humidity_pct": r[2]}
            for r in rows
        ]
        return jsonify(data)
    finally:
        con.close()
