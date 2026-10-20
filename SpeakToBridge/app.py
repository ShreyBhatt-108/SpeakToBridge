from __future__ import annotations

import logging
import json
from pathlib import Path
import sys
import threading
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from .config import AppConfig, ConfigStore
from .constants import APP_NAME, APP_VERSION, DEFAULT_ACTIVATION_HOTKEY, DEFAULT_READ_HOTKEY
from .controller import DictationController
from .hotkey import HoldHotkeyListener
from .logging_utils import configure_logging
from .model_storage import delete_cached_model, format_size, list_cached_models
from .paths import get_app_data_dir, get_config_path, get_model_cache_dir, get_stats_path, get_word_bank_path
from .stats_store import LifetimeStats, StatsStore
from .ui import SettingsWindow
from .word_bank import WordBank


LOGGER = logging.getLogger(__name__)
_MUTEX_ALREADY_EXISTS = 183
_SINGLE_INSTANCE_MUTEX_NAME = "Global\\SpeakToBridge_SingleInstance"
_UNINSTALL_SHUTDOWN_EVENT_NAME = "Global\\SpeakToBridge_ShutdownForUninstall"
_EVENT_MODIFY_STATE = 0x0002
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_ABANDONED = 0x00000080
_single_instance_handle = None


def _acquire_single_instance_mutex():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD
    # Owning the mutex lets the uninstall helper wait until this process has
    # fully exited before Inno Setup starts removing installed files.
    handle = kernel32.CreateMutexW(None, True, _SINGLE_INSTANCE_MUTEX_NAME)
    if not handle:
        return None, False
    already_running = kernel32.GetLastError() == _MUTEX_ALREADY_EXISTS
    return handle, already_running


def _create_uninstall_shutdown_event():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32.CreateEventW(None, False, False, _UNINSTALL_SHUTDOWN_EVENT_NAME)


def _signal_shutdown_for_uninstall() -> int:
    """Ask the running instance to exit, then wait until it releases its mutex."""
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    event_handle = kernel32.OpenEventW(
        _EVENT_MODIFY_STATE, False, _UNINSTALL_SHUTDOWN_EVENT_NAME
    )
    if not event_handle:
        return 0

    mutex_handle = kernel32.OpenMutexW(_SYNCHRONIZE, False, _SINGLE_INSTANCE_MUTEX_NAME)
    try:
        if not kernel32.SetEvent(event_handle):
            return 1
        if mutex_handle:
            wait_result = kernel32.WaitForSingleObject(mutex_handle, 10_000)
            # An owned mutex becomes abandoned when its process exits. That is
            # the expected success result for this process-lifetime mutex.
            if wait_result not in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
                return 1
        return 0
    finally:
        if mutex_handle:
            kernel32.CloseHandle(mutex_handle)
        kernel32.CloseHandle(event_handle)


