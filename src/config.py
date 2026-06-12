"""
Loads config/conf/{ENV}/config.json where ENV defaults to 'dev'.
Set the TTB_ENV environment variable to switch environments.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENV = os.environ.get("TTB_ENV", "dev")
_config: dict = None


def load() -> dict:
    global _config
    if _config is None:
        path = ROOT / "conf" / ENV / "config.json"
        if not path.is_file():
            raise FileNotFoundError(f"Config not found for environment '{ENV}': {path}")
        with open(path) as f:
            _config = json.load(f)
        print(f"[config] Loaded '{ENV}' configuration from {path}")
    return _config


def get(key: str, default=None):
    return load().get(key, default)
