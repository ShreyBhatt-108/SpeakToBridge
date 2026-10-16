"""Diagnostics available in both source and packaged releases."""
from __future__ import annotations

import argparse
import json
import platform
import os
import sys
import subprocess
import traceback
import wave
from pathlib import Path

import numpy as np

from .amd_whisper import amd_device, optional_runtime_import
from .wsl_whisper import WslWhisperModel, wsl_enabled
from .constants import APP_VERSION
from .paths import get_app_data_dir, get_model_cache_dir
from .whisper_engine import WhisperEngine


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--model", default="small", choices=("tiny", "base", "small", "medium", "large-v3"))
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--require-amd", action="store_true")
    args = parser.parse_args(arguments)
    result = {"version": APP_VERSION, "python": platform.python_version(), "architecture": platform.machine(), "frozen": bool(getattr(sys, "frozen", False))}
    exit_code = 0
    if sys.platform == "win32":
        try:
            hardware = subprocess.run(
                [str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"System32\WindowsPowerShell\v1.0\powershell.exe"), "-NoProfile", "-Command",
                 "@{cpu=(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name); graphics=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)} | ConvertTo-Json -Depth 4"],
                capture_output=True, text=True, timeout=20, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            result["windows_hardware"] = json.loads(hardware.stdout)
        except Exception as exc:
            result["hardware_query_error"] = str(exc)
    try:
        if args.cpu:
            result["optional_runtime_probe_skipped"] = "CPU-only diagnostic"
        elif wsl_enabled():
            result["gpu_transport"] = "WSL"
            try:
                result.update(WslWhisperModel.probe(get_model_cache_dir()))
            except Exception as exc:
                result.update(amd_gpu=None, optional_runtime_error=str(exc), optional_runtime_traceback=traceback.format_exc())
        else:
            try:
                with optional_runtime_import():
                    import torch
                    from transformers import WhisperForConditionalGeneration, WhisperProcessor

                    result.update(rocm_version=torch.version.hip, torch_version=torch.__version__, whisper_imports=True)
            except Exception as exc:
                result.update(rocm_version=None, whisper_imports=False, optional_runtime_error=str(exc), optional_runtime_traceback=traceback.format_exc())
        candidate = amd_device() if not args.cpu and not wsl_enabled() else None
        if not wsl_enabled() or args.cpu:
            result["amd_gpu"] = candidate[1] if candidate else None
        if candidate:
            import torch
            matrix = torch.ones((32, 32), device=f"cuda:{candidate[0]}", dtype=torch.float16)
            result["gpu_matrix_test"] = (matrix @ matrix).float().mean().item() == 32
            if not result["gpu_matrix_test"]:
                raise RuntimeError("GPU FP16 matrix multiplication failed")
        if args.require_amd and not result.get("amd_gpu"):
            exit_code = 1
        if args.wav:
            with wave.open(str(args.wav), "rb") as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                    raise ValueError("Use a 16 kHz mono PCM16 WAV")
                audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
            engine = WhisperEngine(args.model, "en", "cpu" if args.cpu else "cpu_auto_gpu", "pause_preserving", get_model_cache_dir())
            result["transcript"] = engine.transcribe(audio)
            result["actual_backend"] = engine.runtime_description
            from .cpu_worker import CpuWhisperWorker
            result["cpu_worker_isolated"] = isinstance(engine._model, CpuWhisperWorker)
            if args.require_amd and not engine.runtime_description.startswith("AMD ROCm"):
                exit_code = 1
    except Exception:
        result["error"] = traceback.format_exc()
        exit_code = 1
    result["exit_code"] = exit_code
    output = args.output or (get_app_data_dir() / "hardware-diagnostics.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if sys.stdout is not None:
        print(json.dumps(result, indent=2))
        print(f"Saved to {output}")
    return exit_code
