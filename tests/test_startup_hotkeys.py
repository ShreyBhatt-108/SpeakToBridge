import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pynput import keyboard
from SpeakToBridge.hotkey import HoldHotkeyListener
from SpeakToBridge.whisper_engine import WhisperEngine


class NativeHotkeyTests(unittest.TestCase):
    def setUp(self):
        self.keys = set()
        self.listener = HoldHotkeyListener()
        self.listener.set_activation_hotkey("ctrl+win")
        self.listener._get_async_key_state = lambda vk: 0x8000 if vk in self.keys else 0
        self.fired = Mock()
        self.read = Mock()
        self.listener.hotkey_pressed.connect(self.fired)
        self.listener.read_hotkey_pressed.connect(self.read)

    def event(self, vk, down=True, deliver=True):
        if deliver:
            self.assertFalse(
                self.listener._on_windows_event(
                    0x100 if down else 0x101, SimpleNamespace(vkCode=vk)
                )
            )
        if down:
            self.keys.add(vk)
        else:
            self.keys.discard(vk)

    def test_lost_ctrl_release_cannot_make_windows_alone_toggle(self):
        self.event(0xA2)
        self.event(0xA2, False, deliver=False)
        self.event(0x5B)
        self.fired.assert_not_called()
        self.assertNotIn("ctrl", self.listener._pressed_modifiers)

    def test_lost_releases_allow_next_full_chord_to_stop(self):
        self.event(0xA2)
        self.event(0x5B)
        self.event(0x5B, False, deliver=False)
        self.event(0xA2, False, deliver=False)
        self.event(0xA2)
        self.event(0x5B)
        self.assertEqual(self.fired.call_count, 2)

    def test_repeat_keydown_does_not_toggle_again(self):
        self.event(0xA2)
        self.event(0x5B)
        for _ in range(8):
            self.event(0x5B)
        self.fired.assert_called_once()

    def test_one_side_ctrl_release_keeps_other_side_held(self):
        self.event(0xA2)
        self.event(0xA3)
        self.event(0x5B)
        self.event(0xA2, False)
        self.event(0x5B)
        self.fired.assert_called_once()
        self.event(0x5B, False)
        self.event(0x5B)
        self.assertEqual(self.fired.call_count, 2)

    def test_right_ctrl_and_right_windows(self):
        self.event(0xA3)
        self.event(0x5C)
        self.fired.assert_called_once()

    def test_read_hotkey_recovers_missed_release(self):
        self.event(0xA2)
        self.event(0x77)
        self.event(0x77, False, deliver=False)
        self.event(0x77)
        self.assertEqual(self.read.call_count, 2)
        self.fired.assert_not_called()

    def test_windows_alone_cannot_be_configured_as_win_plus_win(self):
        with self.assertRaises(ValueError):
            self.listener.set_activation_hotkey("win+win")

    def test_letter_hotkey_uses_virtual_key(self):
        self.listener.set_activation_hotkey("ctrl+b")
        self.event(0xA2)
        self.event(ord("B"))
        self.fired.assert_called_once()


class PreparationRegressionTests(unittest.TestCase):
    def test_slow_runtime_discovery_does_not_block_gui_prepare_call(self):
        entered = threading.Event()
        release = threading.Event()
        returned = threading.Event()
        engine = WhisperEngine("tiny", "en", "cpu", "off", Path("unused"))

        def resolve():
            entered.set()
            self.assertTrue(release.wait(3))
            return "cpu", "int8"

        with (
            patch.object(engine, "_resolve_runtime", side_effect=resolve),
            patch(
                "SpeakToBridge.whisper_engine._create_cpu_model", return_value=Mock()
            ) as load,
            patch(
                "SpeakToBridge.whisper_engine.rocm_runtime_installed",
                return_value=False,
            ),
            patch(
                "SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=False
            ),
        ):
            engine.prepare_async()
            self.assertTrue(entered.wait(1))
            request = threading.Thread(
                target=lambda: (engine.prepare_async(), returned.set())
            )
            request.start()
            try:
                self.assertTrue(returned.wait(0.3), "GUI blocked on GPU discovery")
            finally:
                release.set()
                request.join(2)
                engine._preparation_thread.join(2)
            load.assert_called_once()
            engine.close()

    def test_runtime_discovery_failure_releases_preparation_gate(self):
        engine = WhisperEngine("tiny", "en", "cpu", "off", Path("unused"))
        with patch.object(
            engine, "_resolve_runtime", side_effect=ValueError("discovery failed")
        ):
            with self.assertRaises(ValueError):
                engine.warm_model()
        self.assertFalse(engine._loading_in_progress)
        engine.close()

    def test_startup_prepares_selected_model_without_recording(self):
        from SpeakToBridge.app import SpeakToBridgeRuntime

        controller = Mock(is_recording=False, is_busy=False)
        runtime = SimpleNamespace(
            _dictation_enabled=True,
            _controller=controller,
            _config=SimpleNamespace(model_name="small"),
        )
        SpeakToBridgeRuntime._prepare_startup_model(runtime)
        controller.preload_model_async.assert_called_once_with()
        controller.start_recording.assert_not_called()
        self.assertEqual(runtime._pending_model_name, "small")

    def test_recording_stop_takes_priority_over_preparation_and_busy_flags(self):
        from SpeakToBridge.app import SpeakToBridgeRuntime

        controller = Mock(
            is_recording=True,
            is_microphone_test_recording=False,
            is_preloading=True,
            is_busy=True,
        )
        runtime = SimpleNamespace(
            _controller=controller, _model_cache_delete_in_progress=True
        )
        SpeakToBridgeRuntime._on_hotkey_pressed(runtime)
        controller.stop_recording_and_transcribe.assert_called_once_with()

    def test_preload_finished_opens_gate_before_ready_signal(self):
        from SpeakToBridge.controller import DictationController

        # Controller is constructed below with hardware dependencies mocked.
        # Exercise the real Qt object/signals with hardware dependencies mocked.
        from SpeakToBridge.config import AppConfig

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("SpeakToBridge.controller.AudioRecorder"),
            patch("SpeakToBridge.controller.TextInserter"),
            patch("SpeakToBridge.controller.SystemAudioDucker"),
            patch("SpeakToBridge.controller.SoundFeedbackPlayer"),
            patch("SpeakToBridge.controller.WhisperEngine"),
        ):
            controller = DictationController(AppConfig(), Path(tmp), Mock())
            controller._is_preloading = True
            observed = []
            controller.model_preload_finished.connect(
                lambda *args: observed.append(controller.is_preloading)
            )
            controller._preload_model()
            self.assertEqual(observed, [False])
            controller.shutdown()
