from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Set

from PySide6.QtCore import QObject, Signal
from pynput import keyboard


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: frozenset[str]
    key_token: str
    display: str


def parse_hotkey_spec(spec: str) -> HotkeySpec:
    raw_parts = [part.strip().lower() for part in spec.split("+") if part.strip()]
    if len(raw_parts) < 2:
        raise ValueError("Hotkey must include at least one modifier and one key.")

    modifier_aliases = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "win": "win",
        "windows": "win",
    }
    modifiers: set[str] = set()
    for token in raw_parts[:-1]:
        mapped = modifier_aliases.get(token)
        if mapped is None:
            raise ValueError(f"Unsupported modifier: {token}")
        modifiers.add(mapped)
    if not modifiers:
        raise ValueError("Hotkey must include at least one modifier.")

    key_token = raw_parts[-1]
    if key_token in ("win", "windows"):
        key_token = "win"
    elif key_token.startswith("f") and key_token[1:].isdigit():
        fn = int(key_token[1:])
        if fn < 1 or fn > 12:
            raise ValueError("Function key must be between F1 and F12.")
    elif len(key_token) == 1 and key_token.isalnum():
        pass
    else:
        raise ValueError("Key must be F1-F12, Windows key, A-Z, or 0-9.")

    ordered_modifiers = [m for m in ("ctrl", "alt", "shift", "win") if m in modifiers]
    label_map = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
    display = "+".join([label_map[m] for m in ordered_modifiers] + [key_token.upper()])
    return HotkeySpec(modifiers=frozenset(modifiers), key_token=key_token, display=display)


class HoldHotkeyListener(QObject):
    hotkey_pressed = Signal()
    hotkey_released = Signal()
    read_hotkey_pressed = Signal()
    listener_error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._listener: keyboard.Listener | None = None
        self._pressed_modifiers: Set[str] = set()
        self._activation_spec = parse_hotkey_spec("ctrl+f9")
        self._read_spec = parse_hotkey_spec("ctrl+f8")
        self._activation_down = False
        self._read_down = False

    @property
    def activation_hotkey_display(self) -> str:
        return self._activation_spec.display

    def set_activation_hotkey(self, spec_text: str) -> str:
        parsed = parse_hotkey_spec(spec_text)
        self._activation_spec = parsed
        self._activation_down = False
        return parsed.display

    @property
    def read_hotkey_display(self) -> str:
        return self._read_spec.display

    def set_read_hotkey(self, spec_text: str) -> str:
        parsed = parse_hotkey_spec(spec_text)
        self._read_spec = parsed
        self._read_down = False
        return parsed.display

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
            LOGGER.info("Global hotkey listener started")
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Failed to start hotkey listener")
            self.listener_error.emit(
                f"Unable to start global hotkey listener ({exc}). "
                "Another app may be intercepting the hotkey."
            )

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        self._pressed_modifiers.clear()
        self._activation_down = False
        self._read_down = False
        if listener is not None:
            listener.stop()

    def _on_press(self, key) -> None:  # noqa: ANN001
        if self._matches_activation(key) and not self._activation_down:
            self._activation_down = True
            self.hotkey_pressed.emit()
            return

        if self._matches_read(key) and not self._read_down:
            self._read_down = True
            self.read_hotkey_pressed.emit()
            return

        modifier = self._key_to_modifier(key)
        if modifier is not None:
            self._pressed_modifiers.add(modifier)

    def _on_release(self, key) -> None:  # noqa: ANN001
        if self._matches_activation(key) and self._activation_down:
            self._activation_down = False
            self.hotkey_released.emit()
            return

        if self._matches_read(key) and self._read_down:
            self._read_down = False
            return

        modifier = self._key_to_modifier(key)
        if modifier is not None:
            self._pressed_modifiers.discard(modifier)

    @staticmethod
    def _key_to_modifier(key) -> str | None:  # noqa: ANN001
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "alt"
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "shift"
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            return "win"
        vk = getattr(key, "vk", None)
        if vk in (91, 92):
            return "win"
        return None

    def _matches_activation(self, key) -> bool:  # noqa: ANN001
        if self._activation_spec.modifiers != frozenset(self._pressed_modifiers):
            return False

        token = self._activation_spec.key_token
        if token.startswith("f"):
            expected = getattr(keyboard.Key, token, None)
            return key == expected
        if token == "win":
            return self._key_to_modifier(key) == "win"
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char.lower() == token
        return False

    def _matches_read(self, key) -> bool:  # noqa: ANN001
        if self._read_spec.modifiers != frozenset(self._pressed_modifiers):
            return False
        token = self._read_spec.key_token
        if token.startswith("f"):
            expected = getattr(keyboard.Key, token, None)
            return key == expected
        if token == "win":
            return self._key_to_modifier(key) == "win"
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char.lower() == token
        return False
