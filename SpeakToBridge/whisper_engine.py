from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from .model_storage import is_model_cache_ready
from .amd_whisper import AmdWhisperModel, amd_device


LOGGER = logging.getLogger(__name__)

# Avoid Hugging Face Xet transport on Windows where it can stall for some users.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def _has_cuda_device() -> bool:
    try:
        import ctranslate2  # pylint: disable=import-outside-toplevel

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


class WhisperEngine:
    def __init__(
        self,
        model_name: str,
        language: str,
        runtime_mode: str,
        vad_mode: str,
        model_cache_dir: Path,
        status_callback=None,  # noqa: ANN001
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._runtime_mode = runtime_mode
        self._vad_mode = vad_mode
        self._model_cache_dir = model_cache_dir
        self._status_callback = status_callback
        self._model: WhisperModel | AmdWhisperModel | None = None
        self._gpu_failed = False
        self._amd_device_index = 0
        self._runtime_description = "Not loaded yet"
        self._device = "cpu"
        self._compute_type = "int8"
        self._model_lock = threading.Lock()
        self._model_cv = threading.Condition(self._model_lock)
        self._loading_in_progress = False
        self._known_cached_models: set[str] = set()

    def update_model(self, model_name: str) -> None:
        if model_name == self._model_name:
            return
        with self._model_cv:
            self._model_name = model_name
            self._model = None
            self._runtime_description = "Not loaded yet"
            self._model_cv.notify_all()

    def _resolve_runtime(self) -> tuple[str, str]:
        if self._runtime_mode == "cpu" or self._gpu_failed:
            return "cpu", "int8"
        candidate = amd_device()
        if candidate is not None:
            self._amd_device_index, self._amd_device_name = candidate
            return "rocm", "float16"
        if self._runtime_mode == "amd_gpu":
            self._emit_status("AMD GPU runtime or compatible driver unavailable. Using CPU; check the hardware report and AMD setup guide.")
            return "cpu", "int8"
        if self._runtime_mode == "cpu_auto_gpu" and _has_cuda_device():
            return "cuda", "float16"
        return "cpu", "int8"

    @property
    def runtime_description(self) -> str:
        return self._runtime_description

    def update_runtime(self, runtime_mode: str) -> None:
        with self._model_cv:
            self._runtime_mode = runtime_mode
            self._gpu_failed = False
            self._model = None
            self._runtime_description = "Not loaded yet"
            self._model_cv.notify_all()

    def _emit_status(self, message: str) -> None:
        if self._status_callback is not None:
            self._status_callback(message)

    @staticmethod
    def _model_source(model_name: str) -> str:
        return f"Hugging Face Hub (Systran/faster-whisper-{model_name})"

    def _is_model_cached_locally(self, model_name: str) -> bool:
        candidate = self._model_cache_dir / f"models--Systran--faster-whisper-{model_name}"
        if model_name in self._known_cached_models and is_model_cache_ready(candidate):
            return True
        # A cache folder can exist after a failed or partial download. Only call it
        # local when the actual model files are present.
        cached = is_model_cache_ready(candidate)
        if cached:
            self._known_cached_models.add(model_name)
        else:
            self._known_cached_models.discard(model_name)
        return cached

    def _ensure_model(self) -> None:
        while True:
            with self._model_cv:
                if self._model is not None:
                    return
                if self._loading_in_progress:
                    self._model_cv.wait(timeout=0.5)
                    continue
                self._loading_in_progress = True
                model_name = self._model_name
                runtime_mode = self._runtime_mode
                device, compute_type = self._resolve_runtime()

            source = (f"Hugging Face Hub (openai/whisper-{model_name})" if device == "rocm"
                      else self._model_source(model_name))
            if device == "rocm":
                self._emit_status(f"Preparing AMD GPU model '{model_name}' from {source}; downloading missing files.")
            elif self._is_model_cached_locally(model_name):
                self._emit_status(f"Loading model '{model_name}' from local cache.")
            else:
                self._emit_status(f"Downloading model '{model_name}' from {source}.")
            LOGGER.info(
                "Loading Whisper model '%s' (device=%s, compute_type=%s)",
                model_name,
                device,
                compute_type,
            )
            try:
                if device == "rocm":
                    loaded_model = AmdWhisperModel(model_name, self._model_cache_dir, self._amd_device_index)
                else:
                    loaded_model = WhisperModel(
                        model_name, device=device, compute_type=compute_type,
                        download_root=str(self._model_cache_dir),
                    )
            except Exception:
                with self._model_cv:
                    if device != "cpu":
                        self._gpu_failed = True
                    self._loading_in_progress = False
                    self._model_cv.notify_all()
                if device != "cpu":
                    LOGGER.exception("GPU model initialization failed; falling back to CPU")
                    self._emit_status("GPU initialization failed. Falling back to CPU.")
                    continue
                raise

            with self._model_cv:
                self._loading_in_progress = False
                self._model_cv.notify_all()
                # If the requested model changed while loading, discard and load current target.
                if self._model_name != model_name or self._runtime_mode != runtime_mode:
                    continue
                self._device = device
                self._compute_type = compute_type
                self._model = loaded_model
                if device != "rocm":
                    self._known_cached_models.add(model_name)
                self._runtime_description = (
                    f"AMD ROCm GPU: {self._amd_device_name} (FP16)" if device == "rocm"
                    else "NVIDIA CUDA GPU (FP16)" if device == "cuda" else "CPU (INT8)"
                )
                self._emit_status(f"Model ready. Using {self._runtime_description}.")
                return

    def warm_model(self) -> None:
        self._ensure_model()

    def _vad_options(self) -> dict:
        if self._vad_mode == "off":
            return {"vad_filter": False}
        profiles = {
            # More aggressive, useful if the user prefers speed and accepts that
            # some long intentional pauses may be shortened.
            "fast": {"min_silence_duration_ms": 500, "speech_pad_ms": 250},
            # Default: remove real dead air while preserving most comma/period
            # pause cues for Whisper's punctuation inference.
            "pause_preserving": {"min_silence_duration_ms": 1000, "speech_pad_ms": 350},
            # Maximum protection for intentional pauses, with less speed benefit.
            "accuracy": {"min_silence_duration_ms": 1600, "speech_pad_ms": 500},
        }
        profile = profiles.get(self._vad_mode, profiles["pause_preserving"])
        return {
            "vad_filter": True,
            "vad_parameters": {
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "min_silence_duration_ms": profile["min_silence_duration_ms"],
                "speech_pad_ms": profile["speech_pad_ms"],
            },
        }

    def transcribe(self, audio: np.ndarray, initial_prompt: str = "") -> str:
        try:
            return self._transcribe(audio, initial_prompt)
        except Exception:
            if self._device == "cpu" or self._model is None:
                raise
            LOGGER.exception("GPU transcription failed; retrying recording on CPU")
            with self._model_cv:
                self._model = None
                self._gpu_failed = True
                self._runtime_description = "Not loaded yet"
            self._emit_status("GPU transcription failed. Retrying on CPU.")
            return self._transcribe(audio, initial_prompt)

    def _transcribe(self, audio: np.ndarray, initial_prompt: str = "") -> str:
        if audio.size == 0:
            return ""
        self._ensure_model()
        assert self._model is not None
        self._emit_status(f"Transcribing with {self._runtime_description}.")
        if isinstance(self._model, AmdWhisperModel):
            return self._model.transcribe(audio, self._language, initial_prompt, self._vad_options())
        options = {
            "language": self._language,
            "beam_size": 4,
        }
        options.update(self._vad_options())
        if initial_prompt:
            options["initial_prompt"] = initial_prompt
        segments, _info = self._model.transcribe(
            audio,
            **options,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text
