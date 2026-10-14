from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np

from SpeakToBridge.amd_whisper import AmdWhisperModel, amd_device
from SpeakToBridge.config import AppConfig
from SpeakToBridge.model_storage import is_model_cache_ready, list_cached_models
from SpeakToBridge.whisper_engine import WhisperEngine


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        # Native-runtime tests must not inherit the user's persisted WSL choice.
        selection = patch("SpeakToBridge.whisper_engine.wsl_enabled", return_value=False)
        selection.start()
        self.addCleanup(selection.stop)

    def engine(self, mode="cpu_auto_gpu"):
        return WhisperEngine("tiny", "en", mode, "off", Path("unused-test-cache"))

    def test_rocm_attempt_skips_ctranslate2_cuda_probe(self):
        from SpeakToBridge.whisper_engine import _has_cuda_device
        import builtins
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == "ctranslate2":
                raise AssertionError("ROCm fallback introduced another OpenMP runtime")
            return original(name, *args, **kwargs)
        with patch("SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=True), \
             patch("builtins.__import__", side_effect=guarded):
            self.assertFalse(_has_cuda_device())

    def test_cpu_mode_does_not_probe_gpu(self):
        with patch("SpeakToBridge.whisper_engine.amd_device") as detect:
            self.assertEqual(self.engine("cpu")._resolve_runtime(), ("cpu", "int8"))
            detect.assert_not_called()

    def test_amd_rocm_detection_prefers_8060s_and_rejects_nvidia_torch(self):
        torch = Mock()
        torch.version.hip = "7.2"
        torch.cuda.is_available.return_value = True
        torch.cuda.device_count.return_value = 2
        torch.cuda.get_device_name.side_effect = ["AMD Radeon Other", "AMD Radeon 8060S"]
        with patch.dict(sys.modules, {"torch": torch}):
            self.assertEqual(amd_device(), (1, "AMD Radeon 8060S"))
            torch.version.hip = None
            self.assertIsNone(amd_device())

    def test_auto_selects_rocm_without_passing_amd_to_ctranslate(self):
        model = Mock(spec=AmdWhisperModel)
        with patch("SpeakToBridge.whisper_engine.amd_device", return_value=(0, "AMD Radeon 8060S")), \
             patch("SpeakToBridge.whisper_engine.AmdWhisperModel", return_value=model) as amd, \
             patch("SpeakToBridge.whisper_engine._create_cpu_model") as cpu:
            engine = self.engine()
            engine.warm_model()
            amd.assert_called_once_with("tiny", Path("unused-test-cache"), 0, status_callback=engine._emit_status)
            cpu.assert_not_called()
            self.assertIn("8060S", engine.runtime_description)

    def test_amd_load_failure_falls_back_to_cpu(self):
        with patch.dict(sys.modules, {"torch": None}), \
             patch("SpeakToBridge.whisper_engine.amd_device", return_value=(0, "8060S")), \
             patch("SpeakToBridge.whisper_engine.AmdWhisperModel", side_effect=RuntimeError("driver error")), \
             patch("SpeakToBridge.whisper_engine._create_cpu_model") as cpu:
            engine = self.engine()
            engine.warm_model()
            self.assertEqual(engine.runtime_description, "CPU (INT8)")
            cpu.assert_called_once_with("tiny", device="cpu", compute_type="int8", download_root="unused-test-cache")

    def test_rocm_loaded_cpu_fallback_uses_isolated_worker(self):
        torch = SimpleNamespace(version=SimpleNamespace(hip="7.2"))
        with patch.dict(sys.modules, {"torch": torch}), \
             patch("SpeakToBridge.cpu_worker.CpuWhisperWorker") as worker, \
             patch("SpeakToBridge.whisper_engine._create_cpu_model") as cpu:
            engine = self.engine("cpu")
            engine.warm_model()
            worker.assert_called_once_with("tiny", Path("unused-test-cache"))
            cpu.assert_not_called()
            self.assertEqual(engine.runtime_description, "CPU (INT8)")

    def test_failed_rocm_import_keeps_cpu_in_isolated_worker(self):
        with patch("SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=True), \
             patch("SpeakToBridge.cpu_worker.CpuWhisperWorker") as worker, \
             patch("SpeakToBridge.whisper_engine._create_cpu_model") as cpu:
            engine = self.engine("cpu")
            engine.warm_model()
            worker.assert_called_once_with("tiny", Path("unused-test-cache"))
            cpu.assert_not_called()

    def test_gpu_inference_failure_retries_same_audio_on_cpu_once(self):
        engine = self.engine()
        engine._model = Mock()
        engine._device = "rocm"
        audio = np.ones(16000, dtype=np.float32)
        with patch.object(engine, "_transcribe", side_effect=[RuntimeError("out of memory"), "recovered"]) as transcribe:
            self.assertEqual(engine.transcribe(audio, "custom words"), "recovered")
            self.assertEqual(transcribe.call_count, 2)
            for call in transcribe.call_args_list:
                self.assertIs(call.args[0], audio)
                self.assertEqual(call.args[1], "custom words")
            self.assertTrue(engine._gpu_failed)
            self.assertEqual(engine._resolve_runtime(), ("cpu", "int8"))

    def test_cpu_failure_is_not_retried(self):
        engine = self.engine("cpu")
        with patch.object(engine, "_transcribe", side_effect=RuntimeError("bad model")) as transcribe:
            with self.assertRaises(RuntimeError):
                engine.transcribe(np.ones(10))
            self.assertEqual(transcribe.call_count, 1)

    def test_runtime_change_allows_gpu_retry_and_config_round_trip(self):
        engine = self.engine()
        engine._gpu_failed = True
        engine._model = Mock()
        engine.update_runtime("amd_gpu")
        self.assertFalse(engine._gpu_failed)
        self.assertIsNone(engine._model)
        config = AppConfig.from_dict({"runtime_mode": "amd_gpu"})
        self.assertEqual(AppConfig.from_dict(config.to_dict()).runtime_mode, "amd_gpu")

    def test_long_recording_and_word_bank_prompt_are_preserved(self):
        model = AmdWhisperModel.__new__(AmdWhisperModel)
        model._device = "cuda:0"
        model._torch = MagicMock()
        model._processor = Mock()
        features, mask, prompt = Mock(), Mock(), Mock()
        model._processor.return_value = {"input_features": features, "attention_mask": mask}
        model._processor.get_prompt_ids.return_value = prompt
        model._processor.batch_decode.return_value = [" All of the recording. "]
        model._model = Mock()
        audio = np.zeros(16000 * 61, dtype=np.float32)
        self.assertEqual(model.transcribe(audio, "en", "Shrey", {"vad_filter": False}), "All of the recording.")
        self.assertIs(model._processor.call_args.args[0], audio)
        self.assertFalse(model._processor.call_args.kwargs["truncation"])
        self.assertTrue(model._model.generate.call_args.kwargs["return_timestamps"])
        self.assertEqual(model._model.generate.call_args.kwargs["prompt_condition_type"], "all-segments")

    def test_silence_does_not_generate_hallucinated_text(self):
        model = AmdWhisperModel.__new__(AmdWhisperModel)
        model._processor = Mock()
        with patch("SpeakToBridge.vad.get_speech_timestamps", return_value=[]):
            self.assertEqual(model.transcribe(np.zeros(16000), "en", "", {"vad_filter": True}), "")
        model._processor.assert_not_called()

    def test_amd_cache_lists_complete_models_and_rejects_missing_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "models--openai--whisper-small"
            snapshot = folder / "snapshots" / "revision"
            snapshot.mkdir(parents=True)
            for name in ["config.json", "generation_config.json", "preprocessor_config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors"]:
                (snapshot / name).write_text("{}")
            self.assertTrue(is_model_cache_ready(folder))
            items = list_cached_models(root)
            self.assertEqual(items[0].model_name, "small")
            self.assertEqual(items[0].backend, "AMD ROCm")
            (snapshot / "model.safetensors").unlink()
            (snapshot / "model.safetensors.index.json").write_text('{"weight_map":{"a":"missing.safetensors"}}')
            self.assertFalse(is_model_cache_ready(folder))


if __name__ == "__main__":
    unittest.main()
