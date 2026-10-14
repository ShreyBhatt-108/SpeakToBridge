"""Optional Whisper inference on AMD GPUs through ROCm PyTorch.

ROCm intentionally exposes GPUs through torch.cuda; torch.version.hip is
what distinguishes an AMD build from NVIDIA CUDA or CPU-only PyTorch.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import sys
import logging
import importlib.metadata

import numpy as np


LOGGER = logging.getLogger(__name__)
_rocm_import_attempted = False


@contextmanager
def optional_runtime_import():
    # An unavailable optional DLL should produce a logged Python error and CPU
    # fallback, rather than a Windows loader dialog. This does not change any
    # security policy or permit a blocked DLL to load.
    previous_mode = None
    kernel = None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetThreadErrorMode.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetThreadErrorMode.restype = wintypes.BOOL
        kernel.GetThreadErrorMode.restype = wintypes.DWORD
        old_mode = wintypes.DWORD()
        if kernel.SetThreadErrorMode(kernel.GetThreadErrorMode() | 0x8001, ctypes.byref(old_mode)):
            previous_mode = old_mode.value
    try:
        yield
    finally:
        if previous_mode is not None:
            kernel.SetThreadErrorMode(previous_mode, None)


def rocm_import_attempted() -> bool:
    # Failed torch imports can leave native OpenMP DLLs loaded even after Python
    # removes torch from sys.modules. Keep CPU inference isolated in that case.
    return _rocm_import_attempted


def amd_device() -> tuple[int, str] | None:
    global _rocm_import_attempted
    try:
        try:
            _rocm_import_attempted |= "rocm" in importlib.metadata.version("torch").lower()
        except importlib.metadata.PackageNotFoundError:
            pass
        with optional_runtime_import():
            import torch

            if not torch.version.hip or not torch.cuda.is_available():
                return None
            for index in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(index)
                if "8060" in name:
                    return index, name
            return 0, torch.cuda.get_device_name(0)
    except ModuleNotFoundError:
        return None
    except Exception:
        LOGGER.exception("AMD runtime unavailable; CPU fallback remains available")
        return None



class AmdWhisperModel:
    def __init__(self, model_name: str, cache_dir: Path, device_index: int, status_callback=None) -> None:
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        self._torch = torch
        self._device = f"cuda:{device_index}"
        repository = f"openai/whisper-{model_name}"
        # A local_dir download contains regular files readable by both Windows
        # and WSL, unlike Linux-only symlinks written on a mounted NTFS drive.
        from .model_storage import find_cached_amd_model
        shared_model = find_cached_amd_model(cache_dir, model_name)
        if shared_model is not None:
            repository = str(shared_model)
        self._processor = WhisperProcessor.from_pretrained(repository, cache_dir=str(cache_dir))
        if status_callback:
            status_callback("Reading cached model weights into memory.")
        self._model = WhisperForConditionalGeneration.from_pretrained(
            repository,
            cache_dir=str(cache_dir),
            torch_dtype=torch.float16,
            # Standard attention avoids dependence on optional CUDA-only kernels.
            attn_implementation="eager",
            use_safetensors=True,
        )
        if sys.platform == "linux" and torch.version.hip:
            # Hundreds of individual .to() allocations/copies are particularly
            # expensive through WSL's GPU bridge. Transfer one flat FP16 buffer
            # and give each parameter a view into it (preserving tied weights).
            with torch.no_grad():
                if status_callback:
                    status_callback("Packing model weights for GPU transfer.")
                parameters = list(self._model.parameters())
                packed = torch.nn.utils.parameters_to_vector(parameters)
                if status_callback:
                    status_callback("Moving model weights into Radeon GPU memory.")
                gpu_weights = packed.to(self._device)
                torch.nn.utils.vector_to_parameters(gpu_weights, parameters)
                del packed
                for module in self._model.modules():
                    for name, buffer in module._buffers.items():
                        if buffer is not None:
                            module._buffers[name] = buffer.to(self._device)
            self._model.eval()
        else:
            if status_callback:
                status_callback("Moving model weights into Radeon GPU memory.")
            self._model = self._model.to(self._device).eval()
        if sys.platform == "win32":
            if status_callback:
                status_callback("Warming Radeon inference kernels; preparing the first transcription.")
            self.transcribe(np.zeros(16000, dtype=np.float32), "en", "", {"vad_filter": False})
            torch.cuda.synchronize(device_index)

    def transcribe(self, audio: np.ndarray, language: str, initial_prompt: str, vad: dict) -> str:
        if vad.get("vad_filter"):
            from .vad import get_speech_timestamps

            spans = get_speech_timestamps(audio, **vad.get("vad_parameters", {}))
            if not spans:
                return ""
            audio = np.concatenate([audio[span["start"]:span["end"]] for span in spans])
        # Preserve the entire recording: Whisper's sequential long-form decoding
        # handles audio beyond 30 seconds rather than truncating it.
        inputs = self._processor(
            audio, sampling_rate=16_000, return_tensors="pt",
            truncation=False, padding="longest", return_attention_mask=True,
        )
        inputs["input_features"] = inputs["input_features"].to(self._device, self._torch.float16)
        inputs["attention_mask"] = inputs["attention_mask"].to(self._device)
        options = dict(
            language=language, task="transcribe", num_beams=4,
            return_timestamps=True, condition_on_prev_tokens=True,
        )
        if initial_prompt:
            options["prompt_ids"] = self._processor.get_prompt_ids(
                initial_prompt, return_tensors="pt"
            ).to(self._device)
            options["prompt_condition_type"] = "all-segments"
        with self._torch.inference_mode():
            tokens = self._model.generate(**inputs, **options)
        return self._processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
