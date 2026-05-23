from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import (
    DEFAULT_ACTIVATION_HOTKEY,
    DEFAULT_READ_HOTKEY,
    DEFAULT_DICTIONARY_ENABLED,
    DEFAULT_INSERT_MODE,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DEFAULT_PRIVACY_MODE,
    DEFAULT_RUNTIME_MODE,
    DEFAULT_VAD_MODE,
)


@dataclass
class AppConfig:
    model_name: str = DEFAULT_MODEL
    language: str = DEFAULT_LANGUAGE
    insert_mode: str = DEFAULT_INSERT_MODE
    runtime_mode: str = DEFAULT_RUNTIME_MODE
    privacy_mode: str = DEFAULT_PRIVACY_MODE
    dictionary_enabled: bool = DEFAULT_DICTIONARY_ENABLED
    activation_hotkey: str = DEFAULT_ACTIVATION_HOTKEY
    read_hotkey: str = DEFAULT_READ_HOTKEY
    vad_mode: str = DEFAULT_VAD_MODE

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        default = cls()
        return cls(
            model_name=str(data.get("model_name", default.model_name)),
            language=str(data.get("language", default.language)),
            insert_mode=str(data.get("insert_mode", default.insert_mode)),
            runtime_mode=str(data.get("runtime_mode", default.runtime_mode)),
            privacy_mode=str(data.get("privacy_mode", default.privacy_mode)),
            dictionary_enabled=bool(data.get("dictionary_enabled", default.dictionary_enabled)),
            activation_hotkey=str(data.get("activation_hotkey", default.activation_hotkey)),
            read_hotkey=str(data.get("read_hotkey", default.read_hotkey)),
            vad_mode=str(data.get("vad_mode", default.vad_mode)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


class ConfigStore:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def load(self) -> AppConfig:
        if not self._config_path.exists():
            return AppConfig()
        try:
            raw = self._config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return AppConfig()
        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config.to_dict(), indent=2)
        self._config_path.write_text(payload, encoding="utf-8")
