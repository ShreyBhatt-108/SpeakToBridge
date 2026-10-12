from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class SoundFeedbackPlayer:
    """Play the latest cue, interrupting obsolete feedback immediately."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._pending: Path | None = None
        self._interrupt: threading.Event | None = None
        self._closed = False
        self._worker = threading.Thread(target=self._run, daemon=True, name="speak-to-bridge-sound-feedback")
        self._worker.start()

    def play(self, sound_path: Path) -> None:
        if not sound_path.exists():
            return
        with self._condition:
            if self._closed:
                return
            self._pending = sound_path
            if self._interrupt is not None:
                self._interrupt.set()
            self._condition.notify()

    def stop(self) -> None:
        with self._condition:
            self._pending = None
            if self._interrupt is not None:
                self._interrupt.set()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
            if self._interrupt is not None:
                self._interrupt.set()
            self._condition.notify()

    def _run(self) -> None:
        sequence = 0
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._pending is not None)
                if self._closed:
                    return
                sound_path = self._pending
                self._pending = None
                interrupt = self._interrupt = threading.Event()
            sequence += 1
            self._play_blocking(sound_path, f"speaktobridgecue{sequence}", interrupt)

    @staticmethod
    def _play_blocking(sound_path: Path, alias: str, interrupt: threading.Event) -> None:
        mci_send_string = ctypes.windll.winmm.mciSendStringW
        mci_send_string.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
        mci_send_string.restype = wintypes.UINT
        opened = False
        try:
            result = mci_send_string(f'open "{sound_path}" type mpegvideo alias {alias}', None, 0, 0)
            if result != 0:
                raise OSError(f"MCI open failed with code {result}")
            opened = True

            length_buffer = ctypes.create_unicode_buffer(32)
            result = mci_send_string(f"status {alias} length", length_buffer, len(length_buffer), 0)
            duration_seconds = 2.0
            if result == 0:
                try:
                    duration_seconds = max(0.1, int(length_buffer.value) / 1000.0)
                except ValueError:
                    pass

            if interrupt.is_set():
                return
            result = mci_send_string(f"play {alias} from 0", None, 0, 0)
            if result != 0:
                raise OSError(f"MCI play failed with code {result}")
            interrupt.wait(duration_seconds + 0.1)
        except Exception:
            LOGGER.exception("Unable to play feedback sound: %s", sound_path)
        finally:
            if opened:
                mci_send_string(f"close {alias}", None, 0, 0)
