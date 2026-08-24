from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from SpeakToBridge.config import AppConfig
from SpeakToBridge.controller import DictationController


class SoundSettingTests(unittest.TestCase):
    def test_sound_effects_default_to_enabled(self) -> None:
        self.assertTrue(AppConfig.from_dict({}).sound_effects_enabled)

    def test_saved_boolean_is_loaded(self) -> None:
        self.assertFalse(AppConfig.from_dict({"sound_effects_enabled": False}).sound_effects_enabled)

    def test_non_boolean_value_uses_safe_default(self) -> None:
        self.assertTrue(AppConfig.from_dict({"sound_effects_enabled": "false"}).sound_effects_enabled)

    def test_disabled_setting_suppresses_feedback(self) -> None:
        controller = DictationController.__new__(DictationController)
        controller._config = AppConfig(sound_effects_enabled=False)
        controller._sound_feedback = Mock()

        with patch("SpeakToBridge.controller.winsound.PlaySound") as play_sound:
            controller._play_feedback(Path("cue.mp3"))
            controller._play_feedback(Path("cue.wav"), wav=True)

        controller._sound_feedback.play.assert_not_called()
        play_sound.assert_not_called()

    def test_enabled_setting_routes_feedback_to_correct_player(self) -> None:
        controller = DictationController.__new__(DictationController)
        controller._config = AppConfig(sound_effects_enabled=True)
        controller._sound_feedback = Mock()
        mp3_path = Path("cue.mp3")
        wav_path = Path("cue.wav")

        with patch("SpeakToBridge.controller.winsound.PlaySound") as play_sound:
            controller._play_feedback(mp3_path)
            controller._play_feedback(wav_path, wav=True)

        controller._sound_feedback.play.assert_called_once_with(mp3_path)
        play_sound.assert_called_once()


if __name__ == "__main__":
    unittest.main()
