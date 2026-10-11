import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from SpeakToBridge.whisper_engine import WhisperEngine
from SpeakToBridge.wsl_whisper import WslWhisperModel, linux_path


class WslRuntimeTests(unittest.TestCase):
    def test_windows_path_with_spaces_and_no_shell_interpolation(self):
        self.assertEqual(linux_path(Path(r"C:\Users\Example User\models")), "/mnt/c/Users/Example User/models")
        with self.assertRaises(ValueError):
            linux_path(Path(r"\\server\share\models"))

    def test_configured_wsl_skips_native_rocm_and_cpu_does_not_use_wsl(self):
        with patch("SpeakToBridge.whisper_engine.wsl_enabled", return_value=True), \
             patch("SpeakToBridge.whisper_engine.amd_device") as native:
            engine = WhisperEngine("tiny", "en", "amd_gpu", "off", Path("cache"))
            self.assertEqual(engine._resolve_runtime(), ("wsl_rocm", "float16"))
            engine.update_runtime("cpu")
            self.assertEqual(engine._resolve_runtime(), ("cpu", "int8"))
            native.assert_not_called()

    def test_failed_wsl_model_falls_back_without_native_probe(self):
        with patch("SpeakToBridge.whisper_engine.wsl_enabled", return_value=True), \
             patch("SpeakToBridge.whisper_engine.amd_device") as native, \
             patch("SpeakToBridge.whisper_engine.WslWhisperModel", side_effect=RuntimeError("WSL unavailable")), \
             patch("SpeakToBridge.whisper_engine.WhisperModel") as cpu, \
             patch("SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=False):
            engine = WhisperEngine("tiny", "en", "amd_gpu", "off", Path("cache"))
            engine.warm_model()
            self.assertEqual(engine.runtime_description, "CPU (INT8)")
            cpu.assert_called_once()
            native.assert_not_called()

    def test_model_cache_refresh_in_wsl_does_not_import_native_rocm(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from SpeakToBridge.app import SpeakToBridgeRuntime
        with tempfile.TemporaryDirectory() as temp:
            runtime = SimpleNamespace(_config=SimpleNamespace(runtime_mode="amd_gpu"),
                                      _model_cache_dir=Path(temp), model_cache_entries_ready=Mock())
            with patch("SpeakToBridge.wsl_whisper.wsl_enabled", return_value=True), \
                 patch("SpeakToBridge.amd_whisper.amd_device") as native:
                SpeakToBridgeRuntime._load_model_cache_entries(runtime, 1)
                native.assert_not_called()
                runtime.model_cache_entries_ready.emit.assert_called_once()

    def test_materialized_gpu_cache_is_recognized_without_linux_symlinks(self):
        from SpeakToBridge.model_storage import list_cached_models
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"openai-whisper-tiny"
            folder.mkdir()
            for name in ("config.json", "generation_config.json", "preprocessor_config.json",
                         "tokenizer_config.json", "tokenizer.json", "model.safetensors"):
                (folder/name).write_text("test fixture")
            models=list_cached_models(Path(temp))
            self.assertEqual(len(models), 1)
            self.assertEqual((models[0].model_name, models[0].backend, models[0].ready), ("tiny", "AMD ROCm", True))

    def test_real_pipe_transport_preserves_audio_and_prompt_and_stops_on_close(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp)/"fake_worker.py"
            script.write_text('''import sys, json, base64
print(json.dumps({"ready": True, "gpu_matrix_test": True, "amd_gpu": "test GPU"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    assert len(base64.b64decode(request["audio"])) == 16
    assert request["initial_prompt"] == "Word Bank example"
    assert request["language"] == "en"
    print(json.dumps({"text": "verified pipe"}), flush=True)
''', encoding="utf-8")
            with patch("SpeakToBridge.wsl_whisper.worker_command", return_value=[sys.executable, "-u", str(script)]):
                worker = WslWhisperModel("tiny", Path(temp))
                self.assertEqual(worker.transcribe(np.ones(4, dtype=np.float32), "en", "Word Bank example", {"vad_filter": False}), "verified pipe")
                worker.close()
                self.assertEqual(worker._process.returncode, 0)


if __name__ == "__main__":
    unittest.main()
