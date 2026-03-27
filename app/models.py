"""Mapping from Weather Underground API JSON fields to database columns."""


def _get(obs: dict, *keys, default=None):
    """Try multiple keys in order, return first non-None value."""
    for key in keys:
        parts = key.split(".")
        val = obs
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break
        if val is not None:
            return val
    return default


def map_rapid_observation(obs: dict, station_id: str) -> dict:
    metric = obs.get("metric", {}) or {}
    return {
        "station_id": station_id,
        "observed_at": obs.get("obsTimeUtc"),
        "observed_at_local": obs.get("obsTimeLocal"),
        "temp_c": _get(obs, "metric.tempAvg", "metric.temp"),
        "heat_index_c": _get(obs, "metric.heatindexAvg", "metric.heatindex"),
        "dew_point_c": _get(obs, "metric.dewptAvg", "metric.dewpt"),
        "wind_chill_c": _get(obs, "metric.windchillAvg", "metric.windchill"),
        "humidity_pct": _get(obs, "humidityAvg", "humidity"),
        "pressure_hpa": _get(obs, "metric.pressureMax", "metric.pressure"),
        "wind_speed_kmh": _get(obs, "metric.windspeedAvg", "metric.windspeed"),
        "wind_gust_kmh": _get(obs, "metric.windgustAvg", "metric.windgust"),
        "wind_dir_deg": _get(obs, "winddirAvg", "winddir"),
        "precip_rate_mmh": _get(obs, "metric.precipRate"),
        "precip_total_mm": _get(obs, "metric.precipTotal"),
        "solar_radiation_wm2": _get(obs, "solarRadiationHigh", "solarRadiation"),
        "uv_index": _get(obs, "uvHigh", "uv"),
    }


# Hourly observations share the same JSON structure as rapid
map_hourly_observation = map_rapid_observation


def map_daily_observation(obs: dict, station_id: str, obs_date) -> dict:
    return {
        "station_id": station_id,
        "obs_date": obs_date,
        "temp_avg_c": _get(obs, "metric.tempAvg"),
        "temp_high_c": _get(obs, "metric.tempHigh"),
        "temp_low_c": _get(obs, "metric.tempLow"),
        "humidity_avg_pct": _get(obs, "humidityAvg"),
        "humidity_high_pct": _get(obs, "humidityHigh"),
        "humidity_low_pct": _get(obs, "humidityLow"),
        "dew_point_avg_c": _get(obs, "metric.dewptAvg"),
        "dew_point_high_c": _get(obs, "metric.dewptHigh"),
        "dew_point_low_c": _get(obs, "metric.dewptLow"),
        "pressure_avg_hpa": _get(obs, "metric.pressureAvg"),
        "pressure_max_hpa": _get(obs, "metric.pressureMax"),
        "pressure_min_hpa": _get(obs, "metric.pressureMin"),
        "wind_speed_avg_kmh": _get(obs, "metric.windspeedAvg"),
        "wind_speed_high_kmh": _get(obs, "metric.windspeedHigh"),
        "wind_gust_high_kmh": _get(obs, "metric.windgustHigh"),
        "precip_total_mm": _get(obs, "metric.precipTotal"),
    }


def map_current_conditions(obs: dict) -> dict:
    metric = obs.get("metric", {}) or {}
    return {
        "temp_c": metric.get("temp"),
        "heat_index_c": metric.get("heatIndex"),
        "dew_point_c": metric.get("dewpt"),
        "wind_chill_c": metric.get("windChill"),
        "humidity_pct": obs.get("humidity"),
        "pressure_hpa": metric.get("pressure"),
        "wind_speed_kmh": metric.get("windSpeed"),
        "wind_gust_kmh": metric.get("windGust"),
        "wind_dir_deg": obs.get("winddir"),
        "precip_rate_mmh": metric.get("precipRate"),
        "precip_total_mm": metric.get("precipTotal"),
        "solar_radiation_wm2": obs.get("solarRadiation"),
        "uv_index": obs.get("uv"),
        "observed_at": obs.get("obsTimeUtc"),
        "observed_at_local": obs.get("obsTimeLocal"),
        "station_id": obs.get("stationID"),
        "neighborhood": obs.get("neighborhood"),
        "country": obs.get("country"),
    }
