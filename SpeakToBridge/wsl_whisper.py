"""Local WSL transport; the Windows process never imports ROCm for this backend."""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path, PureWindowsPath
import queue
import subprocess
import threading
import time

import numpy as np


def _settings() -> dict:
    if "SPEAK_TO_BRIDGE_WSL_DISTRO" in os.environ:
        return {"distribution": os.environ["SPEAK_TO_BRIDGE_WSL_DISTRO"],
                "python": os.environ.get("SPEAK_TO_BRIDGE_WSL_PYTHON", "/opt/amd-ai/bin/python"),
                "worker": os.environ.get("SPEAK_TO_BRIDGE_WSL_WORKER", ""),
                "gpu_cache": os.environ.get("SPEAK_TO_BRIDGE_WSL_CACHE", "")}
    local = os.environ.get("LOCALAPPDATA")
    if local:
        try:
            value = json.loads((Path(local)/"SpeakToBridge/wsl-runtime.json").read_text(encoding="utf-8"))
            if value.get("enabled") is True:
                return value
        except (OSError, ValueError, AttributeError):
            pass
    return {}


def wsl_enabled() -> bool:
    return os.name == "nt" and bool(_settings().get("distribution"))


def linux_path(path: Path) -> str:
    value = PureWindowsPath(str(path))
    if not value.drive or value.drive.startswith("\\\\"):
        raise ValueError("WSL worker/cache must be on a local Windows drive")
    return f"/mnt/{value.drive[0].lower()}/" + "/".join(value.parts[1:])


def worker_command(cache_dir: Path, model_name: str | None) -> list[str]:
    settings = _settings()
    worker = settings.get("worker")
    if not worker:
        raise RuntimeError("Set SPEAK_TO_BRIDGE_WSL_WORKER to scripts/wsl_worker.py")
    command = ["wsl.exe", "--distribution", settings["distribution"],
               "--exec", settings.get("python", "/opt/amd-ai/bin/python"),
               "-u", linux_path(Path(worker)), "--cache", settings.get("gpu_cache") or linux_path(cache_dir)]
    command += ["--model", model_name] if model_name else ["--probe"]
    return command


class WslWhisperModel:
    _wsl_worker = True
    def __init__(self, model_name: str, cache_dir: Path, device_index: int = 0, status_callback=None) -> None:
        self._status_callback = status_callback
        self._lock = threading.Lock()
        self._replies = queue.Queue()
        self._process = subprocess.Popen(
            worker_command(cache_dir, model_name), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._stderr = []
        def read_stdout():
            for line in self._process.stdout:
                self._replies.put(line.replace("\x00", ""))
            self._replies.put(None)
        def read_stderr():
            last_progress = 0
            for line in self._process.stderr:
                self._stderr.append(line)
                del self._stderr[:-30]
                if self._status_callback and "model.safetensors:" in line and time.monotonic() - last_progress >= 5:
                    last_progress = time.monotonic()
                    self._status_callback("Downloading GPU weights: " + line.strip())
        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        try:
            ready = self._read_reply(900)
            if not ready.get("ready") or not ready.get("gpu_matrix_test"):
                raise RuntimeError("WSL worker did not verify GPU execution")
            self.device_name = ready["amd_gpu"]
            if ready.get("model_cache") and _settings().get("gpu_cache"):
                from .model_storage import record_wsl_cached_model
                try:
                    record_wsl_cached_model(cache_dir, ready["model_cache"])
                except OSError:
                    logging.getLogger(__name__).warning("GPU is ready, but its cache summary could not be saved", exc_info=True)
        except Exception:
            self.close()
            raise

    def _read_reply(self, timeout=300):
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self._replies.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise RuntimeError("WSL transcription worker timed out") from exc
            if line is None:
                raise RuntimeError("WSL transcription worker stopped: " + "".join(self._stderr))
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError("WSL worker could not start: " + line + "".join(self._stderr)) from exc
            if "error" in value:
                raise RuntimeError(value["error"])
            if "status" in value:
                if self._status_callback:
                    self._status_callback(value["status"])
                continue
            return value

    @staticmethod
    def probe(cache_dir: Path) -> dict:
        result = subprocess.run(worker_command(cache_dir, None), capture_output=True,
                                text=True, encoding="utf-8", timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError((result.stdout + result.stderr).replace("\x00", ""))
        return json.loads(result.stdout)

    def transcribe(self, audio, language, initial_prompt, vad):
        if vad.get("vad_filter"):
            from .vad import get_speech_timestamps
            spans = get_speech_timestamps(audio, **vad.get("vad_parameters", {}))
            if not spans:
                return ""
            audio = np.concatenate([audio[span["start"]:span["end"]] for span in spans])
        value = {"audio": base64.b64encode(np.asarray(audio, dtype="<f4").tobytes()).decode("ascii"),
                 "language": language, "initial_prompt": initial_prompt}
        with self._lock:
            self._process.stdin.write(json.dumps(value) + "\n")
            self._process.stdin.flush()
            return self._read_reply()["text"]

    def close(self):
        process = getattr(self, "_process", None)
        if process is None:
            return
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
