from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from ctypes import wintypes
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class SoundFeedbackPlayer:
    """Play short MP3 cues sequentially without blocking the Qt event loop."""

    def __init__(self) -> None:
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True, name="severus-sound-feedback")
        self._worker.start()

    def play(self, sound_path: Path) -> None:
        if sound_path.exists():
            self._queue.put(sound_path)

    def close(self) -> None:
        self._queue.put(None)

    def _run(self) -> None:
        sequence = 0
        while True:
            sound_path = self._queue.get()
            if sound_path is None:
                return
            sequence += 1
            self._play_blocking(sound_path, f"severuscue{sequence}")

    @staticmethod
    def _play_blocking(sound_path: Path, alias: str) -> None:
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

            result = mci_send_string(f"play {alias} from 0", None, 0, 0)
            if result != 0:
                raise OSError(f"MCI play failed with code {result}")
            time.sleep(duration_seconds + 0.1)
        except Exception:
            LOGGER.exception("Unable to play feedback sound: %s", sound_path)
        finally:
            if opened:
                mci_send_string(f"close {alias}", None, 0, 0)
