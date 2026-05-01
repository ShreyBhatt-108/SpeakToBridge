from __future__ import annotations

import logging
import threading
import time

import pyperclip
from pynput.keyboard import Controller, Key


LOGGER = logging.getLogger(__name__)


class TextInserter:
    def __init__(self) -> None:
        self._keyboard = Controller()
        self._clipboard_lock = threading.Lock()
        self._insert_guard_lock = threading.Lock()
        self._last_insert_text = ""
        self._last_insert_ts = 0.0
        self._duplicate_guard_window_s = 1.5

    def insert(self, text: str) -> tuple[bool, str]:
        normalized = text.strip()
        if not normalized:
            return False, "Transcription returned empty text."
        with self._insert_guard_lock:
            now = time.monotonic()
            if (
                normalized == self._last_insert_text
                and (now - self._last_insert_ts) <= self._duplicate_guard_window_s
            ):
                return True, "Duplicate insert ignored."
            self._last_insert_text = normalized
            self._last_insert_ts = now

        original_clipboard: str | None = None
        try:
            with self._clipboard_lock:
                # Preserve user's clipboard content and restore it after paste.
                original_clipboard = self._clipboard_read_with_retry()
                self._clipboard_write_with_retry(text)
                # Allow clipboard update to settle before paste.
                time.sleep(0.06)
                with self._keyboard.pressed(Key.ctrl):
                    self._keyboard.press("v")
                    self._keyboard.release("v")
                # Give target app a moment to consume clipboard before restore.
                time.sleep(0.09)
                if original_clipboard is not None:
                    self._clipboard_write_with_retry(original_clipboard)
            return True, "Transcript inserted into focused app."
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Insert via paste failed")
            try:
                if original_clipboard is not None:
                    self._clipboard_write_with_retry(original_clipboard)
                else:
                    self._clipboard_write_with_retry(text)
            except Exception:
                pass
            return False, f"Insert failed ({exc}). Transcript copied to clipboard."

    @staticmethod
    def _clipboard_read_with_retry(attempts: int = 6, sleep_s: float = 0.03) -> str:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                return pyperclip.paste()
            except Exception as exc:  # pragma: no cover
                last_error = exc
                time.sleep(sleep_s)
        if last_error is not None:
            raise last_error
        return ""

    @staticmethod
    def _clipboard_write_with_retry(value: str, attempts: int = 6, sleep_s: float = 0.03) -> None:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                pyperclip.copy(value)
                return
            except Exception as exc:  # pragma: no cover
                last_error = exc
                time.sleep(sleep_s)
        if last_error is not None:
            raise last_error
