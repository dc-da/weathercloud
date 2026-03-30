from flask import Blueprint, jsonify, render_template, request

from ..database import get_connection

bp = Blueprint("reports", __name__)


@bp.route("/reports")
def reports_view(station_id):
    return render_template("reports.html")


@bp.route("/api/report/daily-stats")
def api_daily_stats(station_id):
    source = request.args.get("source", "rapid")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if not date_from or not date_to:
        return jsonify({"error": "from and to parameters required"}), 400

    table = "rapid_observations" if source == "rapid" else "hourly_observations"
    con = get_connection()
    try:
        rows = con.execute(
            f"""SELECT CAST(observed_at_local AS DATE) AS obs_date,
                       AVG(temp_c) AS temp_avg,
                       MIN(temp_c) AS temp_min,
                       MAX(temp_c) AS temp_max,
                       AVG(humidity_pct) AS humidity_avg,
                       MIN(humidity_pct) AS humidity_min,
                       MAX(humidity_pct) AS humidity_max,
                       AVG(pressure_hpa) AS pressure_avg,
                       AVG(wind_speed_kmh) AS wind_avg,
                       MAX(wind_gust_kmh) AS wind_gust_max,
                       SUM(CASE WHEN precip_rate_mmh > 0 THEN precip_rate_mmh ELSE 0 END) AS precip_sum,
                       MAX(precip_total_mm) AS precip_total_max,
                       AVG(solar_radiation_wm2) AS solar_avg,
                       MAX(uv_index) AS uv_max
                FROM {table}
                WHERE station_id = ?
                  AND CAST(observed_at_local AS DATE) >= ?
                  AND CAST(observed_at_local AS DATE) <= ?
                GROUP BY CAST(observed_at_local AS DATE)
                ORDER BY obs_date""",
            [station_id, date_from, date_to],
        ).fetchall()

        columns = [
            "obs_date", "temp_avg", "temp_min", "temp_max",
            "humidity_avg", "humidity_min", "humidity_max",
            "pressure_avg", "wind_avg", "wind_gust_max",
            "precip_sum", "precip_total_max", "solar_avg", "uv_max",
        ]
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in rows]
        return jsonify(data)
    finally:
        con.close()


@bp.route("/api/report/comparison")
def api_comparison(station_id):
    source = request.args.get("source", "rapid")
    metric = request.args.get("metric", "temp_c")
    a_from = request.args.get("a_from")
    a_to = request.args.get("a_to")
    b_from = request.args.get("b_from")
    b_to = request.args.get("b_to")

    if not all([a_from, a_to, b_from, b_to]):
        return jsonify({"error": "a_from, a_to, b_from, b_to parameters required"}), 400

    allowed_metrics = [
        "temp_c", "humidity_pct", "pressure_hpa", "wind_speed_kmh",
        "wind_gust_kmh", "precip_rate_mmh", "precip_total_mm",
        "solar_radiation_wm2", "uv_index", "dew_point_c",
    ]
    if metric not in allowed_metrics:
        return jsonify({"error": f"Invalid metric. Allowed: {allowed_metrics}"}), 400

    table = "rapid_observations" if source == "rapid" else "hourly_observations"
    con = get_connection()
    try:
        def _fetch_period(dfrom, dto):
            rows = con.execute(
                f"""SELECT CAST(observed_at_local AS DATE) AS obs_date,
                           AVG({metric}) AS avg_val,
                           MIN({metric}) AS min_val,
                           MAX({metric}) AS max_val
                    FROM {table}
                    WHERE station_id = ?
                      AND CAST(observed_at_local AS DATE) >= ?
                      AND CAST(observed_at_local AS DATE) <= ?
                    GROUP BY CAST(observed_at_local AS DATE)
                    ORDER BY obs_date""",
                [station_id, dfrom, dto],
            ).fetchall()
            return [
                {"obs_date": str(r[0]), "avg": r[1], "min": r[2], "max": r[3]}
                for r in rows
            ]

        def _summary(dfrom, dto):
            row = con.execute(
                f"""SELECT AVG({metric}), MIN({metric}), MAX({metric}),
                           STDDEV({metric})
                    FROM {table}
                    WHERE station_id = ?
                      AND CAST(observed_at_local AS DATE) >= ?
                      AND CAST(observed_at_local AS DATE) <= ?""",
                [station_id, dfrom, dto],
            ).fetchone()
            return {"avg": row[0], "min": row[1], "max": row[2], "stddev": row[3]}

        return jsonify({
            "metric": metric,
            "period_a": {"data": _fetch_period(a_from, a_to), "summary": _summary(a_from, a_to)},
            "period_b": {"data": _fetch_period(b_from, b_to), "summary": _summary(b_from, b_to)},
        })
    finally:
        con.close()


@bp.route("/api/report/heatmap")
def api_heatmap(station_id):
    source = request.args.get("source", "rapid")
    metric = request.args.get("metric", "temp_c")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    if not date_from or not date_to:
        return jsonify({"error": "from and to parameters required"}), 400

    allowed_metrics = [
        "temp_c", "humidity_pct", "pressure_hpa", "wind_speed_kmh",
        "wind_gust_kmh", "precip_rate_mmh", "solar_radiation_wm2", "uv_index",
        "dew_point_c",
    ]
    if metric not in allowed_metrics:
        return jsonify({"error": f"Invalid metric. Allowed: {allowed_metrics}"}), 400

    table = "rapid_observations" if source == "rapid" else "hourly_observations"
    con = get_connection()
    try:
        rows = con.execute(
            f"""SELECT CAST(observed_at_local AS DATE) AS obs_date,
                       EXTRACT(HOUR FROM observed_at_local) AS hour,
                       AVG({metric}) AS avg_val
                FROM {table}
                WHERE station_id = ?
                  AND CAST(observed_at_local AS DATE) >= ?
                  AND CAST(observed_at_local AS DATE) <= ?
                GROUP BY CAST(observed_at_local AS DATE),
                         EXTRACT(HOUR FROM observed_at_local)
                ORDER BY obs_date, hour""",
            [station_id, date_from, date_to],
        ).fetchall()

        data = [
            {"date": str(r[0]), "hour": int(r[1]), "value": r[2]}
            for r in rows
        ]
        return jsonify({"metric": metric, "data": data})
    finally:
        con.close()
