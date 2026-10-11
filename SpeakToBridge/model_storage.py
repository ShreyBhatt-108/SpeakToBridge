from __future__ import annotations

import shutil
import json
from dataclasses import dataclass
from pathlib import Path

MODEL_CACHE_PREFIX = "models--Systran--faster-whisper-"
AMD_MODEL_CACHE_PREFIX = "models--openai--whisper-"
REQUIRED_MODEL_FILES = frozenset({"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"})


@dataclass
class CachedModelInfo:
    model_name: str
    folder_name: str
    size_bytes: int
    ready: bool
    backend: str = "CPU/NVIDIA"


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
        prefix = next((p for p in (MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX) if entry.name.startswith(p)), None)
        if prefix is None:
            continue
        model_name = entry.name[len(prefix) :]
        size_bytes = _folder_size(entry)
        ready = is_model_cache_ready(entry)
        results.append(
            CachedModelInfo(
                model_name=model_name,
                folder_name=entry.name,
                size_bytes=size_bytes,
                ready=ready,
                backend="AMD ROCm" if prefix == AMD_MODEL_CACHE_PREFIX else "CPU/NVIDIA",
            )
        )
    return sorted(results, key=lambda item: item.model_name)


def delete_cached_model(model_cache_dir: Path, folder_name: str) -> bool:
    if Path(folder_name).name != folder_name or not folder_name.startswith((MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX)):
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
                if snapshot.is_dir() and _snapshot_ready(snapshot, model_folder.name.startswith(AMD_MODEL_CACHE_PREFIX)):
                    return True
            return False
        return _snapshot_ready(model_folder, model_folder.name.startswith(AMD_MODEL_CACHE_PREFIX))
    except OSError:
        return False


def _snapshot_ready(folder: Path, amd: bool) -> bool:
    present = {child.name for child in folder.iterdir() if child.is_file() and child.stat().st_size > 0}
    if not amd:
        return REQUIRED_MODEL_FILES.issubset(present)
    required = {"config.json", "generation_config.json", "preprocessor_config.json", "tokenizer_config.json"}
    if not required.issubset(present) or not ("tokenizer.json" in present or {"vocab.json", "merges.txt"}.issubset(present)):
        return False
    if "model.safetensors" in present:
        return True
    if "model.safetensors.index.json" in present:
        try:
            index = json.loads((folder / "model.safetensors.index.json").read_text(encoding="utf-8"))
            shards = set(index["weight_map"].values())
            return bool(shards) and shards.issubset(present)
        except (ValueError, KeyError, TypeError):
            return False
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
