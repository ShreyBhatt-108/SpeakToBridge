from __future__ import annotations

import logging
import threading
from typing import Any, List

import numpy as np


LOGGER = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate
        self._frames: List[np.ndarray] = []
        self._stream: Any | None = None
        self._sd_module: Any | None = None
        self._lock = threading.Lock()
        self._is_recording = False

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

        if not self._frames:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).reshape(-1).astype(np.float32)
        LOGGER.info("Audio recording stopped with %s samples", len(audio))
        return audio

    def _on_audio_frame(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            LOGGER.warning("Sounddevice status: %s", status)
        self._frames.append(indata.copy())

    def _load_sounddevice(self):  # noqa: ANN001
        if self._sd_module is not None:
            return self._sd_module
        try:
            import sounddevice as sd  # pylint: disable=import-outside-toplevel
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Microphone audio backend could not be loaded. "
                "Please reinstall SeverusAI using the correct Windows architecture build."
            ) from exc
        self._sd_module = sd
        return sd
