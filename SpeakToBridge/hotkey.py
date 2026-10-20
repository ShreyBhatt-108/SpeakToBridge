from __future__ import annotations

import logging
import sys
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

    if key_token == "win" and modifiers == {"win"}:
        raise ValueError("The Windows key needs another modifier, such as Ctrl.")

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
        self._get_async_key_state = None

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
            if sys.platform == "win32":
                import ctypes
                self._get_async_key_state = ctypes.WinDLL("user32").GetAsyncKeyState
                self._get_async_key_state.argtypes = [ctypes.c_int]
                self._get_async_key_state.restype = ctypes.c_short
                # Take the physical snapshot inside the low-level hook, before
                # Windows updates the current key. Apply this event ourselves.
                # Returning False filters pynput delivery, not the OS keystroke.
                self._listener = keyboard.Listener(win32_event_filter=self._on_windows_event)
            else:
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

    @staticmethod
    def _token_vks(token: str) -> tuple[int, ...]:
        if token == "win":
            return (0x5B, 0x5C)
        if token.startswith("f") and token[1:].isdigit():
            return (0x70 + int(token[1:]) - 1,)
        return (ord(token.upper()),)

    def _on_windows_event(self, message, data):
        if message not in (0x100, 0x104, 0x101, 0x105):
            return False
        modifier_keys = {"ctrl": (0xA2, 0xA3), "alt": (0xA4, 0xA5),
                         "shift": (0xA0, 0xA1), "win": (0x5B, 0x5C)}
        vks = {vk for keys in modifier_keys.values() for vk in keys}
        for spec in (self._activation_spec, self._read_spec):
            vks.update(self._token_vks(spec.key_token))
        vks.add(data.vkCode)
        before = {vk: bool(self._get_async_key_state(vk) & 0x8000) for vk in vks}
        down = message in (0x100, 0x104)
        after = dict(before)
        after[data.vkCode] = down
        def chord(spec, state):
            return (all(any(state[vk] for vk in modifier_keys[modifier]) for modifier in spec.modifiers)
                    and any(state[vk] for vk in self._token_vks(spec.key_token)))
        # Recover a lost key-up (sleep, desktop switch or an intercepted event)
        # before deciding whether this is a fresh press or keyboard auto-repeat.
        if self._activation_down and not chord(self._activation_spec, before if down else after):
            self._activation_down = False
            self.hotkey_released.emit()
        if self._read_down and not chord(self._read_spec, before if down else after):
            self._read_down = False
        self._pressed_modifiers = {name for name, keys in modifier_keys.items() if any(after[vk] for vk in keys)}
        if down:
            self._on_press(keyboard.KeyCode.from_vk(data.vkCode))
        return False

    def _on_press(self, key) -> None:  # noqa: ANN001
        modifier = self._key_to_modifier(key)
        if modifier is not None:
            self._pressed_modifiers.add(modifier)

        if self._matches_activation(key) and not self._activation_down:
            self._activation_down = True
            self.hotkey_pressed.emit()
            return

        if self._matches_read(key) and not self._read_down:
            self._read_down = True
            self.read_hotkey_pressed.emit()
            return

    def _on_release(self, key) -> None:  # noqa: ANN001
        released_modifier = self._key_to_modifier(key)
        if self._should_release_activation(key, released_modifier):
            self._activation_down = False
            self.hotkey_released.emit()

        if self._should_release_read(key, released_modifier):
            self._read_down = False

        if released_modifier is not None:
            self._pressed_modifiers.discard(released_modifier)

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
        for modifier, codes in {"ctrl": (0x11, 0xA2, 0xA3), "alt": (0x12, 0xA4, 0xA5),
                                "shift": (0x10, 0xA0, 0xA1), "win": (0x5B, 0x5C)}.items():
            if vk in codes:
                return modifier
        return None

    def _matches_activation(self, key) -> bool:  # noqa: ANN001
        if not self._activation_spec.modifiers.issubset(self._pressed_modifiers):
            return False

        token = self._activation_spec.key_token
        if getattr(key, "vk", None) in self._token_vks(token):
            return True
        if token.startswith("f"):
            expected = getattr(keyboard.Key, token, None)
            return key == expected
        if token == "win":
            return self._key_to_modifier(key) == "win"
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char.lower() == token
        return False

    def _matches_read(self, key) -> bool:  # noqa: ANN001
        if not self._read_spec.modifiers.issubset(self._pressed_modifiers):
            return False
        token = self._read_spec.key_token
        if getattr(key, "vk", None) in self._token_vks(token):
            return True
        if token.startswith("f"):
            expected = getattr(keyboard.Key, token, None)
            return key == expected
        if token == "win":
            return self._key_to_modifier(key) == "win"
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char.lower() == token
        return False

    def _should_release_activation(self, key, released_modifier: str | None) -> bool:  # noqa: ANN001
        if not self._activation_down:
            return False
        if self._matches_activation(key):
            return True
        return (
            released_modifier is not None
            and released_modifier in self._activation_spec.modifiers
        )

    def _should_release_read(self, key, released_modifier: str | None) -> bool:  # noqa: ANN001
        if not self._read_down:
            return False
        if self._matches_read(key):
            return True
        return (
            released_modifier is not None
            and released_modifier in self._read_spec.modifiers
        )
