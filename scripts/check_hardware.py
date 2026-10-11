"""Read-only hardware detection; --transcribe WAV verifies real inference."""
from __future__ import annotations

import argparse
import platform
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SpeakToBridge.amd_whisper import amd_device
from SpeakToBridge.paths import get_model_cache_dir
from SpeakToBridge.whisper_engine import WhisperEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-amd", action="store_true")
    parser.add_argument("--transcribe", type=Path, help="16 kHz mono PCM16 WAV; may download a model")
    parser.add_argument("--model", default="tiny", choices=("tiny", "base", "small", "medium", "large-v3"))
    args = parser.parse_args()
    print(f"CPU architecture: {platform.machine()}; Python: {platform.python_version()}")
    candidate = amd_device()
    print(f"AMD ROCm GPU: {candidate[1] if candidate else 'not available in this Python environment'}")
    if args.require_amd and candidate is None:
        print("Check x64 Python 3.12, AMD ROCm PyTorch, and the AMD graphics driver.")
        return 1
    if candidate:
        import torch
        # Detection alone does not prove the driver can execute GPU kernels.
        device = f"cuda:{candidate[0]}"
        a = torch.ones((32, 32), device=device, dtype=torch.float16)
        assert (a @ a).float().mean().item() == 32
        print(f"GPU FP16 matrix multiplication passed on {candidate[1]}.")
    engine = WhisperEngine(args.model, "en", "amd_gpu" if args.require_amd else "cpu_auto_gpu", "pause_preserving", get_model_cache_dir(), print)
    print(f"Selected backend: {engine._resolve_runtime()}")
    if args.transcribe:
        import numpy as np
        with wave.open(str(args.transcribe), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                raise ValueError("Use a 16 kHz mono PCM16 WAV file.")
            audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        print(f"Transcript: {engine.transcribe(audio)}")
        print(f"Actual backend: {engine.runtime_description}")
        if args.require_amd and not engine.runtime_description.startswith("AMD ROCm"):
            print("GPU inference was not verified: the app fell back to CPU.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
