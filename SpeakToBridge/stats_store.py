from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class LifetimeStats:
    total_words: int = 0
    total_clips: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "LifetimeStats":
        try:
            total_words = int(data.get("total_words", 0))
        except (TypeError, ValueError):
            total_words = 0
        try:
            total_clips = int(data.get("total_clips", 0))
        except (TypeError, ValueError):
            total_clips = 0
        return cls(total_words=max(0, total_words), total_clips=max(0, total_clips))

    def to_dict(self) -> dict:
        return asdict(self)


class StatsStore:
    def __init__(self, stats_path: Path) -> None:
        self._stats_path = stats_path

    def load(self) -> LifetimeStats:
        if not self._stats_path.exists():
            return LifetimeStats()
        try:
            raw = self._stats_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return LifetimeStats()
        if not isinstance(payload, dict):
            return LifetimeStats()
        return LifetimeStats.from_dict(payload)

    def save(self, stats: LifetimeStats) -> None:
        self._stats_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(stats.to_dict(), indent=2)
        self._stats_path.write_text(payload, encoding="utf-8")
