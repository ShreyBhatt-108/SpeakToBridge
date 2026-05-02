from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_AUTHOR, MODEL_CHOICES


class SettingsWindow(QMainWindow):
    model_apply_requested = Signal(str)
    model_cache_refresh_requested = Signal()
    model_cache_delete_requested = Signal(str)
    hotkey_apply_requested = Signal(str)
    read_hotkey_apply_requested = Signal(str)
    word_bank_save_requested = Signal(object)
    dictation_toggle_requested = Signal()

    def __init__(self, initial_model: str, initial_hotkey: str, initial_read_hotkey: str) -> None:
        super().__init__()
        self.setWindowTitle("Severus AI Settings")
        self.resize(820, 760)
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f3f8ff,
                    stop:0.5 #eef5ff,
                    stop:1 #e8f1fc
                );
            }
            QWidget {
                font-family: "Segoe UI", "Tahoma", sans-serif;
                color: #162131;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #cadbf1;
                border-radius: 14px;
                margin-top: 13px;
                padding: 14px 14px 12px 14px;
                background: #ffffff;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #114a82;
                font-size: 13px;
            }
            QLabel#titleLabel {
                color: #0e3a67;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #405061;
                font-size: 13px;
                padding-bottom: 4px;
            }
            QLineEdit, QComboBox, QListWidget {
                border: 1px solid #bfd3ea;
                border-radius: 8px;
                padding: 8px;
                background: #f9fcff;
                color: #0d1d2c;
                selection-background-color: #0e639c;
            }
            QLineEdit:focus, QComboBox:focus, QListWidget:focus {
                border: 2px solid #0e639c;
                background: #ffffff;
            }
            QLineEdit[readOnly="true"] {
                background: #f2f7fc;
            }
            QPushButton {
                border: 1px solid #2a699f;
                border-radius: 9px;
                padding: 8px 14px;
                background: #e7f2ff;
                color: #0e3f6f;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d9eaff;
            }
            QPushButton:pressed {
                background: #c9def9;
            }
            QPushButton:focus {
                border: 2px solid #0e639c;
            }
            QFrame#heroCard {
                border: 1px solid #c9dbf0;
                border-radius: 16px;
                background: #ffffff;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        scroll.setWidget(body)
        root_layout.addWidget(scroll)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(6)

        title = QLabel("Severus AI")
        title.setObjectName("titleLabel")
        hero_layout.addWidget(title)

        subtitle = QLabel("Local Whisper dictation with a keyboard-first, screen-reader-ready interface.")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)

        credit = QLabel(f"Created by {APP_AUTHOR}")
        credit.setObjectName("subtitleLabel")
        hero_layout.addWidget(credit)

        hero_actions = QHBoxLayout()
        self.settings_toggle_button = QPushButton("Show More Settings")
        self.settings_toggle_button.setCheckable(True)
        self.settings_toggle_button.setAccessibleName("Show more settings")
        self.settings_toggle_button.setAccessibleDescription("Press Space or Enter to show or hide settings that are not needed for normal dictation.")
        self.settings_toggle_button.clicked.connect(self._toggle_advanced_settings)
        hero_actions.addWidget(self.settings_toggle_button)
        hero_actions.addStretch(1)
        hero_layout.addLayout(hero_actions)

        body_layout.addWidget(hero_card)

        hotkey_group = QGroupBox("Hotkeys")
        hotkey_group.setAccessibleName("Hotkey settings")
        hotkey_form = QFormLayout(hotkey_group)
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
        self.model_combo = QComboBox()
        self.model_combo.setAccessibleName("Downloaded model")
        self.model_combo.setAccessibleDescription("Choose an already downloaded model, then activate Apply Model.")
        self.model_combo.setFocusPolicy(Qt.StrongFocus)
        self.model_combo.setMaxVisibleItems(10)
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
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
        self.active_model_value.setAccessibleName("Active model")
        model_form.addRow("Active model:", self.active_model_value)
        model_help = QLabel("Model changes apply immediately. Restart is not required.")
        model_help.setWordWrap(True)
        model_form.addRow("", model_help)
        body_layout.addWidget(model_group)
        body_layout.addWidget(hotkey_group)

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
        storage_actions.addWidget(self.model_cache_refresh_button)
        storage_actions.addWidget(self.model_cache_delete_button)
        storage_layout.addLayout(storage_actions)
        body_layout.addWidget(storage_group)

        language_group = QGroupBox("Language")
        language_group.setAccessibleName("Language settings")
        language_form = QFormLayout(language_group)
        self.language_value = QLineEdit("English only (v1)")
        self.language_value.setReadOnly(True)
        self.language_value.setAccessibleName("Language mode value")
        self.language_value.setAccessibleDescription("Current transcription language mode.")
        language_form.addRow("Transcription language:", self.language_value)
        body_layout.addWidget(language_group)

        dictionary_group = QGroupBox("Dictionary")
        dictionary_group.setAccessibleName("Dictionary settings")
        dictionary_layout = QVBoxLayout(dictionary_group)
        dictionary_message = QLabel("Add words the model gets wrong and the correct spelling to use.")
        dictionary_message.setWordWrap(True)
        dictionary_message.setAccessibleName("Dictionary status")
        dictionary_layout.addWidget(dictionary_message)

        word_bank_form = QFormLayout()
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
        dictionary_layout.addWidget(self.word_bank_save_button)
        body_layout.addWidget(dictionary_group)

        stats_group = QGroupBox("Dictation Stats")
        stats_group.setAccessibleName("Dictation statistics")
        stats_form = QFormLayout(stats_group)
        self.last_words_value = QLineEdit("0")
        self.last_words_value.setReadOnly(True)
        self.last_words_value.setAccessibleName("Last transcript word count")
        self.total_words_value = QLineEdit("0")
        self.total_words_value.setReadOnly(True)
        self.total_words_value.setAccessibleName("Total dictated words")
        self.total_clips_value = QLineEdit("0")
        self.total_clips_value.setReadOnly(True)
        self.total_clips_value.setAccessibleName("Total dictated clips")
        stats_form.addRow("Last transcript words:", self.last_words_value)
        stats_form.addRow("Total words:", self.total_words_value)
        stats_form.addRow("Total clips:", self.total_clips_value)
        body_layout.addWidget(stats_group)

        status_group = QGroupBox("Status")
        status_group.setAccessibleName("Runtime status")
        status_layout = QHBoxLayout(status_group)
        self.status_value = QLineEdit("Ready. Configure and use your activation hotkey to start or stop dictation.")
        self.status_value.setReadOnly(True)
        self.status_value.setAccessibleName("Current dictation status")
        self.status_value.setAccessibleDescription("Live status updates for dictation and settings actions.")
        status_layout.addWidget(self.status_value)
        body_layout.addWidget(status_group)

        action_group = QGroupBox("Window")
        action_group.setAccessibleName("Window controls")
        action_layout = QHBoxLayout(action_group)
        self.dictation_toggle_button = QPushButton("Disable Dictation")
        self.dictation_toggle_button.setAccessibleName("Toggle dictation")
        self.dictation_toggle_button.setAccessibleDescription("Enable or disable Ctrl+F9 dictation globally.")
        self.dictation_toggle_button.clicked.connect(self._emit_dictation_toggle_requested)
        action_layout.addWidget(self.dictation_toggle_button)
        self.close_to_tray_button = QPushButton("Close to Tray")
        self.close_to_tray_button.setAccessibleName("Close settings to tray")
        self.close_to_tray_button.setAccessibleDescription("Hides this settings window and keeps the app in the system tray.")
        self.close_to_tray_button.clicked.connect(self.hide)
        action_layout.addWidget(self.close_to_tray_button)
        body_layout.addWidget(action_group)

        body_layout.addStretch(1)
        self.setCentralWidget(central)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(True)
            button.setDefault(False)

        self._advanced_visible = False
        self._advanced_groups = [storage_group, language_group, dictionary_group]
        self.set_hotkey_value(initial_hotkey)
        self.set_read_hotkey_value(initial_read_hotkey)
        self._set_advanced_groups_visible(False)

        self.setTabOrder(self.model_combo, self.apply_model_button)
        self.setTabOrder(self.apply_model_button, self.model_status_value)
        self.setTabOrder(self.model_status_value, self.active_model_value)
        self.setTabOrder(self.active_model_value, self.hotkey_modifier_combo)
        self.setTabOrder(self.hotkey_modifier_combo, self.hotkey_key_combo)
        self.setTabOrder(self.hotkey_key_combo, self.hotkey_apply_button)
        self.setTabOrder(self.hotkey_apply_button, self.read_hotkey_modifier_combo)
        self.setTabOrder(self.read_hotkey_modifier_combo, self.read_hotkey_key_combo)
        self.setTabOrder(self.read_hotkey_key_combo, self.read_hotkey_apply_button)
        self.setTabOrder(self.read_hotkey_apply_button, self.model_cache_list)
        self.setTabOrder(self.model_cache_list, self.model_cache_refresh_button)
        self.setTabOrder(self.model_cache_refresh_button, self.model_cache_delete_button)
        self.setTabOrder(self.model_cache_delete_button, self.language_value)
        self.setTabOrder(self.language_value, self.word_bank_heard_input)
        self.setTabOrder(self.word_bank_heard_input, self.word_bank_correct_input)
        self.setTabOrder(self.word_bank_correct_input, self.word_bank_add_button)
        self.setTabOrder(self.word_bank_add_button, self.word_bank_remove_button)
        self.setTabOrder(self.word_bank_remove_button, self.word_bank_list)
        self.setTabOrder(self.word_bank_list, self.word_bank_save_button)
        self.setTabOrder(self.word_bank_save_button, self.last_words_value)
        self.word_bank_list.setTabKeyNavigation(False)
        self.word_bank_list.setFocusPolicy(Qt.StrongFocus)
        self.word_bank_list.setWrapping(False)
        self.word_bank_list.setWordWrap(False)
        self.setTabOrder(self.last_words_value, self.total_words_value)
        self.setTabOrder(self.total_words_value, self.total_clips_value)
        self.setTabOrder(self.total_clips_value, self.status_value)
        self.setTabOrder(self.status_value, self.dictation_toggle_button)
        self.setTabOrder(self.dictation_toggle_button, self.close_to_tray_button)
        self.model_combo.setFocus()

    def set_status(self, message: str) -> None:
        self.status_value.setText(message)
        self.status_value.setCursorPosition(0)

    def focus_status(self) -> None:
        self.status_value.setFocus()
        self.status_value.selectAll()

    def focus_model_status(self) -> None:
        self.model_status_value.setFocus()
        self.model_status_value.selectAll()

    def set_word_stats(self, last_words: int, total_words: int, total_clips: int) -> None:
        self.last_words_value.setText(str(last_words))
        self.total_words_value.setText(str(total_words))
        self.total_clips_value.setText(str(total_clips))

    def set_dictation_enabled(self, enabled: bool) -> None:
        if enabled:
            self.dictation_toggle_button.setText("Disable Dictation")
            self.dictation_toggle_button.setAccessibleName("Disable dictation")
            self.dictation_toggle_button.setAccessibleDescription("Turns Severus dictation shortcuts off.")
        else:
            self.dictation_toggle_button.setText("Enable Dictation")
            self.dictation_toggle_button.setAccessibleName("Enable dictation")
            self.dictation_toggle_button.setAccessibleDescription("Turns Severus dictation shortcuts on.")

    def set_hotkey_value(self, hotkey_text: str) -> None:
        self.hotkey_value.setText(hotkey_text)
        self.hotkey_value.setCursorPosition(0)
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
                is_ready = True
            elif is_ready:
                label = f"{model_name} (ready)"
            else:
                label = f"{model_name} (not ready)"
            self.model_combo.setItemText(i, label)
            model_item = self.model_combo.model().item(i)
            if model_item is not None:
                model_item.setEnabled(is_ready or model_name == active_model)

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

    def set_model_cache_entries(self, entries: list[tuple[str, str, str, bool]]) -> None:
        self.model_cache_list.clear()
        for label, folder_name, _, _ in entries:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, folder_name)
            self.model_cache_list.addItem(item)

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
            self.model_cache_delete_requested.emit(folder_name)

    def _add_or_update_word_bank_entry(self) -> None:
        wrong = self.word_bank_heard_input.text().strip()
        correct = self.word_bank_correct_input.text().strip()
        if not wrong or not correct:
            return
        target = f"{wrong.lower()} -> {correct}"
        for i in range(self.word_bank_list.count()):
            current = self.word_bank_list.item(i).text()
            if current.split("->", 1)[0].strip().lower() == wrong.lower():
                self.word_bank_list.item(i).setText(target)
                return
        self.word_bank_list.addItem(QListWidgetItem(target))

    def _remove_selected_word_bank_entry(self) -> None:
        row = self.word_bank_list.currentRow()
        if row >= 0:
            self.word_bank_list.takeItem(row)

    def _load_selected_word_bank_entry(self, item: QListWidgetItem) -> None:
        text = item.text()
        if "->" not in text:
            return
        left, right = text.split("->", 1)
        self.word_bank_heard_input.setText(left.strip())
        self.word_bank_correct_input.setText(right.strip())

    def _toggle_advanced_settings(self) -> None:
        self._set_advanced_groups_visible(not self._advanced_visible)

    def _set_advanced_groups_visible(self, visible: bool) -> None:
        self._advanced_visible = visible
        self.settings_toggle_button.setChecked(visible)
        for group in self._advanced_groups:
            group.setVisible(visible)
        self.settings_toggle_button.setText("Hide More Settings" if visible else "Show More Settings")
        self.settings_toggle_button.setAccessibleName("Hide more settings" if visible else "Show more settings")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self.model_combo.setFocus()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        event.ignore()
        self.hide()
