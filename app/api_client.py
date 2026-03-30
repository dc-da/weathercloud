import logging
import time

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class WUClient:
    def __init__(self, cfg: dict):
        self.api_key = cfg["wu"]["api_key"]
        self.units = cfg["wu"].get("units", "m")
        self.urls = cfg["api"]

    def _common_params(self, station_id: str) -> dict:
        return {
            "stationId": station_id,
            "apiKey": self.api_key,
            "units": self.units,
            "format": "json",
        }

    def _request(self, url: str, station_id: str, extra_params: dict | None = None) -> dict | None:
        params = self._common_params(station_id)
        if extra_params:
            params.update(extra_params)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(url, params=params, timeout=TIMEOUT)

                if resp.status_code == 204 or not resp.content:
                    logger.info("No data returned (HTTP %s) from %s", resp.status_code, url)
                    return None

                if resp.status_code == 401:
                    logger.error("Invalid API key (HTTP 401)")
                    return None

                if resp.status_code == 429:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning("Rate limited, waiting %ss (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.Timeout:
                logger.warning("Timeout on attempt %d/%d for %s", attempt, MAX_RETRIES, url)
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_BASE ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error("Request error on attempt %d/%d: %s", attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_BASE ** attempt)

        logger.error("All %d attempts failed for %s", MAX_RETRIES, url)
        return None

    def get_current_conditions(self, station_id: str) -> dict | None:
        data = self._request(self.urls["current_conditions"], station_id)
        if data and "observations" in data and data["observations"]:
            return data["observations"][0]
        return None

    def get_rapid_history_1day(self, station_id: str) -> list[dict]:
        data = self._request(self.urls["rapid_history_1day"], station_id)
        if data and "observations" in data:
            return data["observations"]
        return []

    def get_hourly_history_7day(self, station_id: str) -> list[dict]:
        data = self._request(self.urls["hourly_history_7day"], station_id)
        if data and "observations" in data:
            return data["observations"]
        return []

    def get_historical_daily(self, station_id: str, date_str: str) -> dict | None:
        """Fetch daily summary for a specific date (YYYYMMDD format)."""
        data = self._request(self.urls["historical"], station_id, extra_params={"date": date_str})
        if data and "observations" in data and data["observations"]:
            return data["observations"][0]
        return None

    def has_data_on_date(self, station_id: str, dt) -> bool:
        """Check whether the station has any data for a given date."""
        obs = self.get_historical_daily(station_id, dt.strftime("%Y%m%d"))
        return obs is not None
