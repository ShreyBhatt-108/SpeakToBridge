from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleAnnouncementEvent,
    QAccessibleEvent,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    APP_NAME,
    APP_TAGLINE,
    MAX_MAX_RECORDING_SECONDS,
    MIN_MAX_RECORDING_SECONDS,
    MODEL_CHOICES,
    RUNTIME_CHOICES,
)


class SettingsWindow(QMainWindow):
    model_apply_requested = Signal(str)
    model_cache_refresh_requested = Signal()
    model_cache_delete_requested = Signal(str)
    hotkey_apply_requested = Signal(str)
    read_hotkey_apply_requested = Signal(str)
    recording_limit_apply_requested = Signal(int)
    sound_effects_changed = Signal(bool)
    runtime_apply_requested = Signal(str)
    word_bank_save_requested = Signal(object)
    dictation_toggle_requested = Signal()
    microphone_test_start_requested = Signal()
    microphone_test_stop_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        initial_model: str,
        initial_hotkey: str,
        initial_read_hotkey: str,
        initial_max_recording_seconds: int,
        initial_sound_effects_enabled: bool,
        initial_runtime_mode: str = "cpu_auto_gpu",
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Settings")
        self.resize(820, 760)
        # Use the native Windows palette, font, focus indicators, dark mode, and
        # high-contrast behavior instead of overriding them with fixed colors.

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        welcome_label = QLabel(f"Welcome to {APP_NAME}\n{APP_TAGLINE}")
        welcome_label.setWordWrap(True)
        welcome_label.setAccessibleName(f"Welcome to {APP_NAME}. {APP_TAGLINE}")
        welcome_label.setAccessibleDescription(
            "Local, accessible dictation that carries your spoken words into the active application."
        )
        root_layout.addWidget(welcome_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        scroll.setWidget(body)
        root_layout.addWidget(scroll)

        hotkey_group = QGroupBox("Hotkeys")
        hotkey_group.setAccessibleName("Hotkey settings")
        hotkey_form = QFormLayout(hotkey_group)
        hotkey_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.hotkey_modifier_combo = QComboBox()
        self.hotkey_modifier_combo.setAccessibleName("Activation hotkey modifier")
        self.hotkey_modifier_combo.addItem("Ctrl", "ctrl")
        self.hotkey_modifier_combo.addItem("Alt", "alt")
        self.hotkey_modifier_combo.addItem("Shift", "shift")
        self.hotkey_modifier_combo.addItem("Win", "win")
        self.hotkey_modifier_combo.addItem("Ctrl+Alt", "ctrl+alt")
        self.hotkey_modifier_combo.addItem("Ctrl+Shift", "ctrl+shift")
        self.hotkey_modifier_combo.addItem("Ctrl+Win", "ctrl+win")
        self.hotkey_modifier_combo.addItem("Alt+Shift", "alt+shift")
        self.hotkey_modifier_combo.addItem("Alt+Win", "alt+win")
        self.hotkey_modifier_combo.addItem("Shift+Win", "shift+win")
        self.hotkey_modifier_combo.addItem("Ctrl+Alt+Shift", "ctrl+alt+shift")
        self.hotkey_modifier_combo.addItem("Ctrl+Alt+Win", "ctrl+alt+win")
        self.hotkey_modifier_combo.addItem("Ctrl+Shift+Win", "ctrl+shift+win")
        self.hotkey_modifier_combo.addItem("Alt+Shift+Win", "alt+shift+win")
        self.hotkey_modifier_combo.addItem("Ctrl+Alt+Shift+Win", "ctrl+alt+shift+win")

        self.hotkey_key_combo = QComboBox()
        self.hotkey_key_combo.setAccessibleName("Activation hotkey key")
        self.hotkey_key_combo.addItem("Win", "win")
        for i in range(1, 13):
            self.hotkey_key_combo.addItem(f"F{i}", f"f{i}")
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.hotkey_key_combo.addItem(ch, ch.lower())
        for digit in "0123456789":
            self.hotkey_key_combo.addItem(digit, digit)

        self.hotkey_apply_button = QPushButton("Apply Hotkey")
        self.hotkey_apply_button.setAccessibleName("Apply activation hotkey")
        self.hotkey_apply_button.clicked.connect(self._emit_hotkey_apply_requested)

        self.hotkey_value = QLineEdit("")
        self.hotkey_value.setReadOnly(True)
        self.hotkey_value.setFocusPolicy(Qt.NoFocus)
        self.hotkey_value.setAccessibleName("Current activation hotkey")
        self.hotkey_value.setAccessibleDescription("Current active dictation hotkey.")

        self.read_hotkey_modifier_combo = QComboBox()
        self.read_hotkey_modifier_combo.setAccessibleName("Read aloud hotkey modifier")
        self.read_hotkey_modifier_combo.addItem("Ctrl", "ctrl")
        self.read_hotkey_modifier_combo.addItem("Alt", "alt")
        self.read_hotkey_modifier_combo.addItem("Shift", "shift")
        self.read_hotkey_modifier_combo.addItem("Win", "win")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Alt", "ctrl+alt")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Shift", "ctrl+shift")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Win", "ctrl+win")
        self.read_hotkey_modifier_combo.addItem("Alt+Shift", "alt+shift")
        self.read_hotkey_modifier_combo.addItem("Alt+Win", "alt+win")
        self.read_hotkey_modifier_combo.addItem("Shift+Win", "shift+win")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Alt+Shift", "ctrl+alt+shift")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Alt+Win", "ctrl+alt+win")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Shift+Win", "ctrl+shift+win")
        self.read_hotkey_modifier_combo.addItem("Alt+Shift+Win", "alt+shift+win")
        self.read_hotkey_modifier_combo.addItem("Ctrl+Alt+Shift+Win", "ctrl+alt+shift+win")

        self.read_hotkey_key_combo = QComboBox()
        self.read_hotkey_key_combo.setAccessibleName("Read aloud hotkey key")
        self.read_hotkey_key_combo.addItem("Win", "win")
        for i in range(1, 13):
            self.read_hotkey_key_combo.addItem(f"F{i}", f"f{i}")
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.read_hotkey_key_combo.addItem(ch, ch.lower())
        for digit in "0123456789":
            self.read_hotkey_key_combo.addItem(digit, digit)

        self.read_hotkey_apply_button = QPushButton("Apply Read Hotkey")
        self.read_hotkey_apply_button.setAccessibleName("Apply read aloud hotkey")
        self.read_hotkey_apply_button.clicked.connect(self._emit_read_hotkey_apply_requested)

        self.read_hotkey_value = QLineEdit("")
        self.read_hotkey_value.setReadOnly(True)
        self.read_hotkey_value.setFocusPolicy(Qt.NoFocus)
        self.read_hotkey_value.setAccessibleName("Current read aloud hotkey")

        hotkey_form.addRow("Modifier:", self.hotkey_modifier_combo)
        hotkey_form.addRow("Key:", self.hotkey_key_combo)
        hotkey_form.addRow("", self.hotkey_apply_button)
        hotkey_form.addRow("Current activation:", self.hotkey_value)
        hotkey_form.addRow("Read modifier:", self.read_hotkey_modifier_combo)
        hotkey_form.addRow("Read key:", self.read_hotkey_key_combo)
        hotkey_form.addRow("", self.read_hotkey_apply_button)
        hotkey_form.addRow("Read aloud:", self.read_hotkey_value)
        model_group = QGroupBox("Model")
        model_group.setAccessibleName("Model")
        model_form = QFormLayout(model_group)
        model_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.model_combo = QComboBox()
        self.model_combo.setAccessibleName("Whisper model")
        self.model_combo.setAccessibleDescription(
            "Choose a model. Models marked download on apply require an internet download."
        )
        self.model_combo.setFocusPolicy(Qt.StrongFocus)
        self.model_combo.setMaxVisibleItems(10)
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setMinimumContentsLength(12)
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, model_value in MODEL_CHOICES.items():
            self.model_combo.addItem(label, model_value)
        index = self.model_combo.findData(initial_model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        model_form.addRow("Downloaded model:", self.model_combo)

        self.apply_model_button = QPushButton("Apply Model")
        self.apply_model_button.setAccessibleName("Apply selected model")
        self.apply_model_button.setAccessibleDescription("Applies the selected model setting.")
        self.apply_model_button.clicked.connect(self._emit_model_apply_requested)
        model_form.addRow("", self.apply_model_button)
        self.model_status_value = QLineEdit("Idle")
        self.model_status_value.setReadOnly(True)
        self.model_status_value.setAccessibleName("Model status")
        model_form.addRow("Model status:", self.model_status_value)
        self.active_model_value = QLineEdit(initial_model)
        self.active_model_value.setReadOnly(True)
        self.active_model_value.setFocusPolicy(Qt.NoFocus)
        self.active_model_value.setAccessibleName("Active model")
        model_form.addRow("Active model:", self.active_model_value)
        self.loaded_backend_value = QLineEdit("Not loaded yet")
        self.loaded_backend_value.setReadOnly(True)
        self.loaded_backend_value.setAccessibleName("Loaded backend")
        self.loaded_backend_value.setAccessibleDescription("The backend actually loaded, rather than the selected preference.")
        model_form.addRow("Loaded backend:", self.loaded_backend_value)
        self.last_transcription_backend_value = QLineEdit("No transcription this session")
        self.last_transcription_backend_value.setReadOnly(True)
        self.last_transcription_backend_value.setAccessibleName("Last transcription backend")
        self.last_transcription_backend_value.setAccessibleDescription("CPU or GPU used for the last successful transcription in this session, including microphone tests.")
        model_form.addRow("Last transcription:", self.last_transcription_backend_value)
        self.runtime_combo = QComboBox()
        self.runtime_combo.setAccessibleName("Processing device")
        for label, value in RUNTIME_CHOICES.items():
            self.runtime_combo.addItem(label, value)
        self.runtime_combo.setCurrentIndex(max(0, self.runtime_combo.findData(initial_runtime_mode)))
        model_form.addRow("Processing device:", self.runtime_combo)
        self.runtime_apply_button = QPushButton("Apply Processing Device")
        self.runtime_apply_button.clicked.connect(
            lambda: self.runtime_apply_requested.emit(str(self.runtime_combo.currentData()))
        )
        model_form.addRow("", self.runtime_apply_button)
        runtime_help = QLabel("AMD GPU mode requires the optional ROCm runtime. CPU works without it.")
        runtime_help.setWordWrap(True)
        model_form.addRow("", runtime_help)
        model_help = QLabel("Model changes apply immediately. Restart is not required.")
        model_help.setWordWrap(True)
        model_form.addRow("", model_help)
        body_layout.addWidget(model_group)
        body_layout.addWidget(hotkey_group)

        sound_group = QGroupBox("Sound Effects")
        sound_group.setAccessibleName("Sound effect settings")
        sound_layout = QVBoxLayout(sound_group)
        self.sound_effects_checkbox = QCheckBox("Play sound effects")
        self.sound_effects_checkbox.setAccessibleName("Play sound effects")
        self.sound_effects_checkbox.setAccessibleDescription(
            "Controls the recording, processing, success, and failure sound cues. "
            "Runtime Status remains available when sounds are off."
        )
        self.sound_effects_checkbox.setChecked(initial_sound_effects_enabled)
        self.sound_effects_checkbox.toggled.connect(self.sound_effects_changed.emit)
        sound_layout.addWidget(self.sound_effects_checkbox)
        sound_help = QLabel(
            "Turn off sound cues if you prefer to use Runtime Status alone. The setting is saved automatically."
        )
        sound_help.setWordWrap(True)
        sound_layout.addWidget(sound_help)
        body_layout.addWidget(sound_group)

        microphone_group = QGroupBox("Microphone Check")
        microphone_group.setAccessibleName("Microphone quality and model accuracy check")
        microphone_group.setAccessibleDescription(
            "Records a short sample only for this check, reports microphone level and clipping, then compares "
            "the local model transcript with the displayed test sentence. It does not insert text or change dictation statistics."
        )
        microphone_layout = QVBoxLayout(microphone_group)
        microphone_help = QLabel(
            "Test the default Windows microphone and this app's selected model without inserting anything into another app. "
            "Select Start, say the test sentence, then select Stop and Analyze."
        )
        microphone_help.setWordWrap(True)
        microphone_layout.addWidget(microphone_help)
        self.microphone_test_phrase_value = QLineEdit("The quick brown fox jumps over the lazy dog.")
        self.microphone_test_phrase_value.setReadOnly(True)
        self.microphone_test_phrase_value.setAccessibleName("Microphone test sentence")
        self.microphone_test_phrase_value.setAccessibleDescription("Read this sentence aloud during the microphone test.")
        microphone_layout.addWidget(QLabel("Say this sentence:"))
        microphone_layout.addWidget(self.microphone_test_phrase_value)
        microphone_actions = QHBoxLayout()
        self.microphone_test_start_button = QPushButton("Start Microphone Test")
        self.microphone_test_start_button.setAccessibleName("Start microphone test recording")
        self.microphone_test_start_button.setAccessibleDescription(
            "Starts a private microphone test. Read the displayed sentence, then use Stop and Analyze."
        )
        self.microphone_test_start_button.clicked.connect(self.microphone_test_start_requested.emit)
        self.microphone_test_stop_button = QPushButton("Stop and Analyze")
        self.microphone_test_stop_button.setAccessibleName("Stop microphone test and analyze it")
        self.microphone_test_stop_button.setAccessibleDescription(
            "Stops recording and measures audio level, clipping, and the local model's word accuracy."
        )
        self.microphone_test_stop_button.setEnabled(False)
        self.microphone_test_stop_button.clicked.connect(self.microphone_test_stop_requested.emit)
        microphone_actions.addWidget(self.microphone_test_start_button)
        microphone_actions.addWidget(self.microphone_test_stop_button)
        microphone_layout.addLayout(microphone_actions)
        self.microphone_test_result = QPlainTextEdit("No microphone test has been run.")
        self.microphone_test_result.setReadOnly(True)
        self.microphone_test_result.setMinimumHeight(110)
        self.microphone_test_result.setAccessibleName("Microphone test result")
        self.microphone_test_result.setAccessibleDescription("Audio level, clipping, recognition accuracy, and transcript from the microphone test.")
        microphone_layout.addWidget(self.microphone_test_result)
        body_layout.addWidget(microphone_group)

        storage_group = QGroupBox("Model Storage")
        storage_group.setAccessibleName("Model storage")
        storage_layout = QVBoxLayout(storage_group)
        storage_help = QLabel("Cached models are kept for faster switching. Select one and delete if you need space.")
        storage_help.setWordWrap(True)
        storage_layout.addWidget(storage_help)

        self.model_cache_list = QListWidget()
        self.model_cache_list.setAccessibleName("Cached model list")
        self.model_cache_list.setMinimumHeight(110)
        storage_layout.addWidget(self.model_cache_list)

        storage_actions = QHBoxLayout()
        self.model_cache_refresh_button = QPushButton("Refresh List")
        self.model_cache_refresh_button.clicked.connect(self.model_cache_refresh_requested.emit)
        self.model_cache_delete_button = QPushButton("Delete Selected Model")
        self.model_cache_delete_button.clicked.connect(self._emit_model_cache_delete_requested)
        self.model_cache_delete_button.setEnabled(False)
        self.model_cache_list.currentItemChanged.connect(self._update_model_cache_delete_button)
        storage_actions.addWidget(self.model_cache_refresh_button)
        storage_actions.addWidget(self.model_cache_delete_button)
        storage_layout.addLayout(storage_actions)

        language_group = QGroupBox("Language")
        language_group.setAccessibleName("Language settings")
        language_form = QFormLayout(language_group)
        language_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.language_value = QLineEdit("English only (v1)")
        self.language_value.setReadOnly(True)
        self.language_value.setFocusPolicy(Qt.NoFocus)
        self.language_value.setAccessibleName("Language mode value")
        self.language_value.setAccessibleDescription("Current transcription language mode.")
        language_form.addRow("Transcription language:", self.language_value)

        dictionary_group = QGroupBox("Dictionary")
        dictionary_group.setAccessibleName("Dictionary settings")
        dictionary_layout = QVBoxLayout(dictionary_group)
        dictionary_message = QLabel("Add words the model gets wrong and the correct spelling to use.")
        dictionary_message.setWordWrap(True)
        dictionary_message.setAccessibleName("Dictionary status")
        dictionary_layout.addWidget(dictionary_message)

        word_bank_form = QFormLayout()
        word_bank_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.word_bank_heard_input = QLineEdit("")
        self.word_bank_heard_input.setAccessibleName("Heard as")
        self.word_bank_correct_input = QLineEdit("")
        self.word_bank_correct_input.setAccessibleName("Correct spelling")
        word_bank_form.addRow("Heard as:", self.word_bank_heard_input)
        word_bank_form.addRow("Correct spelling:", self.word_bank_correct_input)
        dictionary_layout.addLayout(word_bank_form)

        word_bank_actions = QHBoxLayout()
        self.word_bank_add_button = QPushButton("Add Or Update")
        self.word_bank_add_button.clicked.connect(self._add_or_update_word_bank_entry)
        self.word_bank_remove_button = QPushButton("Remove Selected")
        self.word_bank_remove_button.clicked.connect(self._remove_selected_word_bank_entry)
        word_bank_actions.addWidget(self.word_bank_add_button)
        word_bank_actions.addWidget(self.word_bank_remove_button)
        dictionary_layout.addLayout(word_bank_actions)

        self.word_bank_list = QListWidget()
        self.word_bank_list.setAccessibleName("Word bank entries")
        self.word_bank_list.setAccessibleDescription("List of saved word corrections.")
        self.word_bank_list.itemActivated.connect(self._load_selected_word_bank_entry)
        self.word_bank_list.itemClicked.connect(self._load_selected_word_bank_entry)
        self.word_bank_list.setMinimumHeight(140)
        dictionary_layout.addWidget(self.word_bank_list)

        self.word_bank_save_button = QPushButton("Save Word Bank")
        self.word_bank_save_button.setAccessibleName("Save word bank")
        self.word_bank_save_button.clicked.connect(self._emit_word_bank_save_requested)
        self.word_bank_save_button.setEnabled(False)
        dictionary_layout.addWidget(self.word_bank_save_button)

        recording_group = QGroupBox("Recording Limit")
        recording_group.setAccessibleName("Recording duration limit")
        recording_form = QFormLayout(recording_group)
        recording_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.recording_limit_input = QSpinBox()
        self.recording_limit_input.setRange(MIN_MAX_RECORDING_SECONDS, MAX_MAX_RECORDING_SECONDS)
        self.recording_limit_input.setSuffix(" seconds")
        self.recording_limit_input.setValue(initial_max_recording_seconds)
        self.recording_limit_input.setAccessibleName("Maximum recording length in seconds")
        self.recording_limit_input.setAccessibleDescription(
            "Recording stops and transcription starts automatically at this limit."
        )
        self.recording_limit_apply_button = QPushButton("Apply Recording Limit")
        self.recording_limit_apply_button.clicked.connect(
            lambda: self.recording_limit_apply_requested.emit(self.recording_limit_input.value())
        )
        recording_form.addRow("Maximum length:", self.recording_limit_input)
        recording_form.addRow("", self.recording_limit_apply_button)

        stats_group = QGroupBox("Dictation Stats")
        stats_group.setAccessibleName("Dictation statistics")
        stats_form = QFormLayout(stats_group)
        stats_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.last_words_value = QLineEdit("0")
        self.last_words_value.setReadOnly(True)
        self.last_words_value.setFocusPolicy(Qt.NoFocus)
        self.last_words_value.setAccessibleName("Last transcript word count")
        self.total_words_value = QLineEdit("0")
        self.total_words_value.setReadOnly(True)
        self.total_words_value.setFocusPolicy(Qt.NoFocus)
        self.total_words_value.setAccessibleName("Total dictated words")
        self.total_clips_value = QLineEdit("0")
        self.total_clips_value.setReadOnly(True)
        self.total_clips_value.setFocusPolicy(Qt.NoFocus)
        self.total_clips_value.setAccessibleName("Total dictated clips")
        self.lifetime_summary_value = QLineEdit("0 words in 0 clips")
        self.lifetime_summary_value.setReadOnly(True)
        self.lifetime_summary_value.setFocusPolicy(Qt.StrongFocus)
        self.lifetime_summary_value.setAccessibleName("Overall dictation total")
        self.lifetime_summary_value.setAccessibleDescription(
            f"All words and dictation clips recorded across every {APP_NAME} session."
        )
        stats_form.addRow("Last transcript words:", self.last_words_value)
        stats_form.addRow("Session words:", self.total_words_value)
        stats_form.addRow("Session clips:", self.total_clips_value)
        stats_form.addRow("Overall total:", self.lifetime_summary_value)
        body_layout.addWidget(stats_group)

        status_group = QGroupBox("Status")
        status_group.setAccessibleName("Runtime status")
        status_layout = QHBoxLayout(status_group)
        self.status_value = QPlainTextEdit()
        self.status_value.setPlainText(
            "Ready. Configure and use your activation hotkey to start or stop dictation."
        )
        self.status_value.setReadOnly(True)
        self.status_value.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.status_value.setTabChangesFocus(True)
        self.status_value.setMinimumHeight(76)
        self.status_value.setMaximumHeight(120)
        self.status_value.setFocusPolicy(Qt.StrongFocus)
        self.status_value.setAccessibleName("Current runtime status")
        self.status_value.setAccessibleDescription(
            "Live status updates for dictation and settings actions. Press Alt+S to focus it, "
            "then use normal text-reading commands."
        )
        status_layout.addWidget(self.status_value)
        body_layout.addWidget(status_group)
        self._status_shortcut = QShortcut(QKeySequence("Alt+S"), self)
        self._status_shortcut.activated.connect(self.focus_status)

        action_group = QGroupBox("Window")
        action_group.setAccessibleName("Window controls")
        action_layout = QGridLayout(action_group)
        self.settings_toggle_button = QPushButton("Show More Settings")
        self.settings_toggle_button.setAccessibleName("Show more settings")
        self.settings_toggle_button.setAccessibleDescription("Press Space or Enter to show or hide settings that are not needed for normal dictation.")
        self.settings_toggle_button.clicked.connect(self._toggle_advanced_settings)
        action_layout.addWidget(self.settings_toggle_button, 0, 0)
        self.dictation_toggle_button = QPushButton("Disable Dictation")
        self.dictation_toggle_button.setAccessibleName("Toggle dictation")
        self.dictation_toggle_button.setAccessibleDescription(
            f"Enable or disable {initial_hotkey} dictation globally."
        )
        self.dictation_toggle_button.clicked.connect(self._emit_dictation_toggle_requested)
        action_layout.addWidget(self.dictation_toggle_button, 0, 1)
        self.quit_button = QPushButton(f"Quit {APP_NAME}")
        self.quit_button.setAccessibleName(f"Quit {APP_NAME}")
        self.quit_button.setAccessibleDescription("This button shuts down the program.")
        self.quit_button.clicked.connect(self._emit_quit_requested)
        action_layout.addWidget(self.quit_button, 1, 0)
        self.close_to_tray_button = QPushButton("Close Settings to Tray")
        self.close_to_tray_button.setAccessibleName("Close settings to tray")
        self.close_to_tray_button.setAccessibleDescription(f"This button minimizes {APP_NAME} to tray.")
        self.close_to_tray_button.clicked.connect(self._request_close_to_tray)
        action_layout.addWidget(self.close_to_tray_button, 1, 1)
        body_layout.addWidget(action_group)
        body_layout.addWidget(recording_group)
        body_layout.addWidget(storage_group)
        body_layout.addWidget(language_group)
        body_layout.addWidget(dictionary_group)

        body_layout.addStretch(1)
        self.setCentralWidget(central)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(True)
            button.setDefault(False)

        self._advanced_visible = False
        self._word_bank_dirty = False
        self._advanced_groups = [recording_group, storage_group, language_group, dictionary_group]
        self.set_hotkey_value(initial_hotkey)
        self.set_read_hotkey_value(initial_read_hotkey)
        self._set_advanced_groups_visible(False)

        self.setTabOrder(self.model_combo, self.apply_model_button)
        self.setTabOrder(self.apply_model_button, self.model_status_value)
        self.setTabOrder(self.model_status_value, self.runtime_combo)
        self.setTabOrder(self.runtime_combo, self.runtime_apply_button)
        self.setTabOrder(self.runtime_apply_button, self.hotkey_modifier_combo)
        self.setTabOrder(self.hotkey_modifier_combo, self.hotkey_key_combo)
        self.setTabOrder(self.hotkey_key_combo, self.hotkey_apply_button)
        self.setTabOrder(self.hotkey_apply_button, self.read_hotkey_modifier_combo)
        self.setTabOrder(self.read_hotkey_modifier_combo, self.read_hotkey_key_combo)
        self.setTabOrder(self.read_hotkey_key_combo, self.read_hotkey_apply_button)
        self.setTabOrder(self.read_hotkey_apply_button, self.sound_effects_checkbox)
        self.setTabOrder(self.sound_effects_checkbox, self.lifetime_summary_value)
        self.setTabOrder(self.sound_effects_checkbox, self.microphone_test_phrase_value)
        self.setTabOrder(self.microphone_test_phrase_value, self.microphone_test_start_button)
        self.setTabOrder(self.microphone_test_start_button, self.microphone_test_stop_button)
        self.setTabOrder(self.microphone_test_stop_button, self.microphone_test_result)
        self.setTabOrder(self.microphone_test_result, self.lifetime_summary_value)
        self.setTabOrder(self.lifetime_summary_value, self.status_value)
        self.setTabOrder(self.status_value, self.settings_toggle_button)
        self.setTabOrder(self.settings_toggle_button, self.dictation_toggle_button)
        self.setTabOrder(self.dictation_toggle_button, self.quit_button)
        self.setTabOrder(self.quit_button, self.close_to_tray_button)
        self.setTabOrder(self.close_to_tray_button, self.recording_limit_input)
        self.setTabOrder(self.recording_limit_input, self.recording_limit_apply_button)
        self.setTabOrder(self.recording_limit_apply_button, self.model_cache_list)
        self.setTabOrder(self.model_cache_list, self.model_cache_refresh_button)
        self.setTabOrder(self.model_cache_refresh_button, self.model_cache_delete_button)
        self.setTabOrder(self.model_cache_delete_button, self.word_bank_heard_input)
        self.setTabOrder(self.word_bank_heard_input, self.word_bank_correct_input)
        self.setTabOrder(self.word_bank_correct_input, self.word_bank_add_button)
        self.setTabOrder(self.word_bank_add_button, self.word_bank_remove_button)
        self.setTabOrder(self.word_bank_remove_button, self.word_bank_list)
        self.setTabOrder(self.word_bank_list, self.word_bank_save_button)
        self.word_bank_list.setTabKeyNavigation(False)
        self.word_bank_list.setFocusPolicy(Qt.StrongFocus)
        self.word_bank_list.setWrapping(False)
        self.word_bank_list.setWordWrap(False)
        self.setTabOrder(self.word_bank_save_button, self.status_value)
        self.model_combo.setFocus()

    def set_status(self, message: str) -> None:
        self.status_value.setPlainText(message)
        self.status_value.moveCursor(QTextCursor.MoveOperation.Start)
        self.status_value.setAccessibleName(f"Current runtime status: {message}")
        QAccessible.updateAccessibility(
            QAccessibleEvent(self.status_value, QAccessible.Event.NameChanged)
        )
        announcement = QAccessibleAnnouncementEvent(self.status_value, message)
        announcement.setPoliteness(QAccessible.AnnouncementPoliteness.Polite)
        QAccessible.updateAccessibility(announcement)

    def set_microphone_test_recording(self, recording: bool) -> None:
        self.microphone_test_start_button.setEnabled(not recording)
        self.microphone_test_stop_button.setEnabled(recording)
        self.microphone_test_start_button.setText(
            "Microphone Test Recording" if recording else "Start Microphone Test"
        )
        state = "Microphone test recording. Read the displayed sentence, then select Stop and Analyze." if recording else "Microphone test recording stopped. Analysis may still be in progress."
        announcement = QAccessibleAnnouncementEvent(self.microphone_test_start_button, state)
        announcement.setPoliteness(QAccessible.AnnouncementPoliteness.Polite)
        QAccessible.updateAccessibility(announcement)

    def set_microphone_test_result(self, result: dict) -> None:
        quality = result["quality"]
        accuracy = result.get("accuracy")
        accuracy_text = "Not available" if accuracy is None else f"{accuracy:.0f}% word accuracy"
        transcript = result.get("transcript") or "No speech recognized."
        text = (
            f"Audio quality: {quality['assessment']}\n"
            f"Duration: {quality['duration']:.1f} seconds. Average level: {quality['rms_dbfs']:.1f} dBFS. "
            f"Peak: {quality['peak_dbfs']:.1f} dBFS. Clipping: {quality['clipping_percent']:.2f}%.\n"
            f"Model accuracy: {accuracy_text}.\n"
            f"Expected: {result['expected']}\n"
            f"Model heard: {transcript}"
        )
        self.microphone_test_result.setPlainText(text)
        self.microphone_test_result.moveCursor(QTextCursor.MoveOperation.Start)
        self.microphone_test_result.setAccessibleName(f"Microphone test result: {text}")
        QAccessible.updateAccessibility(
            QAccessibleEvent(self.microphone_test_result, QAccessible.Event.NameChanged)
        )
        announcement = QAccessibleAnnouncementEvent(
            self.microphone_test_result,
            f"Microphone test complete. {quality['assessment']} Model accuracy: {accuracy_text}."
        )
        announcement.setPoliteness(QAccessible.AnnouncementPoliteness.Assertive)
        QAccessible.updateAccessibility(announcement)
        self.microphone_test_result.setFocus()

    def set_loaded_backend(self, description: str) -> None:
        self.loaded_backend_value.setText(description)
        self.loaded_backend_value.setToolTip(description)
        self.loaded_backend_value.setCursorPosition(0)

    def set_last_transcription_backend(self, description: str) -> None:
        self.last_transcription_backend_value.setText(description)
        self.last_transcription_backend_value.setToolTip(description)
        self.last_transcription_backend_value.setCursorPosition(0)

    def focus_status(self) -> None:
        self.status_value.setFocus()

    def focus_model_status(self) -> None:
        self.model_status_value.setFocus()
        self.model_status_value.selectAll()

    def set_word_stats(
        self,
        last_words: int,
        total_words: int,
        total_clips: int,
        lifetime_words: int = 0,
        lifetime_clips: int = 0,
    ) -> None:
        self.last_words_value.setText(str(last_words))
        self.total_words_value.setText(str(total_words))
        self.total_clips_value.setText(str(total_clips))
        summary = f"{lifetime_words} words in {lifetime_clips} clips"
        self.lifetime_summary_value.setText(summary)
        self.lifetime_summary_value.setAccessibleName(f"Overall dictation total: {summary}")

    def set_dictation_enabled(self, enabled: bool) -> None:
        if enabled:
            self.dictation_toggle_button.setText("Disable Dictation")
            self.dictation_toggle_button.setAccessibleName("Disable dictation")
            self.dictation_toggle_button.setAccessibleDescription(
                f"Turns {APP_NAME} dictation shortcuts off."
            )
        else:
            self.dictation_toggle_button.setText("Enable Dictation")
            self.dictation_toggle_button.setAccessibleName("Enable dictation")
            self.dictation_toggle_button.setAccessibleDescription(
                f"Turns {APP_NAME} dictation shortcuts on."
            )

    def set_hotkey_value(self, hotkey_text: str) -> None:
        self.hotkey_value.setText(hotkey_text)
        self.hotkey_value.setCursorPosition(0)
        self.dictation_toggle_button.setAccessibleDescription(
            f"Enable or disable {hotkey_text} dictation globally."
        )
        parts = hotkey_text.lower().split("+")
        if len(parts) < 2:
            return
        modifier = "+".join(parts[:-1])
        key = parts[-1]
        modifier_index = self.hotkey_modifier_combo.findData(modifier)
        if modifier_index >= 0:
            self.hotkey_modifier_combo.setCurrentIndex(modifier_index)
        key_index = self.hotkey_key_combo.findData(key)
        if key_index >= 0:
            self.hotkey_key_combo.setCurrentIndex(key_index)

    def set_read_hotkey_value(self, hotkey_text: str) -> None:
        self.read_hotkey_value.setText(hotkey_text)
        self.read_hotkey_value.setCursorPosition(0)
        parts = hotkey_text.lower().split("+")
        if len(parts) < 2:
            return
        modifier = "+".join(parts[:-1])
        key = parts[-1]
        modifier_index = self.read_hotkey_modifier_combo.findData(modifier)
        if modifier_index >= 0:
            self.read_hotkey_modifier_combo.setCurrentIndex(modifier_index)
        key_index = self.read_hotkey_key_combo.findData(key)
        if key_index >= 0:
            self.read_hotkey_key_combo.setCurrentIndex(key_index)

    def set_model_status(self, text: str) -> None:
        self.model_status_value.setText(text)
        self.model_status_value.setCursorPosition(0)

    def set_active_model(self, model_name: str) -> None:
        self.active_model_value.setText(model_name)
        self.active_model_value.setCursorPosition(0)

    def set_model_value(self, model_name: str) -> None:
        index = self.model_combo.findData(model_name)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

    def set_model_choices_availability(self, ready_map: dict[str, bool], active_model: str) -> None:
        for i in range(self.model_combo.count()):
            model_name = str(self.model_combo.itemData(i))
            label = model_name
            is_ready = ready_map.get(model_name, False)
            if model_name == active_model:
                label = f"{model_name} (active)"
            elif is_ready:
                label = f"{model_name} (ready)"
            else:
                label = f"{model_name} (download on apply)"
            self.model_combo.setItemText(i, label)
            model_item = self.model_combo.model().item(i)
            if model_item is not None:
                # Keep all models selectable so users can trigger first-time download.
                model_item.setEnabled(True)

    def set_model_cache_refreshing(self, refreshing: bool) -> None:
        self.model_cache_refresh_button.setEnabled(not refreshing)
        if refreshing:
            self.model_cache_refresh_button.setText("Refreshing List")
            self.model_cache_list.setAccessibleDescription("Cached model list is refreshing.")
        else:
            self.model_cache_refresh_button.setText("Refresh List")
            self.model_cache_list.setAccessibleDescription("Cached models found on this computer.")

    def set_word_bank_entries(self, entries: list[tuple[str, str]]) -> None:
        self.word_bank_list.clear()
        for wrong, right in entries:
            self.word_bank_list.addItem(f"{wrong} -> {right}")
        self._set_word_bank_dirty(False)

    def set_model_cache_entries(self, entries: list[tuple[str, str, str, bool]]) -> None:
        self.model_cache_list.clear()
        for label, folder_name, _, _ in entries:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, folder_name)
            self.model_cache_list.addItem(item)
        self._update_model_cache_delete_button()

    def _emit_model_apply_requested(self) -> None:
        model_name = str(self.model_combo.currentData())
        self.model_apply_requested.emit(model_name)

    def _emit_hotkey_apply_requested(self) -> None:
        modifier = str(self.hotkey_modifier_combo.currentData())
        key = str(self.hotkey_key_combo.currentData())
        self.hotkey_apply_requested.emit(f"{modifier}+{key}")

    def _emit_read_hotkey_apply_requested(self) -> None:
        modifier = str(self.read_hotkey_modifier_combo.currentData())
        key = str(self.read_hotkey_key_combo.currentData())
        self.read_hotkey_apply_requested.emit(f"{modifier}+{key}")

    def _emit_dictation_toggle_requested(self) -> None:
        self.dictation_toggle_requested.emit()

    def _emit_word_bank_save_requested(self) -> None:
        entries: list[tuple[str, str]] = []
        for i in range(self.word_bank_list.count()):
            text = self.word_bank_list.item(i).text()
            if "->" not in text:
                continue
            left, right = text.split("->", 1)
            wrong = left.strip()
            correct = right.strip()
            if wrong and correct:
                entries.append((wrong, correct))
        self.word_bank_save_requested.emit(entries)

    def _emit_model_cache_delete_requested(self) -> None:
        current = self.model_cache_list.currentItem()
        if current is None:
            return
        folder_name = current.data(Qt.UserRole)
        if isinstance(folder_name, str) and folder_name:
            answer = QMessageBox.question(
                self,
                "Delete Cached Model",
                f"Delete {current.text()} from this computer?\n\nThe model can be downloaded again later.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.model_cache_delete_requested.emit(folder_name)

    def _update_model_cache_delete_button(self, *_args) -> None:  # noqa: ANN002
        self.model_cache_delete_button.setEnabled(self.model_cache_list.currentItem() is not None)

    def _add_or_update_word_bank_entry(self) -> None:
        wrong = self.word_bank_heard_input.text().strip()
        correct = self.word_bank_correct_input.text().strip()
        if not wrong or not correct:
            self.set_status("Enter both the heard form and the correct spelling.")
            return
        target = f"{wrong.lower()} -> {correct}"
        for i in range(self.word_bank_list.count()):
            current = self.word_bank_list.item(i).text()
            if current.split("->", 1)[0].strip().lower() == wrong.lower():
                self.word_bank_list.item(i).setText(target)
                self._set_word_bank_dirty(True)
                return
        self.word_bank_list.addItem(QListWidgetItem(target))
        self._set_word_bank_dirty(True)

    def _remove_selected_word_bank_entry(self) -> None:
        row = self.word_bank_list.currentRow()
        if row >= 0:
            self.word_bank_list.takeItem(row)
            self._set_word_bank_dirty(True)

    def _load_selected_word_bank_entry(self, item: QListWidgetItem) -> None:
        text = item.text()
        if "->" not in text:
            return
        left, right = text.split("->", 1)
        self.word_bank_heard_input.setText(left.strip())
        self.word_bank_correct_input.setText(right.strip())

    def _toggle_advanced_settings(self) -> None:
        self._set_advanced_groups_visible(not self._advanced_visible)

    def toggle_advanced_settings(self) -> None:
        self._toggle_advanced_settings()

    def is_advanced_settings_visible(self) -> bool:
        return self._advanced_visible

    def _set_advanced_groups_visible(self, visible: bool) -> None:
        self._advanced_visible = visible
        for group in self._advanced_groups:
            group.setVisible(visible)
        self.settings_toggle_button.setText("Hide More Settings" if visible else "Show More Settings")
        self.settings_toggle_button.setAccessibleName("Hide more settings" if visible else "Show more settings")

    def _set_word_bank_dirty(self, dirty: bool) -> None:
        self._word_bank_dirty = dirty
        self.word_bank_save_button.setEnabled(dirty)
        self.word_bank_save_button.setText("Save Word Bank (Unsaved Changes)" if dirty else "Save Word Bank")

    def _confirm_unsaved_word_bank(self) -> bool:
        if not self._word_bank_dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Word Bank Changes",
            "Save your Word Bank changes before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self._emit_word_bank_save_requested()
            return not self._word_bank_dirty
        self._set_word_bank_dirty(False)
        return True

    def _request_close_to_tray(self) -> None:
        if self._confirm_unsaved_word_bank():
            self.hide()

    def _emit_quit_requested(self) -> None:
        if self._confirm_unsaved_word_bank():
            self.quit_requested.emit()

    def confirm_pending_changes(self) -> bool:
        return self._confirm_unsaved_word_bank()

    def save_pending_changes(self) -> bool:
        """Persist in-window Word Bank edits without an uninstall-time prompt."""
        if self._word_bank_dirty:
            self._emit_word_bank_save_requested()
        return not self._word_bank_dirty

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self.model_combo.setFocus()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._confirm_unsaved_word_bank():
            event.ignore()
            self.hide()
            return
        event.ignore()
