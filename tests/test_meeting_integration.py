import os, tempfile, time, wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from SpeakToBridge.app import SpeakToBridgeRuntime


class MeetingIntegrationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_real_window_runtime_import_notes_edit_and_export(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {"LOCALAPPDATA": temporary}),
            patch("SpeakToBridge.app.HoldHotkeyListener") as hotkey,
            patch("SpeakToBridge.app.DictationController") as controller,
            patch(
                "SpeakToBridge.meeting_notes.generate_meeting_notes",
                return_value="## Summary\nAlice will send the report.\n\n## Action items\n- [ ] Send report",
            ),
        ):
            hk = hotkey.return_value
            hk.activation_hotkey_display = "Ctrl+F9"
            hk.read_hotkey_display = "Ctrl+F8"
            ctl = controller.return_value
            ctl.runtime_description = "CPU (INT8)"
            ctl.is_recording = False
            ctl.is_busy = False
            ctl.is_preloading = False
            ctl._engine.transcribe.return_value = (
                "Alice will send the report by Friday."
            )
            runtime = SpeakToBridgeRuntime(self.app)
            try:
                self.assertEqual(runtime._window.mode_tabs.tabText(1), "Meetings")
                panel = runtime._window.meeting_panel
                self.assertEqual(panel.source.currentData(), "microphone")
                fixture = Path(temporary) / "clip.wav"
                with wave.open(str(fixture), "wb") as handle:
                    handle.setnchannels(1)
                    handle.setsampwidth(2)
                    handle.setframerate(16000)
                    handle.writeframes(b"\0\0" * 16000)
                runtime._import_meeting(str(fixture), "Integration meeting", False)
                panel.notes.setPlainText("My manual note must survive.")
                session = runtime._meeting_session
                session._thread.join(5)
                self.assertFalse(session._thread.is_alive())
                deadline = time.monotonic() + 3
                while (
                    runtime._meeting_session is not None and time.monotonic() < deadline
                ):
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertIsNone(runtime._meeting_session)
                self.assertIn(
                    "Alice will send the report", panel.transcript.toPlainText()
                )
                self.assertIn("My manual note must survive.", panel.notes.toPlainText())
                self.assertIn("AI-generated draft notes", panel.notes.toPlainText())
                self.assertIn("Action items", panel.notes.toPlainText())
                self.assertFalse(panel.stop_button.isEnabled())
                self.assertTrue(panel.start_button.isEnabled())
                output = Path(temporary) / "export.md"
                runtime._export_meeting(str(output))
                self.assertIn(
                    "My manual note must survive.", output.read_text(encoding="utf-8")
                )
                self.assertIn("## Transcript", output.read_text(encoding="utf-8"))
                self.assertFalse(hasattr(runtime._window, "cancel_recording_button"))
            finally:
                runtime.shutdown()
                runtime._window.deleteLater()
                self.app.processEvents()
