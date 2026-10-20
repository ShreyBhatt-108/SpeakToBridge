"""Watch speech activity only while recording; never run inference in the audio callback."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np

LOGGER = logging.getLogger(__name__)
SILENCE_TIMEOUT_SECONDS = 30.0


class SpeechSilenceMonitor:
    def __init__(self, snapshot, on_timeout, on_error, sample_rate=16000):
        self._snapshot = snapshot
        self._on_timeout = on_timeout
        self._on_error = on_error
        self._sample_rate = sample_rate
        self._stop = threading.Event()
        self._thread = None
        self._last_speech_at = 0.0

    def start(self):
        self.stop()
        self._last_speech_at = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(self._stop,),
            daemon=True,
            name="speak-to-bridge-silence",
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)
        self._thread = None

    def _check_silence(self, model, now):
        audio, captured_at = self._snapshot()
        if audio.size:
            padded = np.pad(audio, (0, (-len(audio)) % 512))
            probabilities = np.asarray(model(padded)).reshape(-1)
            speech = np.flatnonzero(probabilities >= 0.5)
            if speech.size:
                end_sample = min(len(audio), (int(speech[-1]) + 1) * 512)
                speech_at = captured_at - (len(audio) - end_sample) / self._sample_rate
                self._last_speech_at = max(self._last_speech_at, speech_at)
        return now - self._last_speech_at >= SILENCE_TIMEOUT_SECONDS

    def _run(self, stopped):
        try:
            from .vad import get_vad_model

            model = get_vad_model()
            while not stopped.wait(0.5):
                if self._check_silence(model, time.monotonic()):
                    if not stopped.is_set():
                        self._on_timeout()
                    return
        except Exception:
            LOGGER.exception("Speech silence monitor failed")
            if not stopped.is_set():
                self._on_error(
                    "Silence detection unavailable. The maximum recording limit still applies."
                )
