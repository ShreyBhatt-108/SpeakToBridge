from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SpeakToBridge.config import AppConfig, ConfigStore
from SpeakToBridge.paths import get_config_path, get_model_cache_dir
from SpeakToBridge.whisper_engine import WhisperEngine


def main() -> int:
    print("Running basic smoke checks...")

    config_store = ConfigStore(get_config_path())
    config = config_store.load()
    if not isinstance(config, AppConfig):
        raise RuntimeError("Config load did not return AppConfig")

    config_store.save(config)
    cfg_file = Path(get_config_path())
    if not cfg_file.exists():
        raise RuntimeError("Config file was not written.")
    print(f"Config OK: {cfg_file}")

    model_cache = get_model_cache_dir()
    if not model_cache.exists():
        raise RuntimeError("Model cache directory does not exist.")
    print(f"Model cache dir OK: {model_cache}")

    engine = WhisperEngine(
        model_name=config.model_name,
        language=config.language,
        runtime_mode=config.runtime_mode,
        vad_mode=config.vad_mode,
        model_cache_dir=model_cache,
    )
    runtime = engine._resolve_runtime()  # noqa: SLF001
    print(f"Inference runtime resolved to: device={runtime[0]}, compute_type={runtime[1]}")

    print("Smoke checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
