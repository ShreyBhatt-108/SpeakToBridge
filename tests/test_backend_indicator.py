import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from SpeakToBridge.ui import SettingsWindow
from SpeakToBridge.whisper_engine import WhisperEngine
from SpeakToBridge.controller import DictationController
from SpeakToBridge.config import AppConfig
import numpy as np


class BackendIndicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        return SettingsWindow("tiny", "ctrl+win", "ctrl+f8", 300, False)

    def test_gpu_failure_updates_loaded_backend_without_erasing_last_transcription(self):
        window = self.window()
        window.set_last_transcription_backend("AMD ROCm GPU: 8060S (FP16, WSL)")
        engine = WhisperEngine("tiny", "en", "cpu_auto_gpu", "off", Path("unused-test-cache"),
                               runtime_callback=window.set_loaded_backend)
        with patch("SpeakToBridge.whisper_engine.wsl_enabled", return_value=False), \
             patch("SpeakToBridge.whisper_engine.amd_device", return_value=(0, "8060S")), \
             patch("SpeakToBridge.whisper_engine.AmdWhisperModel"), \
             patch("SpeakToBridge.whisper_engine.WhisperModel"), \
             patch("SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=False):
            def transcribe(audio, prompt):
                engine.warm_model()
                if engine._device != "cpu":
                    raise RuntimeError("GPU inference unavailable")
                return "Recovered on CPU."
            with patch.object(engine, "_transcribe", side_effect=transcribe):
                self.assertEqual(engine.transcribe(np.ones(16000)), "Recovered on CPU.")
            self.assertEqual(window.loaded_backend_value.text(), "CPU (INT8)")
            self.assertIn("GPU", window.last_transcription_backend_value.text())
            engine.update_runtime("cpu")
            self.assertEqual(window.loaded_backend_value.text(), "Not loaded yet")
            self.assertIn("GPU", window.last_transcription_backend_value.text())
        window.close()

    def test_controller_reports_actual_backend_without_modifying_inserted_text(self):
        for backend in ("CPU (INT8)", "AMD ROCm GPU: 8060S (FP16, WSL)"):
            with self.subTest(backend=backend), \
                 patch("SpeakToBridge.controller.AudioRecorder"), \
                 patch("SpeakToBridge.controller.TextInserter"), \
                 patch("SpeakToBridge.controller.SystemAudioDucker"), \
                 patch("SpeakToBridge.controller.SoundFeedbackPlayer"):
                bank = Mock()
                bank.glossary_prompt.return_value = ""
                bank.apply.side_effect = lambda text: text
                controller = DictationController(AppConfig(sound_effects_enabled=False), Path("unused-test-cache"), bank)
                controller._engine = SimpleNamespace(transcribe=Mock(return_value="Hello world."), runtime_description=backend)
                controller._inserter.insert.return_value = (True, "Inserted.")
                window = self.window()
                controller.transcription_backend_changed.connect(window.set_last_transcription_backend)
                controller._transcribe_and_insert(np.ones(16000))
                self.assertEqual(window.last_transcription_backend_value.text(), backend)
                controller._inserter.insert.assert_called_once_with("Hello world.")
                window.close()


class OfflineWslCacheTests(unittest.TestCase):
    def test_complete_shared_model_does_not_contact_hub(self):
        import tempfile
        from scripts.wsl_worker import prepare_model_cache
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            model = cache / "openai-whisper-small"
            model.mkdir()
            for name in ("config.json", "generation_config.json", "preprocessor_config.json",
                         "tokenizer_config.json", "tokenizer.json", "model.safetensors", ".speak_to_bridge_ready"):
                (model / name).write_text("ready")
            with patch("huggingface_hub.snapshot_download", side_effect=AssertionError("Network used")):
                self.assertEqual(prepare_model_cache(cache, "small"), model)


    def test_download_excludes_redundant_fp32_weights(self):
        import fnmatch
        import tempfile
        from scripts.wsl_worker import prepare_model_cache
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            def download(repository, local_dir, allow_patterns, ignore_patterns):
                names = ["model.safetensors", "model.fp32-00001-of-00002.safetensors",
                         "model.fp32-00002-of-00002.safetensors", "model.safetensors.index.fp32.json",
                         "config.json", "generation_config.json", "preprocessor_config.json",
                         "tokenizer_config.json", "tokenizer.json"]
                selected = [name for name in names if any(fnmatch.fnmatch(name,p) for p in allow_patterns)
                            and not any(fnmatch.fnmatch(name,p) for p in ignore_patterns)]
                self.assertEqual([name for name in selected if name.endswith(".safetensors")], ["model.safetensors"])
                self.assertNotIn("model.safetensors.index.fp32.json", selected)
                model = Path(local_dir)
                model.mkdir()
                for name in selected:
                    (model/name).write_text("test fixture")
            with patch("huggingface_hub.snapshot_download", side_effect=download):
                model = prepare_model_cache(cache,"large-v3")
                self.assertTrue((model/".speak_to_bridge_ready").is_file())
