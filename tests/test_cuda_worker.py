import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from SpeakToBridge.cpu_worker import CpuWhisperWorker
from SpeakToBridge.whisper_engine import WhisperEngine


class CudaWorkerTests(unittest.TestCase):
    def test_cuda_native_crash_retries_same_audio_on_cpu_and_closes_worker(self):
        audio = np.ones(16000, dtype=np.float32)
        worker = Mock(_cpu_worker=True)
        worker.transcribe.side_effect = RuntimeError('Transcription worker stopped unexpectedly')
        cpu = Mock()
        cpu.transcribe.return_value = ([SimpleNamespace(text='Recovered recording')], None)
        engine = WhisperEngine('tiny', 'en', 'cpu_auto_gpu', 'off', Path('unused'))
        with patch.object(engine, '_resolve_runtime', side_effect=[('cuda', 'float16'), ('cpu', 'int8')]), \
             patch('SpeakToBridge.cpu_worker.CpuWhisperWorker', return_value=worker) as factory, \
             patch('SpeakToBridge.whisper_engine.rocm_runtime_installed', return_value=False), \
             patch('SpeakToBridge.whisper_engine.rocm_import_attempted', return_value=False), \
             patch('SpeakToBridge.whisper_engine._create_cpu_model', return_value=cpu):
            self.assertEqual(engine.transcribe(audio), 'Recovered recording')
        factory.assert_called_once_with('tiny', Path('unused'), device='cuda', compute_type='float16')
        worker.close.assert_called_once()
        self.assertIs(cpu.transcribe.call_args.args[0], audio)
        self.assertEqual(engine.runtime_description, 'CPU (INT8)')

    def test_worker_passes_validated_cuda_arguments_without_shell(self):
        process = Mock()
        process.stdout.readline.return_value = '{"ready":true}\n'
        process.poll.return_value = 0
        with patch('SpeakToBridge.cpu_worker.subprocess.Popen', return_value=process) as launch:
            worker = CpuWhisperWorker('tiny', Path('cache with spaces'), device='cuda', compute_type='float16')
            self.assertEqual(launch.call_args.args[0][-4:], ['tiny', 'cache with spaces', 'cuda', 'float16'])
            self.assertNotIn('shell', launch.call_args.kwargs)
            worker.close()
        with patch('SpeakToBridge.cpu_worker.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):
                CpuWhisperWorker('tiny', Path('cache'), device='invalid')
            launch.assert_not_called()
