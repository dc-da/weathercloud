from flask import Blueprint, jsonify, render_template, request

from ..database import get_connection

bp = Blueprint("historical", __name__)


@bp.route("/historical")
def historical_view(station_id):
    return render_template("historical.html")


@bp.route("/api/daily")
def api_daily(station_id):
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if not date_from or not date_to:
        return jsonify({"error": "from and to parameters required"}), 400

    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            """SELECT obs_date,
                      temp_avg_c, temp_high_c, temp_low_c,
                      humidity_avg_pct, humidity_high_pct, humidity_low_pct,
                      dew_point_avg_c, dew_point_high_c, dew_point_low_c,
                      pressure_avg_hpa, pressure_max_hpa, pressure_min_hpa,
                      wind_speed_avg_kmh, wind_speed_high_kmh, wind_gust_high_kmh,
                      precip_total_mm,
                      COALESCE(data_source, 'station') AS data_source
               FROM daily_observations
               WHERE station_id = %s
                 AND obs_date >= %s
                 AND obs_date <= %s
               ORDER BY obs_date""",
            [station_id, date_from, date_to],
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
        cur.close()
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()
