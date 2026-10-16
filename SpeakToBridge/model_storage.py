from __future__ import annotations

import shutil
import json
import os
import tempfile
import re
import stat
from dataclasses import dataclass
from pathlib import Path

MODEL_CACHE_PREFIX = "models--Systran--faster-whisper-"
SHARED_AMD_MODEL_CACHE_PREFIX = "openai-whisper-"
AMD_MODEL_CACHE_PREFIX = "models--openai--whisper-"
WSL_MODEL_CACHE_PREFIX = "wsl--openai-whisper-"
WSL_MANIFEST_NAME = ".wsl-models.json"
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
        prefix = next((p for p in (MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX) if entry.name.startswith(p)), None)
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
                backend="AMD ROCm" if prefix in (AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX) else "CPU/NVIDIA",
            )
        )
    for item in _read_wsl_manifest(model_cache_dir):
        try:
            if item["model_name"] not in ("tiny", "base", "small", "medium", "large-v3"):
                continue
            results.append(CachedModelInfo(item["model_name"], WSL_MODEL_CACHE_PREFIX + item["model_name"],
                                           int(item["size_bytes"]), item.get("ready") is True, "AMD ROCm (WSL)"))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(results, key=lambda item: item.model_name)


def cached_model_name(folder_name: str) -> str:
    if not isinstance(folder_name, str):
        raise ValueError("Invalid model folder")
    for prefix in (MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX, WSL_MODEL_CACHE_PREFIX):
        if folder_name.startswith(prefix):
            name = folder_name[len(prefix):]
            if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
                return name
    raise ValueError("Invalid model folder")


def delete_cached_model(model_cache_dir: Path, folder_name: str) -> bool:
    cached_model_name(folder_name)
    if folder_name.startswith(WSL_MODEL_CACHE_PREFIX):
        name = folder_name[len(WSL_MODEL_CACHE_PREFIX):]
        if name not in ("tiny", "base", "small", "medium", "large-v3"):
            raise ValueError("Unsafe WSL model name")
        from .wsl_whisper import worker_command
        import subprocess
        result = subprocess.run(worker_command(model_cache_dir, None)[:-1] + ["--delete-model", name],
                                capture_output=True, text=True, encoding="utf-8", timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        try:
            reply = json.loads(result.stdout.strip().splitlines()[-1])
            if reply.get("deleted") != name:
                raise ValueError("Unexpected deletion response")
        except (ValueError, IndexError, AttributeError) as exc:
            raise RuntimeError("WSL did not confirm model deletion") from exc
        entries = [item for item in _read_wsl_manifest(model_cache_dir) if item.get("model_name") != name]
        _write_wsl_manifest(model_cache_dir, entries)
        return reply.get("removed", True) is True
    if Path(folder_name).name != folder_name or not folder_name.startswith((MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX)):
        raise ValueError("Unsafe cached model folder name.")
    base = model_cache_dir.resolve(strict=False)
    candidate = base / folder_name
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        raise ValueError("Model folder links cannot be deleted")
    target = candidate.resolve(strict=False)
    if target.parent != base:
        raise ValueError("Model folder is outside the cache")
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
                if snapshot.is_dir() and _snapshot_ready(snapshot, model_folder.name.startswith((AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX))):
                    return True
            return False
        return _snapshot_ready(model_folder, model_folder.name.startswith((AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX)))
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


def _read_wsl_manifest(cache_dir: Path) -> list:
    try:
        value = json.loads((cache_dir / WSL_MANIFEST_NAME).read_text(encoding="utf-8"))
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    except (OSError, ValueError):
        return []


def _write_wsl_manifest(cache_dir: Path, entries: list) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache_dir, delete=False) as f:
        json.dump(entries, f)
        temp = Path(f.name)
    try:
        temp.replace(cache_dir / WSL_MANIFEST_NAME)
    finally:
        temp.unlink(missing_ok=True)


def record_wsl_cached_model(cache_dir: Path, item: dict) -> None:
    entries = [entry for entry in _read_wsl_manifest(cache_dir)
               if entry.get("model_name") != item["model_name"]]
    entries.append(item)
    _write_wsl_manifest(cache_dir, entries)


def find_cached_amd_model(cache_dir: Path, model_name: str) -> Path | None:
    shared = cache_dir / (SHARED_AMD_MODEL_CACHE_PREFIX + model_name)
    if (shared / ".speak_to_bridge_ready").is_file() and is_model_cache_ready(shared):
        return shared
    legacy = cache_dir / (AMD_MODEL_CACHE_PREFIX + model_name)
    snapshots = legacy / "snapshots"
    try:
        if not snapshots.is_dir():
            return None
        candidates = list(snapshots.iterdir())
        reference = legacy / "refs" / "main"
        if reference.is_file():
            revision = reference.read_text(encoding="utf-8").strip()
            if len(revision) == 40 and all(c in "0123456789abcdef" for c in revision):
                candidates.insert(0, snapshots / revision)
        for candidate in candidates:
            if candidate.is_dir() and candidate.resolve().parent == snapshots.resolve() and _snapshot_ready(candidate, True):
                return candidate
    except OSError:
        return None
    return None
