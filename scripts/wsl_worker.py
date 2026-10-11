"""JSON-lines Whisper GPU worker for Linux; no listener or remote service."""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import traceback

_PROTOCOL_STDOUT = sys.stdout

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def send(value):
    print(json.dumps(value), file=_PROTOCOL_STDOUT, flush=True)


def prepare_model_cache(cache, model_name, status_callback=None):
    from SpeakToBridge.model_storage import is_model_cache_ready
    model_dir = cache / f"openai-whisper-{model_name}"
    marker = model_dir / ".speak_to_bridge_ready"
    if marker.is_file() and is_model_cache_ready(model_dir):
        return model_dir
    if status_callback:
        size_hint = " (approximately 3.1 GB of weights)" if model_name == "large-v3" else ""
        status_callback(f"Downloading missing GPU model files for '{model_name}'{size_hint}.")
    from huggingface_hub import snapshot_download
    snapshot_download(f"openai/whisper-{model_name}", local_dir=str(model_dir),
                      allow_patterns=["*.json", "*.txt", "model.safetensors"],
                      ignore_patterns=["*fp32*"])
    if not is_model_cache_ready(model_dir):
        raise RuntimeError(f"Incomplete downloaded Whisper model: {model_dir}")
    marker.write_text("ready", encoding="utf-8")
    return model_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    try:
        with redirect_stdout(sys.stderr):
            import numpy as np
            import torch
            if not torch.version.hip or not torch.cuda.is_available():
                raise RuntimeError("ROCm GPU is unavailable in WSL")
            index = next((i for i in range(torch.cuda.device_count())
                          if "8060" in torch.cuda.get_device_name(i)), 0)
            matrix = torch.ones((32, 32), device=f"cuda:{index}", dtype=torch.float16)
            passed = (matrix @ matrix).float().mean().item() == 32
            if not passed:
                raise RuntimeError("WSL Radeon FP16 matrix test failed")
            info = {"amd_gpu": torch.cuda.get_device_name(index), "torch_version": torch.__version__,
                    "rocm_version": torch.version.hip, "gpu_matrix_test": passed}
            if not args.probe:
                prepare_model_cache(args.cache, args.model, lambda message: send({"status": message}))
                send({"status": f"Loading cached GPU model '{args.model}' into Radeon memory."})
                from SpeakToBridge.amd_whisper import AmdWhisperModel
                model = AmdWhisperModel(args.model, args.cache, index)
        if args.probe:
            send(info)
            return 0
        send(dict(info, ready=True))
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with redirect_stdout(sys.stderr):
                    audio = np.frombuffer(base64.b64decode(request["audio"], validate=True), dtype="<f4")
                    text = model.transcribe(audio, request["language"], request["initial_prompt"], {"vad_filter": False})
                send({"text": text})
            except Exception:
                send({"error": traceback.format_exc()})
        return 0
    except Exception:
        send({"error": traceback.format_exc()})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
