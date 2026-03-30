import os
import shutil
import sys

import yaml

CONFIG_PATH = "config.yaml"
EXAMPLE_PATH = "config.yaml.example"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(EXAMPLE_PATH):
            shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
            print(
                f"[SETUP] {CONFIG_PATH} created from example. "
                "Please edit it with your API key and station settings, then restart.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(f"[ERROR] {CONFIG_PATH} not found and no example available.", file=sys.stderr)
            sys.exit(1)

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    if cfg["wu"]["api_key"] in ("YOUR_API_KEY", ""):
        print("[SETUP] Please set your api_key in config.yaml, then restart.", file=sys.stderr)
        sys.exit(1)

    _normalize_stations(cfg)

    return cfg


def _normalize_stations(cfg: dict):
    """Convert legacy single-station config to multi-station format in-place."""
    wu = cfg["wu"]

    if "station_id" in wu and "primary_station" not in wu:
        # Legacy format: wu.station_id as flat string
        sid = wu.pop("station_id")
        if sid in ("YOUR_STATION_ID", ""):
            print("[SETUP] Please set your station in config.yaml, then restart.", file=sys.stderr)
            sys.exit(1)
        wu["primary_station"] = {"id": sid, "name": sid}
        wu.setdefault("secondary_stations", [])
    else:
        # New format
        ps = wu.get("primary_station", {})
        if not ps.get("id") or ps["id"] in ("YOUR_STATION_ID", ""):
            print("[SETUP] Please set primary_station.id in config.yaml, then restart.", file=sys.stderr)
            sys.exit(1)
        ps.setdefault("name", ps["id"])
        wu.setdefault("secondary_stations", [])

    # Ensure every secondary station has defaults
    for s in wu["secondary_stations"]:
        s.setdefault("name", s["id"])
        s.setdefault("use_for_gap_fill", False)


def get_all_stations(cfg: dict) -> list[dict]:
    """Return list of all stations (primary first) with metadata."""
    wu = cfg["wu"]
    ps = wu["primary_station"]
    stations = [
        {"id": ps["id"], "name": ps["name"], "is_primary": True, "use_for_gap_fill": False},
    ]
    for s in wu.get("secondary_stations", []):
        stations.append({
            "id": s["id"],
            "name": s["name"],
            "is_primary": False,
            "use_for_gap_fill": s.get("use_for_gap_fill", False),
        })
    return stations


def get_station_by_id(cfg: dict, station_id: str) -> dict | None:
    """Look up a station dict by its ID. Returns None if not found."""
    for s in get_all_stations(cfg):
        if s["id"] == station_id:
            return s
    return None


def get_primary_station_id(cfg: dict) -> str:
    """Return the primary station ID."""
    return cfg["wu"]["primary_station"]["id"]
