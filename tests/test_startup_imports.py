from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StartupImportTests(unittest.TestCase):
    def test_inference_import_does_not_load_optional_torch(self):
        # Model the real loader rejection: this optional package raises OSError,
        # rather than ImportError, if CTranslate2 tries to load it at startup.
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "torch.py").write_text(
                "raise OSError(4551, 'Application Control blocked test runtime')",
                encoding="utf-8",
            )
            code = """
import sys
from SpeakToBridge.whisper_engine import WhisperEngine
assert 'torch' not in sys.modules, 'Optional torch import guard leaked'
import huggingface_hub.constants
assert huggingface_hub.constants.HF_HUB_DISABLE_XET, 'Xet flag was set after Hub imported'
try:
    import torch
except OSError as error:
    assert error.errno == 4551
else:
    raise AssertionError('Real GPU import must remain available after startup')
"""
            environment = os.environ.copy()
            environment.pop("HF_HUB_DISABLE_XET", None)
            environment["PYTHONPATH"] = os.pathsep.join(
                [directory, str(Path(__file__).resolve().parent.parent)]
            )
            result = subprocess.run(
                [sys.executable, "-c", code], env=environment,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cpu_diagnostic_does_not_load_optional_torch(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "torch.py").write_text(
                "raise AssertionError('CPU diagnostic imported GPU runtime')",
                encoding="utf-8",
            )
            code = """
import json
import sys
from pathlib import Path
from unittest.mock import patch
from SpeakToBridge.diagnostics import main
output = Path(sys.argv[1])
with patch('SpeakToBridge.diagnostics.subprocess.run', side_effect=RuntimeError('skip hardware query')):
    assert main(['--cpu', '--output', str(output)]) == 0
assert 'torch' not in sys.modules
assert json.loads(output.read_text())['optional_runtime_probe_skipped'] == 'CPU-only diagnostic'
"""
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                [directory, str(Path(__file__).resolve().parent.parent)]
            )
            result = subprocess.run(
                [sys.executable, "-c", code, str(Path(directory, "report.json"))],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
