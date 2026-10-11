from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import (
    DEFAULT_ACTIVATION_HOTKEY,
    DEFAULT_MAX_RECORDING_SECONDS,
    DEFAULT_READ_HOTKEY,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DEFAULT_RUNTIME_MODE,
    DEFAULT_VAD_MODE,
    MAX_MAX_RECORDING_SECONDS,
    MIN_MAX_RECORDING_SECONDS,
    MODEL_CHOICES,
)


ALLOWED_MODELS = frozenset(MODEL_CHOICES.values())
ALLOWED_LANGUAGES = frozenset({"en"})
ALLOWED_RUNTIME_MODES = frozenset({"cpu", "cpu_auto_gpu", "amd_gpu"})
ALLOWED_VAD_MODES = frozenset({"off", "fast", "pause_preserving", "accuracy"})


def _validated_string(value: object, default: str, allowed: frozenset[str]) -> str:
    candidate = str(value)
    return candidate if candidate in allowed else default


def _validated_recording_limit(value: object, default: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_MAX_RECORDING_SECONDS, min(MAX_MAX_RECORDING_SECONDS, candidate))


def _validated_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


@dataclass
class AppConfig:
    model_name: str = DEFAULT_MODEL
    language: str = DEFAULT_LANGUAGE
    runtime_mode: str = DEFAULT_RUNTIME_MODE
    activation_hotkey: str = DEFAULT_ACTIVATION_HOTKEY
    read_hotkey: str = DEFAULT_READ_HOTKEY
    vad_mode: str = DEFAULT_VAD_MODE
    max_recording_seconds: int = DEFAULT_MAX_RECORDING_SECONDS
    sound_effects_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        default = cls()
        if not isinstance(data, dict):
            return default
        return cls(
            model_name=_validated_string(data.get("model_name"), default.model_name, ALLOWED_MODELS),
            language=_validated_string(data.get("language"), default.language, ALLOWED_LANGUAGES),
            runtime_mode=_validated_string(
                data.get("runtime_mode"), default.runtime_mode, ALLOWED_RUNTIME_MODES
            ),
            activation_hotkey=str(data.get("activation_hotkey", default.activation_hotkey)),
            read_hotkey=str(data.get("read_hotkey", default.read_hotkey)),
            vad_mode=_validated_string(data.get("vad_mode"), default.vad_mode, ALLOWED_VAD_MODES),
            max_recording_seconds=_validated_recording_limit(
                data.get("max_recording_seconds"), default.max_recording_seconds
            ),
            sound_effects_enabled=_validated_bool(
                data.get("sound_effects_enabled"), default.sound_effects_enabled
            ),
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