class SpeakToBridgeRuntime(QObject):
    model_cache_entries_ready = Signal(object)
    model_cache_delete_finished = Signal(object)
    meeting_entry_ready = Signal(object)
    meeting_status_changed = Signal(str)
    meeting_finished = Signal(str, object)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._config_store = ConfigStore(get_config_path())
        self._config: AppConfig = self._config_store.load()
        from .wsl_whisper import wsl_enabled
        LOGGER.info("Application data directory: %s; WSL configured: %s", get_config_path().parent, wsl_enabled())
        self._stats_store = StatsStore(get_stats_path())
        self._lifetime_stats: LifetimeStats = self._stats_store.load()
        self._word_bank = WordBank(get_word_bank_path())
        self._model_cache_dir = get_model_cache_dir()
        self._model_cache_delete_in_progress = False
        self._meeting_session = None
        self._meeting_store = None
        self._meeting_root = get_app_data_dir() / "meetings"
        self._quit_after_meeting = False
        self._meeting_finishing = False

        self._hotkey = HoldHotkeyListener()
        self._apply_saved_hotkey()
        self._window = SettingsWindow(
            initial_model=self._config.model_name,
            initial_hotkey=self._hotkey.activation_hotkey_display,
            initial_read_hotkey=self._hotkey.read_hotkey_display,
            initial_max_recording_seconds=self._config.max_recording_seconds,
            initial_sound_effects_enabled=self._config.sound_effects_enabled,
            initial_runtime_mode=self._config.runtime_mode,
        )
        self._controller = DictationController(
            config=self._config,
            model_cache_dir=self._model_cache_dir,
            word_bank=self._word_bank,
        )
        self._controller.set_activation_hotkey_display(self._hotkey.activation_hotkey_display)

        self._uninstall_shutdown_event = _create_uninstall_shutdown_event()
        self._uninstall_shutdown_timer = QTimer(self)
        self._uninstall_shutdown_timer.setInterval(200)
        self._uninstall_shutdown_timer.timeout.connect(self._check_uninstall_shutdown_request)
        self._uninstall_shutdown_timer.start()

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
        self._window.set_model_status("Not loaded yet")
        self._window.set_active_model(self._config.model_name)
        self._set_status(f"Ready. Press {self._hotkey.activation_hotkey_display} to start or stop dictation.")
        self._sync_tray_state()
        self._hotkey.start()
        self._refresh_meeting_history()
        QTimer.singleShot(0, self._prepare_startup_model)

    def _prepare_startup_model(self) -> None:
        if not self._dictation_enabled or self._controller.is_recording or self._controller.is_busy:
            return
        self._pending_model_name = self._config.model_name
        self._controller.preload_model_async()

    def _meeting_can_start(self) -> bool:
        if self._meeting_session is not None:
            return False
        if (self._controller.is_recording or self._controller.is_busy or self._controller.is_preloading
                or self._model_cache_delete_in_progress):
            self._set_status("Wait for the current recording or model preparation to finish.")
            return False
        return True

    def _start_meeting(self, title: str, source: str, keep_audio: bool) -> None:
        self._begin_meeting(title, source, keep_audio)

    def _import_meeting(self, path: str, title: str, keep_audio: bool) -> None:
        self._begin_meeting(title, "file", keep_audio, path)

    def _begin_meeting(self, title, source, keep_audio, audio_file=None) -> None:
        if not self._meeting_can_start():
            return
        from .meetings import MeetingSession, MeetingStore
        panel = self._window.meeting_panel
        panel.flush_notes()
        try:
            store = MeetingStore.create(self._meeting_root, title, source, keep_audio)
        except Exception as exc:
            LOGGER.exception("Could not create meeting storage")
            self._on_error(f"Could not save a new meeting ({exc}).")
            return
        self._meeting_store = store
        panel.set_document(*store.load())
        session = MeetingSession(
            self._controller._engine, store,
            lambda entry: self.meeting_entry_ready.emit((str(store.folder), entry)),
            self.meeting_status_changed.emit, self.meeting_finished.emit,
            transform=self._word_bank.apply, model_cache_dir=self._model_cache_dir,
        )
        self._meeting_session = session
        self._meeting_finishing = False
        panel.set_active(True)
        self._window.mode_tabs.setCurrentIndex(1)
        try:
            session.start(source, audio_file)
        except Exception as exc:
            self._meeting_session = None
            panel.set_active(False)
            store.update(status="needs_attention", errors=[str(exc)])
            self._on_error(f"Could not start meeting ({exc}).")
        self._refresh_meeting_history()

    def _stop_meeting(self) -> None:
        if self._meeting_session is None:
            return
        self._meeting_finishing = True
        self._meeting_session.stop()
        self._window.meeting_panel.set_active(True, finishing=True)
        self._window.meeting_panel.status.setText("Stopping capture and finishing the transcript...")

    def _on_meeting_entry(self, payload) -> None:
        folder, entry = payload
        if self._meeting_store is not None and str(self._meeting_store.folder) == folder:
            self._window.meeting_panel.append_entry(entry)
            self._window.set_last_transcription_backend(self._controller.runtime_description)

    def _on_meeting_finished(self, folder: str, errors: object) -> None:
        self._meeting_session = None
        self._meeting_finishing = False
        self._window.meeting_panel.flush_notes()
        self._window.meeting_panel.set_active(False)
        if self._meeting_store is not None:
            ai_notes=self._meeting_store.folder / "ai-notes.md"
            metadata=json.loads((self._meeting_store.folder / "meeting.json").read_text(encoding="utf-8"))
            if ai_notes.is_file() and metadata.get("notes_status") == "ready":
                self._window.meeting_panel.append_generated_notes(ai_notes.read_text(encoding="utf-8"))
        self._refresh_model_cache_list()
        message = "Meeting saved." if not errors else "Meeting saved. Some audio needs attention; see the log and saved meeting folder."
        self._window.meeting_panel.status.setText(message)
        self._set_status(message)
        self._refresh_meeting_history()
        if self._quit_after_meeting:
            self.shutdown()

    def _regenerate_meeting_notes(self) -> None:
        if self._meeting_store is None or not self._meeting_can_start():
            return
        from .meetings import MeetingSession
        store=self._meeting_store
        self._window.meeting_panel.flush_notes()
        session=MeetingSession(self._controller._engine,store,lambda entry:None,
                               self.meeting_status_changed.emit,self.meeting_finished.emit,
                               model_cache_dir=self._model_cache_dir)
        self._meeting_session=session
        self._window.meeting_panel.set_active(True,finishing=True)
        session.start("notes")

    def _save_meeting_notes(self, notes: str) -> None:
        if self._meeting_store is not None:
            try:
                self._meeting_store.save_notes(notes)
            except Exception as exc:
                LOGGER.exception("Meeting notes save failed")
                self._on_error(f"Could not save meeting notes ({exc}).")

    def _open_meeting(self, folder: str) -> None:
        if not folder or self._meeting_session is not None:
            return
        from .meetings import MeetingStore
        path = Path(folder)
        if path.is_symlink() or path.is_junction() or path.resolve().parent != self._meeting_root.resolve():
            self._on_error("Invalid saved meeting selection.")
            return
        try:
            self._window.meeting_panel.flush_notes()
            store = MeetingStore(path)
            document = store.load()
            self._meeting_store = store
            self._window.meeting_panel.set_document(*document)
            self._window.meeting_panel.status.setText("Saved meeting opened.")
        except Exception as exc:
            LOGGER.exception("Could not open meeting")
            self._on_error(f"Could not open meeting ({exc}).")

    def _export_meeting(self, path: str) -> None:
        if self._meeting_store is None:
            return
        try:
            self._window.meeting_panel.flush_notes()
            Path(path).write_text(self._meeting_store.export_markdown(), encoding="utf-8")
            self._window.meeting_panel.status.setText("Notes and transcript exported.")
        except Exception as exc:
            LOGGER.exception("Meeting export failed")
            self._on_error(f"Could not export meeting ({exc}).")

    def _refresh_meeting_history(self) -> None:
        from .meetings import MeetingStore
        items = []
        if self._meeting_root.is_dir():
            for folder in sorted(self._meeting_root.iterdir(), reverse=True):
                if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
                    continue
                try:
                    metadata = json.loads((folder / "meeting.json").read_text(encoding="utf-8"))
                    items.append((metadata["created_at"][:16] + " — " + metadata["title"], str(folder)))
                except (OSError, ValueError, KeyError):
                    LOGGER.warning("Could not read saved meeting metadata: %s", folder.name)
                if len(items) >= 100:
                    break
        self._window.meeting_panel.set_history(items)

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
        self._word_count_action = menu.addAction("Session: 0 words (0 last)")
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
        panel = self._window.meeting_panel
        panel.start_requested.connect(self._start_meeting)
        panel.stop_requested.connect(self._stop_meeting)
        panel.import_requested.connect(self._import_meeting)
        panel.open_saved_requested.connect(self._open_meeting)
        panel.notes_changed.connect(self._save_meeting_notes)
        panel.export_requested.connect(self._export_meeting)
        panel.generate_notes_requested.connect(self._regenerate_meeting_notes)
        self.meeting_entry_ready.connect(self._on_meeting_entry)
        self.meeting_status_changed.connect(panel.status.setText)
        self.meeting_finished.connect(self._on_meeting_finished)
        self._window.model_apply_requested.connect(self._on_model_changed)
        self._window.model_cache_refresh_requested.connect(self._on_model_cache_refresh_requested)
        self._window.model_cache_delete_requested.connect(self._on_model_cache_delete_requested)
        self.model_cache_delete_finished.connect(self._finish_model_cache_delete)
        self._window.hotkey_apply_requested.connect(self._on_hotkey_changed)
        self._window.read_hotkey_apply_requested.connect(self._on_read_hotkey_changed)
        self._window.recording_limit_apply_requested.connect(self._on_recording_limit_changed)
        self._window.sound_effects_changed.connect(self._on_sound_effects_changed)
        self._window.runtime_apply_requested.connect(self._on_runtime_changed)
        self._window.word_bank_save_requested.connect(self._on_word_bank_save_requested)
        self._window.dictation_toggle_requested.connect(self._toggle_dictation)
        self._window.microphone_test_start_requested.connect(self._on_microphone_test_start)
        self._window.microphone_test_stop_requested.connect(self._on_microphone_test_stop)
        self._window.quit_requested.connect(self.shutdown)
        self._hotkey.hotkey_pressed.connect(self._on_hotkey_pressed)
        self._hotkey.read_hotkey_pressed.connect(self._on_read_hotkey_pressed)
        self._hotkey.listener_error.connect(self._on_error)

        self._controller.runtime_changed.connect(self._window.set_loaded_backend)
        self._controller.transcription_backend_changed.connect(self._window.set_last_transcription_backend)
        self._controller.status_changed.connect(self._set_status)
        self._controller.error_occurred.connect(self._on_error)
        self._controller.transcript_ready.connect(self._on_transcript_ready)
        self._controller.recording_changed.connect(self._on_recording_changed)
        self._controller.model_preload_finished.connect(self._on_model_preload_finished)
        self._controller.microphone_test_finished.connect(self._on_microphone_test_finished)
        self.model_cache_entries_ready.connect(self._apply_model_cache_entries)

    def _on_model_changed(self, model_name: str) -> None:
        if getattr(self, "_meeting_session", None) is not None:
            self._set_status("Finish the meeting before using dictation or changing its model.")
            return
        if getattr(self, "_model_cache_delete_in_progress", False):
            self._set_status("Wait for model deletion to finish.")
            return
        if model_name == self._config.model_name and self._controller.runtime_description != "Not loaded yet":
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

    def _on_runtime_changed(self, runtime_mode: str) -> None:
        if getattr(self, "_meeting_session", None) is not None:
            self._set_status("Finish the meeting before using dictation or changing its model.")
            return
        if getattr(self, "_model_cache_delete_in_progress", False):
            self._set_status("Wait for model deletion to finish.")
            return
        from .config import ALLOWED_RUNTIME_MODES

        if runtime_mode not in ALLOWED_RUNTIME_MODES:
            return
        if self._controller.is_recording or self._controller.is_busy or self._controller.is_preloading:
            self._set_status("Finish the current recording or processing task before changing device.")
            self._window.runtime_combo.setCurrentIndex(
                self._window.runtime_combo.findData(self._config.runtime_mode)
            )
            return
        self._controller.set_runtime(runtime_mode)
        self._config.runtime_mode = runtime_mode
        self._config_store.save(self._config)
        self._pending_model_name = self._config.model_name
        self._controller.preload_model_async()
        self._set_status("Processing device saved. Preparing selected model...")
        self._refresh_model_cache_list()

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

    def _on_sound_effects_changed(self, enabled: bool) -> None:
        self._config.sound_effects_enabled = enabled
        self._controller.set_sound_effects_enabled(enabled)
        self._config_store.save(self._config)
        state = "enabled" if enabled else "disabled"
        self._set_status(
            f"Sound effects {state}. Runtime Status will continue to provide text feedback."
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
        if getattr(self, "_meeting_session", None) is not None:
            self._set_status("Finish the meeting before using dictation or changing its model.")
            return
        if (getattr(self, "_model_cache_delete_in_progress", False)
                or self._controller.is_preloading or self._controller.is_busy or self._controller.is_recording):
            self._set_status("Finish the current task before deleting a model.")
            return
        from .model_storage import cached_model_name
        try:
            if cached_model_name(folder_name) == self._config.model_name:
                self._set_status("Select another model before deleting this one.")
                self._window.focus_model_status()
                return
        except ValueError:
            self._on_error("Invalid model selection.")
            return
        self._model_cache_delete_in_progress = True
        self._window.set_model_cache_deleting(True)
        threading.Thread(target=self._delete_model_cache_worker, args=(folder_name,), daemon=True).start()

    def _delete_model_cache_worker(self, folder_name: str) -> None:
        try:
            removed = delete_cached_model(self._model_cache_dir, folder_name)
            result = (removed, "")
        except Exception as exc:
            LOGGER.exception("Cached model delete failed")
            result = (False, str(exc))
        self.model_cache_delete_finished.emit(result)

    def _finish_model_cache_delete(self, result: object) -> None:
        removed, error = result
        self._model_cache_delete_in_progress = False
        self._window.set_model_cache_deleting(False)
        self._refresh_model_cache_list()
        if error:
            self._on_error("Could not delete model. See the log for details.")
        else:
            self._set_status("Model deleted." if removed else "Model not found.")
        self._window.focus_model_status()

    def _on_hotkey_pressed(self) -> None:
        if getattr(self, "_meeting_session", None) is not None:
            self._set_status("Finish the meeting before using dictation or changing its model.")
            return
        # Stopping an existing dictation must never be gated by preparation.
        if self._controller.is_recording and not self._controller.is_microphone_test_recording:
            self._controller.stop_recording_and_transcribe()
            return
        if getattr(self, "_model_cache_delete_in_progress", False):
            self._set_status("Wait for model deletion to finish.")
            return
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
        if self._controller.is_microphone_test_recording:
            self._set_status("Microphone test is recording. Use Stop and Analyze in Microphone Check.")
            return
        if self._controller.is_recording:
            self._controller.stop_recording_and_transcribe()
            return
        self._controller.start_recording()

    def _on_microphone_test_start(self) -> None:
        if getattr(self, "_meeting_session", None) is not None:
            self._set_status("Finish the meeting before using dictation or changing its model.")
            return
        if getattr(self, "_model_cache_delete_in_progress", False):
            self._set_status("Wait for model deletion to finish.")
            return
        if self._controller.is_recording or self._controller.is_busy or self._controller.is_preloading:
            self._set_status("Finish the current dictation or model task before starting a microphone test.")
            return
        self._controller.start_microphone_test()
        if self._controller.is_microphone_test_recording:
            self._window.set_microphone_test_recording(True)

    def _on_microphone_test_stop(self) -> None:
        if not self._controller.is_microphone_test_recording:
            return
        self._window.set_microphone_test_recording(False)
        self._controller.stop_microphone_test()

    def _on_microphone_test_finished(self, result: object) -> None:
        if isinstance(result, dict):
            self._window.set_microphone_test_result(result)
        self._window.set_microphone_test_recording(False)

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
        self._word_count_action.setText(f"Session: {self._total_words} words ({self._last_words} last)")
        self._lifetime_word_count_action.setText(
            f"Lifetime: {self._lifetime_stats.total_words} words ({self._lifetime_stats.total_clips} clips)"
        )
        self._set_status(
            f"Transcript ready: {self._last_words} words. "
            f"This session: {self._total_words} words in {self._total_clips} clips."
        )

    def _on_error(self, message: str) -> None:
        self._controller.play_failure_feedback()
        self._set_status(message)
        self._notify_user(message, QSystemTrayIcon.MessageIcon.Critical, 2500, always=True)

    def _set_status(self, message: str) -> None:
        backend = self._controller.runtime_description
        if backend != "Not loaded yet" and backend not in message:
            message = f"{message} Processing: {backend}."
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
        if "starting amd gpu worker" in lower or "starting wsl pytorch" in lower:
            return "Starting GPU runtime..."
        if "warming radeon" in lower:
            return "Warming GPU kernels..."
        if "packing model weights" in lower or "moving model weights" in lower or "reading cached model" in lower:
            return "Preparing cached weights..."
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
        from .accessibility import concise_status
        self._tray.showMessage(APP_NAME, concise_status(text), icon, timeout_ms)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()

    def show(self) -> None:
        self._window.show()
        self._sync_tray_state()

    def shutdown(self) -> None:
        if self._meeting_session is not None:
            self._quit_after_meeting = True
            self._meeting_session.cancel_for_shutdown()
            self._stop_meeting()
            return
        self._window.meeting_panel.flush_notes()
        self._uninstall_shutdown_timer.stop()
        if self._uninstall_shutdown_event:
            ctypes.windll.kernel32.CloseHandle(self._uninstall_shutdown_event)
            self._uninstall_shutdown_event = None
        self._hotkey.stop()
        self._controller.shutdown()
        self._tray.hide()
        self._app.quit()

    def _check_uninstall_shutdown_request(self) -> None:
        if not self._uninstall_shutdown_event:
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        if kernel32.WaitForSingleObject(self._uninstall_shutdown_event, 0) != _WAIT_OBJECT_0:
            return
        # Preserve any Word Bank edits that have reached the UI before exiting.
        self._window.save_pending_changes()
        kernel32.CloseHandle(self._uninstall_shutdown_event)
        self._uninstall_shutdown_event = None
        self.shutdown()

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
        from .wsl_whisper import wsl_enabled
        from .model_storage import AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX, MODEL_CACHE_PREFIX, WSL_MODEL_CACHE_PREFIX

        rows: list[tuple[str, str, str, bool]] = []
        error = ""
        # Cache enumeration is metadata work, not a GPU availability probe.
        if self._config.runtime_mode == "cpu":
            prefix = MODEL_CACHE_PREFIX
        elif wsl_enabled():
            prefix = (AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX, WSL_MODEL_CACHE_PREFIX)
        elif self._config.runtime_mode == "amd_gpu":
            prefix = (AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX)
        else:
            prefix = (MODEL_CACHE_PREFIX, AMD_MODEL_CACHE_PREFIX, SHARED_AMD_MODEL_CACHE_PREFIX)
        try:
            models = list_cached_models(self._model_cache_dir)
            for item in models:
                status = "ready" if item.ready else "incomplete"
                label = f"{item.model_name} ({item.backend}, {format_size(item.size_bytes)}, {status})"
                rows.append((label, item.folder_name, item.model_name, item.ready))
        except Exception as exc:
            LOGGER.exception("Cached model refresh failed")
            error = str(exc)
        self.model_cache_entries_ready.emit((generation, rows, error, prefix))

    def _apply_model_cache_entries(self, payload: object) -> None:
        generation, rows, error, prefix = payload
        if generation != self._model_cache_refresh_generation:
            return
        ready_map: dict[str, bool] = {}
        for _, folder_name, model_name, ready in rows:
            if folder_name.startswith(prefix):
                ready_map[model_name] = ready_map.get(model_name, False) or ready
        self._model_ready_map = ready_map
        self._window.set_model_cache_entries(rows)
        self._window.set_model_choices_availability(self._model_ready_map, self._config.model_name)
        self._window.set_model_cache_refreshing(False)
        if error:
            self._set_status(f"Unable to refresh cached model list ({error}).")


def run() -> int:
    if "--shutdown-for-uninstall" in sys.argv[1:]:
        return _signal_shutdown_for_uninstall()
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
