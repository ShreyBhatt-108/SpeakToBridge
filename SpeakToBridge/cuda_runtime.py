"""Locate optional NVIDIA redistributables without changing system settings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_dll_handles: list[object] = []
_configured = False


def configure_cuda_dlls() -> None:
    global _configured
    if _configured or sys.platform != "win32":
        return
    _configured = True
    if getattr(sys, "frozen", False):
        roots = [Path(sys._MEIPASS)]
    else:
        roots = [Path(item) for item in sys.path if item and Path(item).is_absolute()]
    folders: list[str] = []
    for root in roots:
        for package in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            directory = root / "nvidia" / package / "bin"
            if directory.is_dir():
                resolved = str(directory.resolve())
                if resolved not in folders:
                    folders.append(resolved)
    for folder in folders:
        # Retain handles: closing one removes the directory from DLL lookup.
        _dll_handles.append(os.add_dll_directory(folder))
    if folders:
        os.environ["PATH"] = os.pathsep.join(folders + [os.environ.get("PATH", "")])
