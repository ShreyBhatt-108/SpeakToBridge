from __future__ import annotations

import logging
import threading
import time
from typing import Any, List

import numpy as np


LOGGER = logging.getLogger(__name__)


def assess_microphone_audio(audio: np.ndarray, sample_rate: int = 16_000) -> dict[str, float | str]:
    """Return simple, explainable level diagnostics for a microphone test clip."""
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    duration = len(samples) / sample_rate if sample_rate else 0.0
    if samples.size == 0:
        return {"duration": duration, "rms_dbfs": -120.0, "peak_dbfs": -120.0,
                "clipping_percent": 0.0, "assessment": "No audio was captured. Check microphone permission and input selection."}
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples))))
    rms_dbfs = 20 * float(np.log10(max(rms, 1e-6)))
    peak_dbfs = 20 * float(np.log10(max(peak, 1e-6)))
    clipping_percent = float(np.mean(np.abs(samples) >= 0.98) * 100)
    if rms_dbfs < -45:
        assessment = "Very quiet. Move closer to the microphone or raise its input level."
    elif clipping_percent >= 0.1 or peak_dbfs > -0.3:
        assessment = "Too loud or clipping. Lower microphone input level or move farther away."
    elif rms_dbfs < -30:
        assessment = "A little quiet, but usable. A modest input-level increase may improve recognition."
    else:
        assessment = "Good recording level for speech recognition."
    return {"duration": duration, "rms_dbfs": rms_dbfs, "peak_dbfs": peak_dbfs,
            "clipping_percent": clipping_percent, "assessment": assessment}


class AudioRecorder:
    def __init__(self, sample_rate: int = 16_000, max_duration_seconds: int = 300) -> None:
        self.sample_rate = sample_rate
        self.max_duration_seconds = max(1, int(max_duration_seconds))
        self._max_samples = self.sample_rate * self.max_duration_seconds
        self._frames: List[np.ndarray] = []
        self._captured_samples = 0
        self._stream: Any | None = None
        self._sd_module: Any | None = None
        self._lock = threading.Lock()
        self._is_recording = False
        self._last_frame_time = 0.0

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def start(self) -> None:
        with self._lock:
            if self._is_recording:
                return
            sd = self._load_sounddevice()
            self._frames = []
            self._captured_samples = 0
            self._last_frame_time = time.monotonic()
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._on_audio_frame,
            )
            self._stream.start()
            self._is_recording = True
            LOGGER.info("Audio recording started")

    def stop(self) -> np.ndarray:
        with self._lock:
            if not self._is_recording:
                return np.array([], dtype=np.float32)

            stream = self._stream
            self._stream = None
            self._is_recording = False

        if stream is not None:
            stream.stop()
            stream.close()

        with self._lock:
            frames = self._frames
            self._frames = []
            self._captured_samples = 0

        if not frames:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(frames, axis=0).reshape(-1).astype(np.float32)
        LOGGER.info("Audio recording stopped with %s samples", len(audio))
        return audio

    def _on_audio_frame(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            LOGGER.warning("Sounddevice status: %s", status)
        with self._lock:
            if not self._is_recording or self._captured_samples >= self._max_samples:
                return
            remaining = self._max_samples - self._captured_samples
            frame_copy = indata[:remaining].copy()
            self._frames.append(frame_copy)
            self._captured_samples += len(frame_copy)
            self._last_frame_time = time.monotonic()

    def recent_audio(self, seconds: float = 2.0) -> tuple[np.ndarray, float]:
        remaining = int(seconds * self.sample_rate)
        chunks = []
        with self._lock:
            captured_at = self._last_frame_time
            for frame in reversed(self._frames):
                if remaining <= 0:
                    break
                chunk = frame[-remaining:]
                chunks.append(chunk)
                remaining -= len(chunk)
        if not chunks:
            return np.array([], dtype=np.float32), captured_at
        return np.concatenate(chunks[::-1], axis=0).reshape(-1), captured_at

    def set_max_duration_seconds(self, seconds: int) -> None:
        with self._lock:
            self.max_duration_seconds = max(1, int(seconds))
            self._max_samples = self.sample_rate * self.max_duration_seconds

    def _load_sounddevice(self):  # noqa: ANN001
        if self._sd_module is not None:
            return self._sd_module
        try:
            import sounddevice as sd  # pylint: disable=import-outside-toplevel
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Microphone audio backend could not be loaded. "
                "Please reinstall Speak to Bridge using the correct Windows architecture build."
            ) from exc
        self._sd_module = sd
        return sd
