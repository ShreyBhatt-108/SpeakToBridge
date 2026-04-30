from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

MODEL_CACHE_PREFIX = "models--Systran--faster-whisper-"
REQUIRED_MODEL_FILES = frozenset({"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"})


@dataclass
class CachedModelInfo:
    model_name: str
    folder_name: str
    size_bytes: int
    ready: bool


def list_cached_models(model_cache_dir: Path) -> list[CachedModelInfo]:
    if not model_cache_dir.exists():
        return []
    results: list[CachedModelInfo] = []
    try:
        entries = list(model_cache_dir.iterdir())
    except OSError:
        return []
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        if not entry.name.startswith(MODEL_CACHE_PREFIX):
            continue
        model_name = entry.name[len(MODEL_CACHE_PREFIX) :]
        size_bytes = _folder_size(entry)
        ready = is_model_cache_ready(entry)
        results.append(
            CachedModelInfo(
                model_name=model_name,
                folder_name=entry.name,
                size_bytes=size_bytes,
                ready=ready,
            )
        )
    return sorted(results, key=lambda item: item.model_name)


def delete_cached_model(model_cache_dir: Path, folder_name: str) -> bool:
    if Path(folder_name).name != folder_name or not folder_name.startswith(MODEL_CACHE_PREFIX):
        raise ValueError("Unsafe cached model folder name.")
    base = model_cache_dir.resolve(strict=False)
    target = (base / folder_name).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Cached model folder is outside the model cache directory.") from exc
    if not target.exists() or not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def is_model_cache_ready(model_folder: Path) -> bool:
    if not model_folder.exists() or not model_folder.is_dir():
        return False
    snapshots = model_folder / "snapshots"
    try:
        if snapshots.exists():
            for snapshot in snapshots.iterdir():
                if snapshot.is_dir() and REQUIRED_MODEL_FILES.issubset({child.name for child in snapshot.iterdir()}):
                    return True
            return False
        return REQUIRED_MODEL_FILES.issubset({child.name for child in model_folder.iterdir()})
    except OSError:
        return False


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size_bytes} B"


def _folder_size(path: Path) -> int:
    total = 0
    try:
        children = path.rglob("*")
        for child in children:
            try:
                if child.is_file():
                    total += child.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total
