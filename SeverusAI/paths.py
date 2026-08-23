from __future__ import annotations

import os
from pathlib import Path

from .constants import APP_ORG


def get_app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    app_dir = base / APP_ORG
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"


def get_model_cache_dir() -> Path:
    model_dir = get_app_data_dir() / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def get_word_bank_path() -> Path:
    return get_app_data_dir() / "word_bank.txt"


def get_log_dir() -> Path:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_stats_path() -> Path:
    return get_app_data_dir() / "stats.json"
