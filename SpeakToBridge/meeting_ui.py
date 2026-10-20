from __future__ import annotations
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QPlainTextEdit,
    QLabel,
    QFileDialog,
)
from .meetings import timestamp


class MeetingPanel(QWidget):
    start_requested = Signal(str, str, bool)
    stop_requested = Signal()
    import_requested = Signal(str, str, bool)
    open_saved_requested = Signal(str)
    notes_changed = Signal(str)
    export_requested = Signal(str)
    generate_notes_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        description = QLabel(
            "Record your microphone or transcribe a recording, with local AI summaries and action items. First use downloads a 1.28 GB notes model; then notes work offline on CPU. Transcription uses your selected device."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.title = QLineEdit("Meeting")
        self.title.setAccessibleName("Meeting title")
        form.addRow("Title:", self.title)
        self.source = QComboBox()
        self.source.setAccessibleName("Meeting audio source")
        self.source.addItem("Microphone", "microphone")
        form.addRow("Record:", self.source)
        self.keep_audio = QCheckBox("Keep audio recordings after transcription")
        self.keep_audio.setToolTip(
            "Unprocessed audio is always retained if transcription fails."
        )
        form.addRow("", self.keep_audio)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.start_button = QPushButton("Start Meeting")
        self.stop_button = QPushButton("Stop Meeting")
        self.import_button = QPushButton("Transcribe Audio File")
        self.start_button.clicked.connect(
            lambda: self.start_requested.emit(
                self.title.text(),
                self.source.currentData(),
                self.keep_audio.isChecked(),
            )
        )
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.stop_button.setEnabled(False)
        self.import_button.clicked.connect(self._import)
        for button in (self.start_button, self.stop_button, self.import_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel(
            "Ready. Meetings do not use the dictation silence timeout or recording limit."
        )
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Meeting status")
        layout.addWidget(self.status)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setAccessibleName("Timestamped meeting transcript")
        self.transcript.setPlaceholderText(
            "The transcript appears here as audio is processed."
        )
        layout.addWidget(self.transcript, 2)
        layout.addWidget(QLabel("Your notes:"))
        self.notes = QPlainTextEdit()
        self.notes.setAccessibleName("Editable meeting notes")
        self.notes.setPlaceholderText(
            "Write key points, decisions and action items. Changes save automatically."
        )
        self.notes.setEnabled(False)
        layout.addWidget(self.notes, 1)
        review = QLabel(
            "AI notes are a draft. Check names, decisions and action items against the transcript before relying on them."
        )
        review.setWordWrap(True)
        layout.addWidget(review)
        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(500)
        self._notes_timer.timeout.connect(
            lambda: self.notes_changed.emit(self.notes.toPlainText())
        )
        self.notes.textChanged.connect(lambda: self._notes_timer.start())
        saved = QHBoxLayout()
        self.history = QComboBox()
        self.history.setAccessibleName("Saved meetings")
        self.history.addItem("Select a saved meeting", "")
        self.open_button = QPushButton("Open Meeting")
        self.open_button.clicked.connect(
            lambda: self.open_saved_requested.emit(self.history.currentData() or "")
        )
        self.export_button = QPushButton("Export Notes and Transcript")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export)
        self.generate_button = QPushButton("Generate AI Notes")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.generate_notes_requested.emit)
        saved.addWidget(self.history, 1)
        saved.addWidget(self.open_button)
        saved.addWidget(self.generate_button)
        saved.addWidget(self.export_button)
        layout.addLayout(saved)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Transcribe a recording",
            "",
            "Audio and video (*.wav *.mp3 *.m4a *.flac *.ogg *.mp4 *.wma);;All files (*)",
        )
        if path:
            self.import_requested.emit(
                path, self.title.text(), self.keep_audio.isChecked()
            )

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export meeting notes",
            "Meeting notes.md",
            "Markdown (*.md);;Text (*.txt)",
        )
        if path:
            self.export_requested.emit(path)

    def set_active(self, active, finishing=False):
        self.start_button.setEnabled(not active)
        self.import_button.setEnabled(not active)
        self.stop_button.setEnabled(active and not finishing)
        self.generate_button.setEnabled(not active and self.notes.isEnabled())
        for widget in (
            self.source,
            self.keep_audio,
            self.history,
            self.open_button,
            self.title,
        ):
            widget.setEnabled(not active)

    def set_document(self, metadata, entries, notes):
        self._notes_timer.stop()
        self.title.setText(metadata["title"])
        self.transcript.setPlainText("\n\n".join(self.format_entry(e) for e in entries))
        self.notes.blockSignals(True)
        self.notes.setPlainText(notes)
        self.notes.blockSignals(False)
        self.notes.setEnabled(True)
        self.export_button.setEnabled(True)
        self.generate_button.setEnabled(True)

    @staticmethod
    def format_entry(entry):
        return (
            f"[{timestamp(entry['start_seconds'])}] {entry['source']}: {entry['text']}"
        )

    def append_entry(self, entry):
        # Preserve the reader's cursor/selection rather than moving focus on updates.
        cursor = self.transcript.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        self.transcript.appendPlainText(self.format_entry(entry) + "\n")
        cursor.setPosition(anchor)
        cursor.setPosition(position, cursor.MoveMode.KeepAnchor)
        self.transcript.setTextCursor(cursor)

    def append_generated_notes(self, text):
        self.flush_notes()
        self.notes.appendPlainText("\n\n# AI-generated draft notes\n\n" + text)
        self.flush_notes()

    def flush_notes(self):
        if self.notes.isEnabled() and self._notes_timer.isActive():
            self._notes_timer.stop()
            self.notes_changed.emit(self.notes.toPlainText())

    def set_history(self, items):
        self.history.clear()
        self.history.addItem("Select a saved meeting", "")
        for label, folder in items:
            self.history.addItem(label, folder)
