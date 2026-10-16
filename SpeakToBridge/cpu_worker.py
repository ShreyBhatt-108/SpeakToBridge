"""Keep CTranslate2's CPU OpenMP runtime separate from ROCm PyTorch."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np


class CpuWhisperWorker:
    _cpu_worker = True

    def __init__(self, model_name: str, cache_dir: Path, *, device: str = "cpu", compute_type: str = "int8") -> None:
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(Path(__file__).resolve().parent.parent / "launcher.py"))
        if device not in ("cpu", "cuda") or compute_type not in ("int8", "float16"):
            raise ValueError("Unsupported CTranslate2 worker runtime")
        command.extend(["--cpu-worker", model_name, str(cache_dir), device, compute_type])
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self._read_reply()

    def _read_reply(self):
        line = self._process.stdout.readline()
        if not line:
            raise RuntimeError("Transcription worker stopped unexpectedly")
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

    def transcribe(self, audio, **options):
        payload = {"audio": base64.b64encode(np.asarray(audio, dtype="<f4").tobytes()).decode("ascii"), "options": options}
        with self._lock:
            self._process.stdin.write(json.dumps(payload) + "\n")
            self._process.stdin.flush()
            reply = self._read_reply()
        return [SimpleNamespace(text=text) for text in reply["segments"]], None

    def close(self):
        process = getattr(self, "_process", None)
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        if process is not None:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()

    def __del__(self):
        try:
            self.close()
        except (OSError, ValueError):
            pass


def main(arguments):
    # CTranslate2 imports optional model converters, which otherwise import
    # installed PyTorch even though CPU inference does not use it.
    sys.modules["torch"] = None
    # A windowed frozen executable has no standard streams. Use the inherited
    # pipe handles explicitly so the worker protocol works in installed builds.
    if sys.stdin is None or sys.stdout is None:
        import os
        import msvcrt
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.restype = ctypes.c_void_p
        sys.stdin = os.fdopen(msvcrt.open_osfhandle(kernel.GetStdHandle(-10), os.O_RDONLY), "r", encoding="utf-8")
        sys.stdout = os.fdopen(msvcrt.open_osfhandle(kernel.GetStdHandle(-11), os.O_WRONLY), "w", encoding="utf-8")
    def send(value):
        sys.stdout.write(json.dumps(value) + "\n")
        sys.stdout.flush()
    try:
        from .cuda_runtime import configure_cuda_dlls
        configure_cuda_dlls()
        from faster_whisper import WhisperModel
        device = arguments[2] if len(arguments) > 2 else "cpu"
        compute_type = arguments[3] if len(arguments) > 3 else "int8"
        if device not in ("cpu", "cuda") or compute_type not in ("int8", "float16"):
            raise ValueError("Unsupported CTranslate2 worker runtime")
        model = WhisperModel(arguments[0], device=device, compute_type=compute_type, download_root=arguments[1])
        send({"ready": True})
        for line in sys.stdin:
            try:
                request = json.loads(line)
                audio = np.frombuffer(base64.b64decode(request["audio"]), dtype="<f4")
                segments, _ = model.transcribe(audio, **request["options"])
                send({"segments": [segment.text for segment in segments]})
            except Exception as exc:
                send({"error": str(exc)})
    except Exception as exc:
        send({"error": str(exc)})
        return 1
    return 0
