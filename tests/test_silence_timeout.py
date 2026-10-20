import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from SpeakToBridge.silence_monitor import SpeechSilenceMonitor
from SpeakToBridge.audio import AudioRecorder


class SilenceTimeoutTests(unittest.TestCase):
    def monitor(self, audio=None, captured_at=0):
        audio = np.zeros(32000, dtype=np.float32) if audio is None else audio
        monitor = SpeechSilenceMonitor(lambda: (audio, captured_at), Mock(), Mock())
        monitor._last_speech_at = 0
        return monitor

    def test_thirty_seconds_without_speech_times_out(self):
        monitor = self.monitor()
        model = lambda a: np.zeros(len(a) // 512)
        self.assertFalse(monitor._check_silence(model, 29.99))
        self.assertTrue(monitor._check_silence(model, 30))

    def test_speech_resets_timeout_instead_of_limiting_total_duration(self):
        monitor = self.monitor(captured_at=90)
        speech = lambda a: np.ones(len(a) // 512)
        self.assertFalse(monitor._check_silence(speech, 90))
        silent = lambda a: np.zeros(len(a) // 512)
        self.assertFalse(monitor._check_silence(silent, 119.99))
        self.assertTrue(monitor._check_silence(silent, 120))

    def test_stale_speech_does_not_reset_timeout_forever(self):
        monitor = self.monitor(captured_at=5)
        model = lambda a: np.ones(len(a) // 512)
        self.assertFalse(monitor._check_silence(model, 5))
        self.assertTrue(monitor._check_silence(model, 35))

    def test_background_noise_without_speech_still_times_out(self):
        monitor = self.monitor(np.full(32000, 0.2, dtype=np.float32), captured_at=30)
        self.assertTrue(monitor._check_silence(lambda a: np.zeros(len(a) // 512), 30))

    def test_snapshot_is_limited_to_recent_audio(self):
        recorder = AudioRecorder(sample_rate=10)
        recorder._frames = [np.full((10, 1), i, dtype=np.float32) for i in range(100)]
        recorder._last_frame_time = 123
        audio, at = recorder.recent_audio(2)
        self.assertEqual(len(audio), 20)
        self.assertEqual(at, 123)
        np.testing.assert_array_equal(audio, np.r_[np.full(10, 98), np.full(10, 99)])

    def test_old_timeout_cannot_stop_a_new_recording(self):
        from SpeakToBridge.controller import DictationController

        controller = SimpleNamespace(
            _recording_generation=2,
            _recorder=SimpleNamespace(is_recording=True),
            _microphone_test_active=False,
            stop_recording_and_transcribe=Mock(),
        )
        DictationController._on_silence_timeout(controller, 1)
        controller.stop_recording_and_transcribe.assert_not_called()
        DictationController._on_silence_timeout(controller, 2)
        controller.stop_recording_and_transcribe.assert_called_once_with(
            silence_reached=True
        )

    def test_microphone_check_not_stopped_by_dictation_timeout(self):
        from SpeakToBridge.controller import DictationController

        controller = SimpleNamespace(
            _recording_generation=2,
            _recorder=SimpleNamespace(is_recording=True),
            _microphone_test_active=True,
            stop_recording_and_transcribe=Mock(),
        )
        DictationController._on_silence_timeout(controller, 2)
        controller.stop_recording_and_transcribe.assert_not_called()
