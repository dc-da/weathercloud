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
                "Please edit it with your API key and station ID, then restart.",
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
    if cfg["wu"]["station_id"] in ("YOUR_STATION_ID", ""):
        print("[SETUP] Please set your station_id in config.yaml, then restart.", file=sys.stderr)
        sys.exit(1)

    return cfg
