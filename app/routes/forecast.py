from flask import Blueprint, current_app, jsonify, render_template

from ..api_client import WUClient
from ..database import get_connection

bp = Blueprint("forecast", __name__)


@bp.route("/forecast")
def forecast_view(station_id):
    return render_template("forecast.html")


@bp.route("/api/forecast")
def api_forecast(station_id):
    """Return 5-day forecast for a station based on its lat/lon from the registry."""
    cfg = current_app.config["WS"]
    client = WUClient(cfg)

    # Get coords from registry
    con = get_connection()
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT latitude, longitude FROM station_registry WHERE station_id = %s",
            [station_id],
        )
        row = cur.fetchone()
        cur.close()
    finally:
        con.close()

    if not row or row[0] is None:
        return jsonify({"error": "Station coordinates not available. Visit the dashboard first to populate them."}), 404

    data = client.get_forecast_5day(row[0], row[1])
    if data is None:
        return jsonify({"error": "Forecast data not available"}), 503

    # Reshape into a friendlier structure: array of day objects
    days = []
    num_days = len(data.get("dayOfWeek", []))
    dp = data.get("daypart", [{}])[0] if data.get("daypart") else {}

    for i in range(num_days):
        day_idx = i * 2      # daypart index for day
        night_idx = i * 2 + 1  # daypart index for night

        day = {
            "dayOfWeek": _safe(data, "dayOfWeek", i),
            "validDate": _safe(data, "validTimeLocal", i, "")[:10],
            "narrative": _safe(data, "narrative", i),
            "tempMax": _safe(data, "temperatureMax", i),
            "tempMin": _safe(data, "temperatureMin", i),
            "qpf": _safe(data, "qpf", i),
            "qpfSnow": _safe(data, "qpfSnow", i),
            "sunrise": _safe(data, "sunriseTimeLocal", i, "")[11:16],
            "sunset": _safe(data, "sunsetTimeLocal", i, "")[11:16],
            "moonPhase": _safe(data, "moonPhase", i),
            "day": {
                "name": _safe(dp, "daypartName", day_idx),
                "narrative": _safe(dp, "narrative", day_idx),
                "wxPhrase": _safe(dp, "wxPhraseLong", day_idx),
                "iconCode": _safe(dp, "iconCode", day_idx),
                "temp": _safe(dp, "temperature", day_idx),
                "windChill": _safe(dp, "temperatureWindChill", day_idx),
                "heatIndex": _safe(dp, "temperatureHeatIndex", day_idx),
                "humidity": _safe(dp, "relativeHumidity", day_idx),
                "cloudCover": _safe(dp, "cloudCover", day_idx),
                "windSpeed": _safe(dp, "windSpeed", day_idx),
                "windDir": _safe(dp, "windDirectionCardinal", day_idx),
                "windDeg": _safe(dp, "windDirection", day_idx),
                "precipChance": _safe(dp, "precipChance", day_idx),
                "precipType": _safe(dp, "precipType", day_idx),
                "uvIndex": _safe(dp, "uvIndex", day_idx),
                "uvDesc": _safe(dp, "uvDescription", day_idx),
                "thunderIndex": _safe(dp, "thunderIndex", day_idx),
            },
            "night": {
                "name": _safe(dp, "daypartName", night_idx),
                "narrative": _safe(dp, "narrative", night_idx),
                "wxPhrase": _safe(dp, "wxPhraseLong", night_idx),
                "iconCode": _safe(dp, "iconCode", night_idx),
                "temp": _safe(dp, "temperature", night_idx),
                "windChill": _safe(dp, "temperatureWindChill", night_idx),
                "humidity": _safe(dp, "relativeHumidity", night_idx),
                "cloudCover": _safe(dp, "cloudCover", night_idx),
                "windSpeed": _safe(dp, "windSpeed", night_idx),
                "windDir": _safe(dp, "windDirectionCardinal", night_idx),
                "windDeg": _safe(dp, "windDirection", night_idx),
                "precipChance": _safe(dp, "precipChance", night_idx),
                "precipType": _safe(dp, "precipType", night_idx),
                "thunderIndex": _safe(dp, "thunderIndex", night_idx),
            },
        }
        days.append(day)

    return jsonify(days)


def _safe(data: dict, key: str, idx: int, default=None):
    """Safely get index from a list inside a dict."""
    lst = data.get(key)
    if isinstance(lst, list) and idx < len(lst):
        return lst[idx]
    return default
