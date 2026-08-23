from __future__ import annotations

import logging
import sys
import threading
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from .config import AppConfig, ConfigStore
from .constants import APP_NAME, APP_VERSION, DEFAULT_ACTIVATION_HOTKEY, DEFAULT_READ_HOTKEY
from .controller import DictationController
from .hotkey import HoldHotkeyListener
from .logging_utils import configure_logging
from .model_storage import delete_cached_model, format_size, list_cached_models
from .paths import get_config_path, get_model_cache_dir, get_stats_path, get_word_bank_path
from .stats_store import LifetimeStats, StatsStore
from .ui import SettingsWindow
from .word_bank import WordBank


LOGGER = logging.getLogger(__name__)
_MUTEX_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_MUTEX_NAME = "Global\\SpeakToBridge_SingleInstance"
_single_instance_handle = None


def _acquire_single_instance_mutex():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD
    handle = kernel32.CreateMutexW(None, False, _SINGLE_INSTANCE_MUTEX_NAME)
    if not handle:
        return None, False
    already_running = kernel32.GetLastError() == _MUTEX_ALREADY_EXISTS
    return handle, already_running


class SpeakToBridgeRuntime(QObject):
    model_cache_entries_ready = Signal(object)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._config_store = ConfigStore(get_config_path())
        self._config: AppConfig = self._config_store.load()
        self._stats_store = StatsStore(get_stats_path())
        self._lifetime_stats: LifetimeStats = self._stats_store.load()
        self._word_bank = WordBank(get_word_bank_path())
        self._model_cache_dir = get_model_cache_dir()

        self._hotkey = HoldHotkeyListener()
        self._apply_saved_hotkey()
        self._window = SettingsWindow(
            initial_model=self._config.model_name,
            initial_hotkey=self._hotkey.activation_hotkey_display,
            initial_read_hotkey=self._hotkey.read_hotkey_display,
            initial_max_recording_seconds=self._config.max_recording_seconds,
        )
        self._controller = DictationController(
            config=self._config,
            model_cache_dir=self._model_cache_dir,
            word_bank=self._word_bank,
        )
        self._controller.set_activation_hotkey_display(self._hotkey.activation_hotkey_display)

        self._tray = QSystemTrayIcon(self)
        self._dictation_enabled = True
        self._total_words = 0
        self._last_words = 0
        self._total_clips = 0
        self._last_status_message = ""
        self._pending_model_name: str | None = None
        self._model_cache_refresh_generation = 0
        self._last_notification_message = ""
        self._model_ready_map: dict[str, bool] = {}
        self._setup_tray()
        self._wire_events()
        self._window.set_word_bank_entries(self._word_bank.get_entries())
        self._refresh_model_cache_list()
        self._window.set_word_stats(
            last_words=0,
            total_words=0,
            total_clips=0,
            lifetime_words=self._lifetime_stats.total_words,
            lifetime_clips=self._lifetime_stats.total_clips,
        )
        self._window.set_dictation_enabled(True)
        self._controller.set_enabled(True)
        self._window.set_model_status("Ready")
        self._window.set_active_model(self._config.model_name)
        self._set_status(f"Ready. Press {self._hotkey.activation_hotkey_display} to start or stop dictation.")
        self._sync_tray_state()
        self._hotkey.start()

    def _setup_tray(self) -> None:
        icon = self._app.style().standardIcon(QStyle.SP_MediaPlay)
        self._tray.setIcon(icon)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        open_action = menu.addAction("Open Settings")
        open_action.triggered.connect(self._window.showNormal)
        menu.addSeparator()
        self._settings_summary_action = menu.addAction("Settings Overview")
        self._settings_summary_action.setEnabled(False)
        self._model_action = menu.addAction(f"Model: {self._config.model_name}")
        self._model_action.setEnabled(False)
        self._activation_hotkey_action = menu.addAction(f"Dictation hotkey: {self._hotkey.activation_hotkey_display}")
        self._activation_hotkey_action.setEnabled(False)
        self._read_hotkey_action = menu.addAction(f"Read hotkey: {self._hotkey.read_hotkey_display}")
        self._read_hotkey_action.setEnabled(False)
        self._show_more_settings_action = menu.addAction("Show More Settings")
        self._show_more_settings_action.triggered.connect(self._toggle_advanced_settings)
        menu.addSeparator()
        self._toggle_dictation_action = menu.addAction("Disable Dictation")
        self._toggle_dictation_action.triggered.connect(self._toggle_dictation)
        self._read_last_action = menu.addAction("Read Last Transcript")
        self._read_last_action.triggered.connect(self._controller.read_last_transcript_aloud)
        menu.addSeparator()
        self._status_action = menu.addAction("Status: Ready")
        self._status_action.setEnabled(False)
        self._word_count_action = menu.addAction("Words: 0 total (0 last)")
        self._word_count_action.setEnabled(False)
        self._lifetime_word_count_action = menu.addAction(
            f"Lifetime: {self._lifetime_stats.total_words} words ({self._lifetime_stats.total_clips} clips)"
        )
        self._lifetime_word_count_action.setEnabled(False)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._request_shutdown)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _wire_events(self) -> None:
        self._window.model_apply_requested.connect(self._on_model_changed)
        self._window.model_cache_refresh_requested.connect(self._on_model_cache_refresh_requested)
        self._window.model_cache_delete_requested.connect(self._on_model_cache_delete_requested)
        self._window.hotkey_apply_requested.connect(self._on_hotkey_changed)
        self._window.read_hotkey_apply_requested.connect(self._on_read_hotkey_changed)
        self._window.recording_limit_apply_requested.connect(self._on_recording_limit_changed)
        self._window.word_bank_save_requested.connect(self._on_word_bank_save_requested)
        self._window.dictation_toggle_requested.connect(self._toggle_dictation)
        self._window.quit_requested.connect(self.shutdown)
        self._hotkey.hotkey_pressed.connect(self._on_hotkey_pressed)
        self._hotkey.read_hotkey_pressed.connect(self._on_read_hotkey_pressed)
        self._hotkey.listener_error.connect(self._on_error)

        self._controller.status_changed.connect(self._set_status)
        self._controller.error_occurred.connect(self._on_error)
        self._controller.transcript_ready.connect(self._on_transcript_ready)
        self._controller.recording_changed.connect(self._on_recording_changed)
        self._controller.model_preload_finished.connect(self._on_model_preload_finished)
        self.model_cache_entries_ready.connect(self._apply_model_cache_entries)

    def _on_model_changed(self, model_name: str) -> None:
        if model_name == self._config.model_name:
            self._set_status(f"Model unchanged: {model_name}.")
            self._window.focus_model_status()
            return
        if self._controller.is_recording:
            self._set_status("Stop recording before changing model.")
            self._window.focus_model_status()
            return
        if self._controller.is_busy or self._controller.is_preloading:
            self._set_status("Please wait for transcription to finish before changing model.")
            self._window.focus_model_status()
            return
        self._pending_model_name = model_name
        self._controller.preload_model_async(model_name)
        self._set_status(f"Model selected: {model_name}. Preparing model now...")
        self._window.focus_model_status()
        self._notify_user(f"Model selected: {model_name}. Preparing model...", QSystemTrayIcon.MessageIcon.Information, 1600)

    def _on_model_preload_finished(self, model_name: str, success: bool, message: str) -> None:
        if self._pending_model_name != model_name:
            return
        self._pending_model_name = None
        if success:
            self._config.model_name = model_name
            self._config_store.save(self._config)
            self._window.set_model_value(model_name)
            self._window.set_model_status(f"Ready: {model_name}")
            self._refresh_model_cache_list()
            self._window.set_active_model(model_name)
            self._sync_tray_state()
            self._notify_user(f"Model ready: {model_name}.", QSystemTrayIcon.MessageIcon.Information, 1600)
            return
        self._window.set_model_value(self._config.model_name)
        self._window.set_active_model(self._config.model_name)
        self._window.set_model_status(f"Failed. Still using {self._config.model_name}.")
        self._refresh_model_cache_list()
        short = message if len(message) <= 120 else f"{message[:117]}..."
        self._notify_user(
            f"Model change failed. Still using {self._config.model_name}. {short}",
            QSystemTrayIcon.MessageIcon.Warning,
            2500,
            always=True,
        )

    def _toggle_dictation(self) -> None:
        self._dictation_enabled = not self._dictation_enabled
        if self._dictation_enabled:
            self._controller.set_enabled(True)
            self._hotkey.start()
            self._toggle_dictation_action.setText("Disable Dictation")
            self._window.set_dictation_enabled(True)
            self._set_status(
                f"Dictation enabled. Press {self._hotkey.activation_hotkey_display} to start or stop dictation."
            )
        else:
            self._controller.set_enabled(False)
            if self._controller.is_recording:
                self._controller.cancel_recording()
            self._hotkey.stop()
            self._toggle_dictation_action.setText("Enable Dictation")
            self._window.set_dictation_enabled(False)
            self._set_status(
                f"Dictation disabled. {self._hotkey.activation_hotkey_display} will not start recording."
            )
        self._sync_tray_state()

    def _on_hotkey_changed(self, hotkey_text: str) -> None:
        try:
            display = self._hotkey.set_activation_hotkey(hotkey_text)
        except ValueError as exc:
            self._set_status(f"Invalid hotkey: {exc}")
            return
        self._config.activation_hotkey = hotkey_text
        self._controller.set_activation_hotkey_display(display)
        self._config_store.save(self._config)
        self._window.set_hotkey_value(display)
        self._activation_hotkey_action.setText(f"Dictation hotkey: {display}")
        hint = ""
        if display.upper().endswith(tuple(f"F{i}" for i in range(1, 13))):
            hint = " If this is Windows in Parallels on Mac, enable standard F-keys or use a letter/number key."
        self._set_status(f"Activation hotkey updated to {display}.{hint}")
        self._notify_user(f"Activation hotkey updated to {display}.", QSystemTrayIcon.MessageIcon.Information, 1800)

    def _on_recording_limit_changed(self, seconds: int) -> None:
        self._config.max_recording_seconds = seconds
        self._config_store.save(self._config)
        self._controller.set_max_recording_seconds(seconds)
        self._set_status(
            f"Maximum recording length updated to {seconds} seconds. "
            "Longer recordings will stop and begin transcription automatically."
        )

    def _on_read_hotkey_changed(self, hotkey_text: str) -> None:
        try:
            display = self._hotkey.set_read_hotkey(hotkey_text)
        except ValueError as exc:
            self._set_status(f"Invalid read-aloud hotkey: {exc}")
            return
        self._config.read_hotkey = hotkey_text
        self._config_store.save(self._config)
        self._window.set_read_hotkey_value(display)
        self._read_hotkey_action.setText(f"Read hotkey: {display}")
        hint = ""
        if display.upper().endswith(tuple(f"F{i}" for i in range(1, 13))):
            hint = " If this is Windows in Parallels on Mac, enable standard F-keys or use a letter/number key."
        self._set_status(f"Read-aloud hotkey updated to {display}.{hint}")

    def _on_recording_changed(self, recording: bool) -> None:
        # Keep frequent dictation state changes in the status field only.
        _ = recording

    def _on_word_bank_save_requested(self, entries) -> None:  # noqa: ANN001
        try:
            self._word_bank.save_entries(entries)
            self._window.set_word_bank_entries(self._word_bank.get_entries())
            self._set_status("Word bank saved. Future transcripts will use these corrections.")
        except Exception as exc:
            self._on_error(f"Unable to save word bank ({exc}).")

    def _on_model_cache_refresh_requested(self) -> None:
        self._refresh_model_cache_list()

    def _on_model_cache_delete_requested(self, folder_name: str) -> None:
        if self._controller.is_preloading:
            self._set_status("Please wait for the model change to finish before deleting cached models.")
            self._window.focus_model_status()
            return
        active_folder = f"models--Systran--faster-whisper-{self._config.model_name}"
        if folder_name == active_folder:
            self._set_status("Cannot delete the currently selected model.")
            self._window.focus_model_status()
            return
        try:
            removed = delete_cached_model(self._model_cache_dir, folder_name)
            if removed:
                self._refresh_model_cache_list()
                self._set_status("Selected cached model deleted.")
                self._window.focus_model_status()
            else:
                self._set_status("Selected cached model was not found.")
                self._window.focus_model_status()
        except Exception as exc:
            LOGGER.exception("Cached model delete failed")
            self._on_error(f"Unable to delete selected cached model ({exc}).")

    def _on_hotkey_pressed(self) -> None:
        if not self._dictation_enabled:
            self._set_status(
                f"Dictation disabled. {self._hotkey.activation_hotkey_display} will not start recording."
            )
            return
        if self._controller.is_preloading:
            model_name = self._pending_model_name or self._config.model_name
            self._set_status(
                f"Model '{model_name}' is still preparing/downloading. Hotkey is paused until model is ready."
            )
            self._window.focus_model_status()
            return
        if self._controller.is_busy:
            self._set_status("Please wait. Transcription in progress.")
            return
        if self._controller.is_recording:
            self._controller.stop_recording_and_transcribe()
            return
        self._controller.start_recording()

    def _on_read_hotkey_pressed(self) -> None:
        if not self._dictation_enabled:
            self._set_status("Dictation disabled. Read-aloud shortcut will not run.")
            return
        self._controller.read_last_transcript_aloud()

    def _on_transcript_ready(self, text: str) -> None:
        words = self._count_words(text)
        self._last_words = words
        self._total_words += words
        self._total_clips += 1
        self._lifetime_stats.total_words += words
        self._lifetime_stats.total_clips += 1
        self._stats_store.save(self._lifetime_stats)
        self._window.set_word_stats(
            last_words=self._last_words,
            total_words=self._total_words,
            total_clips=self._total_clips,
            lifetime_words=self._lifetime_stats.total_words,
            lifetime_clips=self._lifetime_stats.total_clips,
        )
        self._word_count_action.setText(f"Words: {self._total_words} total ({self._last_words} last)")
        self._lifetime_word_count_action.setText(
            f"Lifetime: {self._lifetime_stats.total_words} words ({self._lifetime_stats.total_clips} clips)"
        )
        self._set_status(
            f"Transcript ready: {self._last_words} words. "
            f"Total dictated: {self._total_words} words in {self._total_clips} clips."
        )

    def _on_error(self, message: str) -> None:
        self._controller.play_failure_feedback()
        self._set_status(message)
        self._notify_user(message, QSystemTrayIcon.MessageIcon.Critical, 2500, always=True)

    def _set_status(self, message: str) -> None:
        if message == self._last_status_message:
            return
        self._last_status_message = message
        model_status = self._extract_model_status(message)
        if model_status is not None:
            self._window.set_model_status(model_status)
        self._window.set_status(message)
        if hasattr(self, "_status_action"):
            short = message if len(message) <= 70 else f"{message[:67]}..."
            self._status_action.setText(f"Status: {short}")
        LOGGER.info("Status: %s", message)

    def _extract_model_status(self, message: str) -> str | None:
        lower = message.lower()
        if "downloading model" in lower:
            return "Downloading model..."
        if "loading model" in lower:
            return "Loading model from cache..."
        if "preparing selected model" in lower or "model selected" in lower:
            return "Preparing model..."
        if lower.startswith("model ready"):
            return "Ready"
        if "model preload failed" in lower:
            return "Failed"
        if "model unchanged" in lower:
            return "Ready"
        return None

    def _notify_user(
        self,
        text: str,
        icon: QSystemTrayIcon.MessageIcon,
        timeout_ms: int,
        always: bool = False,
    ) -> None:
        # Frequent info popups are disruptive with screen readers; only surface key events.
        if not always and icon == QSystemTrayIcon.MessageIcon.Information:
            return
        if text == self._last_notification_message:
            return
        self._last_notification_message = text
        self._tray.showMessage(APP_NAME, text, icon, timeout_ms)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()

    def show(self) -> None:
        self._window.show()
        self._sync_tray_state()

    def shutdown(self) -> None:
        self._hotkey.stop()
        self._controller.shutdown()
        self._tray.hide()
        self._app.quit()

    def _request_shutdown(self) -> None:
        if self._window.confirm_pending_changes():
            self.shutdown()

    @staticmethod
    def _count_words(text: str) -> int:
        return len([token for token in text.strip().split() if token])

    def _apply_saved_hotkey(self) -> None:
        try:
            self._hotkey.set_activation_hotkey(self._config.activation_hotkey)
        except ValueError:
            self._config.activation_hotkey = DEFAULT_ACTIVATION_HOTKEY
            self._hotkey.set_activation_hotkey(self._config.activation_hotkey)
            self._config_store.save(self._config)
        try:
            self._hotkey.set_read_hotkey(self._config.read_hotkey)
        except ValueError:
            self._config.read_hotkey = DEFAULT_READ_HOTKEY
            self._hotkey.set_read_hotkey(self._config.read_hotkey)
            self._config_store.save(self._config)

    def _toggle_advanced_settings(self) -> None:
        self._window.toggle_advanced_settings()
        self._sync_tray_state()

    def _sync_tray_state(self) -> None:
        self._model_action.setText(f"Model: {self._config.model_name}")
        self._activation_hotkey_action.setText(f"Dictation hotkey: {self._hotkey.activation_hotkey_display}")
        self._read_hotkey_action.setText(f"Read hotkey: {self._hotkey.read_hotkey_display}")
        self._show_more_settings_action.setText(
            "Hide More Settings" if self._window.is_advanced_settings_visible() else "Show More Settings"
        )
        self._lifetime_word_count_action.setText(
            f"Lifetime: {self._lifetime_stats.total_words} words ({self._lifetime_stats.total_clips} clips)"
        )
        self._tray.setToolTip(
            f"{APP_NAME} | Model: {self._config.model_name} | Lifetime words: {self._lifetime_stats.total_words}"
        )

    def _refresh_model_cache_list(self) -> None:
        self._model_cache_refresh_generation += 1
        generation = self._model_cache_refresh_generation
        self._window.set_model_cache_refreshing(True)
        worker = threading.Thread(target=self._load_model_cache_entries, args=(generation,), daemon=True)
        worker.start()

    def _load_model_cache_entries(self, generation: int) -> None:
        rows: list[tuple[str, str, str, bool]] = []
        error = ""
        try:
            models = list_cached_models(self._model_cache_dir)
            for item in models:
                status = "ready" if item.ready else "incomplete"
                label = f"{item.model_name} ({format_size(item.size_bytes)}, {status})"
                rows.append((label, item.folder_name, item.model_name, item.ready))
        except Exception as exc:
            LOGGER.exception("Cached model refresh failed")
            error = str(exc)
        self.model_cache_entries_ready.emit((generation, rows, error))

    def _apply_model_cache_entries(self, payload: object) -> None:
        generation, rows, error = payload
        if generation != self._model_cache_refresh_generation:
            return
        ready_map: dict[str, bool] = {}
        for _, _, model_name, ready in rows:
            ready_map[model_name] = ready
        self._model_ready_map = ready_map
        self._window.set_model_cache_entries(rows)
        self._window.set_model_choices_availability(self._model_ready_map, self._config.model_name)
        self._window.set_model_cache_refreshing(False)
        if error:
            self._set_status(f"Unable to refresh cached model list ({error}).")


def run() -> int:
    configure_logging()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(APP_VERSION)
    app = QApplication(sys.argv)
    global _single_instance_handle  # noqa: PLW0603
    _single_instance_handle, already_running = _acquire_single_instance_mutex()
    if already_running:
        QMessageBox.information(
            None,
            APP_NAME,
            f"{APP_NAME} is already running. Open it from the system tray.",
        )
        return 0
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "System tray is not available on this system.")
        return 1

    runtime = SpeakToBridgeRuntime(app)
    runtime.show()
    return app.exec()
