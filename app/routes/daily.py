from flask import Blueprint, current_app, jsonify, render_template, request

from ..database import get_connection

bp = Blueprint("daily", __name__)


@bp.route("/daily")
def daily_view():
    return render_template("daily.html")


@bp.route("/api/rapid")
def api_rapid():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date parameter required"}), 400

    cfg = current_app.config["WS"]
    station_id = cfg["wu"]["station_id"]
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT observed_at, observed_at_local,
                      temp_c, heat_index_c, dew_point_c, wind_chill_c,
                      humidity_pct, pressure_hpa,
                      wind_speed_kmh, wind_gust_kmh, wind_dir_deg,
                      precip_rate_mmh, precip_total_mm,
                      solar_radiation_wm2, uv_index
               FROM rapid_observations
               WHERE station_id = ?
                 AND CAST(observed_at_local AS DATE) = ?
               ORDER BY observed_at""",
            [station_id, date_str],
        ).fetchall()

        columns = [
            "observed_at", "observed_at_local",
            "temp_c", "heat_index_c", "dew_point_c", "wind_chill_c",
            "humidity_pct", "pressure_hpa",
            "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg",
            "precip_rate_mmh", "precip_total_mm",
            "solar_radiation_wm2", "uv_index",
        ]
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()


@bp.route("/api/hourly")
def api_hourly():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date parameter required"}), 400

    cfg = current_app.config["WS"]
    station_id = cfg["wu"]["station_id"]
    con = get_connection()
    try:
        rows = con.execute(
            """SELECT observed_at, observed_at_local,
                      temp_c, heat_index_c, dew_point_c, wind_chill_c,
                      humidity_pct, pressure_hpa,
                      wind_speed_kmh, wind_gust_kmh, wind_dir_deg,
                      precip_rate_mmh, precip_total_mm,
                      solar_radiation_wm2, uv_index
               FROM hourly_observations
               WHERE station_id = ?
                 AND CAST(observed_at_local AS DATE) = ?
               ORDER BY observed_at""",
            [station_id, date_str],
        ).fetchall()

        columns = [
            "observed_at", "observed_at_local",
            "temp_c", "heat_index_c", "dew_point_c", "wind_chill_c",
            "humidity_pct", "pressure_hpa",
            "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg",
            "precip_rate_mmh", "precip_total_mm",
            "solar_radiation_wm2", "uv_index",
        ]
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()
