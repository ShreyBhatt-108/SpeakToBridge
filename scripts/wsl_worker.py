"""JSON-lines Whisper GPU worker for Linux; no listener or remote service."""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
import json
import os
import signal
import subprocess
import shutil
import queue
import threading
from pathlib import Path
import sys
import traceback

_PROTOCOL_STDOUT = sys.stdout

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
# This worker performs GPU inference. Keep CPU support work bounded and let
# waiting OpenMP threads sleep; do not change the shared environment globally.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
os.environ.setdefault("KMP_BLOCKTIME", "0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def send(value):
    print(json.dumps(value), file=_PROTOCOL_STDOUT, flush=True)


def prepare_model_cache(cache, model_name, status_callback=None):
    from SpeakToBridge.model_storage import is_model_cache_ready, find_cached_amd_model
    model_dir = cache / f"openai-whisper-{model_name}"
    marker = model_dir / ".speak_to_bridge_ready"
    existing = find_cached_amd_model(cache, model_name)
    if existing is not None:
        return existing
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


def supervise_gpu_worker(args):
    """Pause idle ROCm threads while retaining the loaded model in memory.

    Stop only after the child has synchronized GPU work and replied. Forward
    the reply after stopping, so a new request cannot race the pause.
    """
    child = subprocess.Popen(
        [sys.executable, "-u", str(Path(__file__).resolve()), "--gpu-child",
         "--cache", str(args.cache), "--model", args.model],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )
    requests = queue.Queue()
    ready = threading.Event()
    def read_requests():
        saw_request = False
        for request in sys.stdin:
            saw_request = True
            requests.put(request)
        requests.put(None)
        # The GUI can quit while weights are still loading. Do not leave an
        # unneeded GPU child running until initialization finishes.
        if not saw_request and not ready.is_set() and child.poll() is None:
            try:
                child.terminate()
            except ProcessLookupError:
                pass
    threading.Thread(target=read_requests, daemon=True).start()
    try:
        for line in child.stdout:
            reply = json.loads(line)
            if reply.get("ready"):
                ready.set()
                os.kill(child.pid, signal.SIGSTOP)
                send(reply)
                break
            send(reply)
            if "error" in reply:
                return 1
        else:
            raise RuntimeError("GPU child exited before becoming ready")
        for request in iter(requests.get, None):
            os.kill(child.pid, signal.SIGCONT)
            child.stdin.write(request)
            child.stdin.flush()
            for line in child.stdout:
                reply = json.loads(line)
                if "error" in reply:
                    send(reply)
                    return 1
                if "text" in reply:
                    os.kill(child.pid, signal.SIGSTOP)
                    send(reply)
                    break
                send(reply)
            else:
                raise RuntimeError("GPU child exited during transcription")
        return 0
    finally:
        if child.poll() is None:
            os.kill(child.pid, signal.SIGCONT)
            child.stdin.close()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=5)
        child.stdout.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--model", default="tiny")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--delete-model", choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--gpu-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.delete_model:
            base = args.cache.resolve()
            for prefix in ("openai-whisper-", "models--openai--whisper-"):
                target = (base / f"{prefix}{args.delete_model}").resolve()
                if target.parent != base:
                    raise ValueError("Model path is outside the configured GPU cache")
                if target.exists():
                    shutil.rmtree(target)
            send({"deleted": args.delete_model})
            return 0
        if not args.probe and not args.gpu_child:
            return supervise_gpu_worker(args)
        if not args.probe:
            send({"status": "Checking local GPU model files."})
            with redirect_stdout(sys.stderr):
                local_model = prepare_model_cache(args.cache, args.model, lambda message: send({"status": message}))
            send({"status": "Starting WSL PyTorch runtime; model files are cached."})
        with redirect_stdout(sys.stderr):
            import numpy as np
            import torch
            torch.set_num_threads(int(os.environ["OMP_NUM_THREADS"]))
            torch.set_num_interop_threads(1)
            if not args.probe:
                send({"status": "Verifying Radeon GPU runtime."})
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
                send({"status": f"Loading cached GPU model '{args.model}' into Radeon memory."})
                from SpeakToBridge.amd_whisper import AmdWhisperModel
                model = AmdWhisperModel(args.model, args.cache, index,
                                        status_callback=lambda message: send({"status": message}))
        if args.probe:
            send(info)
            return 0
        send({"status": "Warming Radeon inference kernels; preparing the first transcription."})
        with redirect_stdout(sys.stderr):
            model.transcribe(np.zeros(16000, dtype=np.float32), "en", "", {"vad_filter": False})
        torch.cuda.synchronize(index)
        del matrix
        shared = args.cache / f"openai-whisper-{args.model}"
        model_folder = shared if local_model.is_relative_to(shared) else args.cache / f"models--openai--whisper-{args.model}"
        cache_info = {"model_name": args.model, "size_bytes": sum(
            f.stat().st_size for f in model_folder.rglob("*") if f.is_file()), "ready": True}
        send(dict(info, ready=True, model_cache=cache_info))
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with redirect_stdout(sys.stderr):
                    audio = np.frombuffer(base64.b64decode(request["audio"], validate=True), dtype="<f4")
                    text = model.transcribe(audio, request["language"], request["initial_prompt"], {"vad_filter": False})
                torch.cuda.synchronize(index)
                send({"text": text})
            except Exception:
                send({"error": traceback.format_exc()})
        return 0
    except Exception:
        send({"error": traceback.format_exc()})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
