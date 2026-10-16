from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
import numpy as np
from SpeakToBridge.amd_whisper import AmdWhisperModel


class GpuWarmupTests(unittest.TestCase):
    def test_only_warmup_has_short_generation_limit(self):
        model = AmdWhisperModel.__new__(AmdWhisperModel)
        model._device = 'cuda:0'
        model._torch = SimpleNamespace(float16='fp16', inference_mode=nullcontext)
        tensor = Mock()
        model._processor = Mock(return_value={'input_features': tensor, 'attention_mask': tensor})
        model._processor.batch_decode.return_value = ['Test dictation.']
        model._model = Mock()
        model.transcribe(np.zeros(16000), 'en', '', {}, _warmup=True)
        self.assertEqual(model._model.generate.call_args.kwargs['max_new_tokens'], 2)
        self.assertEqual(model._model.generate.call_args.kwargs['num_beams'], 4)
        text = model.transcribe(np.ones(16000), 'en', '', {})
        self.assertEqual(text, 'Test dictation.')
        self.assertNotIn('max_new_tokens', model._model.generate.call_args.kwargs)
        self.assertEqual(model._model.generate.call_args.kwargs['num_beams'], 4)
        self.assertTrue(model._model.generate.call_args.kwargs['return_timestamps'])
