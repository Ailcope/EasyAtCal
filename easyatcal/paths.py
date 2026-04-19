from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

APP = "easyatcal"


def config_path() -> Path:
    return Path(user_config_dir(APP)) / "config.yaml"


def state_path() -> Path:
    return Path(user_data_dir(APP)) / "state.json"


def token_cache_path() -> Path:
    return Path(user_cache_dir(APP)) / "token.json"


def log_path() -> Path:
    return Path(user_data_dir(APP)) / "logs" / "eaw-sync.log"
