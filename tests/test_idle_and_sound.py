import io
import signal
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from SpeakToBridge.sound_feedback import SoundFeedbackPlayer
from scripts import wsl_worker


class FeedbackTests(unittest.TestCase):
    def test_completion_interrupts_processing_instead_of_waiting_for_duration(self):
        started = threading.Event()
        completed = threading.Event()
        interrupted = threading.Event()
        def playback(path, alias, interrupt):
            if path.name == "processing.mp3":
                started.set()
                if interrupt.wait(3):
                    interrupted.set()
            else:
                completed.set()
        with tempfile.TemporaryDirectory() as temp:
            processing = Path(temp)/"processing.mp3"
            success = Path(temp)/"success.mp3"
            processing.touch(); success.touch()
            with patch.object(SoundFeedbackPlayer, "_play_blocking", side_effect=playback):
                player = SoundFeedbackPlayer()
                try:
                    player.play(processing)
                    self.assertTrue(started.wait(1))
                    player.play(success)
                    self.assertTrue(completed.wait(1), "Completion waited behind processing")
                    self.assertTrue(interrupted.is_set())
                finally:
                    player.close()
                    player._worker.join(1)
                self.assertFalse(player._worker.is_alive())

    def test_close_interrupts_active_cue(self):
        started = threading.Event()
        def playback(path, alias, interrupt):
            started.set()
            interrupt.wait(3)
        with tempfile.TemporaryDirectory() as temp:
            cue = Path(temp)/"cue.mp3"; cue.touch()
            with patch.object(SoundFeedbackPlayer, "_play_blocking", side_effect=playback):
                player = SoundFeedbackPlayer()
                player.play(cue)
                self.assertTrue(started.wait(1))
                player.close()
                player._worker.join(1)
                self.assertFalse(player._worker.is_alive())


class IdleWorkerTests(unittest.TestCase):
    def test_pause_precedes_reply_and_resume_precedes_request(self):
        timeline = []
        child = Mock(pid=123)
        child.poll.return_value = None
        child.stdout = io.StringIO('{"status":"loading"}\n{"ready":true}\n{"text":"hello"}\n')
        child.stdin.write.side_effect = lambda request: timeline.append("request")
        signals = SimpleNamespace(SIGSTOP=19, SIGCONT=18)
        def kill(pid, action):
            self.assertEqual(pid, 123)
            timeline.append("stop" if action == 19 else "continue")
        def send(reply):
            timeline.append("ready" if "ready" in reply else "text" if "text" in reply else "status")
        with patch.object(wsl_worker.subprocess, "Popen", return_value=child), \
             patch.object(wsl_worker.os, "kill", side_effect=kill), \
             patch.object(wsl_worker, "signal", signals), \
             patch.object(wsl_worker, "send", side_effect=send), \
             patch.object(wsl_worker.sys, "stdin", io.StringIO('{"audio":"data"}\n')):
            result = wsl_worker.supervise_gpu_worker(SimpleNamespace(cache=Path("cache"), model="tiny"))
        self.assertEqual(result, 0)
        self.assertEqual(timeline, ["status", "stop", "ready", "continue", "request", "stop", "text", "continue"])
        child.stdin.close.assert_called_once()
        child.wait.assert_called_once_with(timeout=5)

    def test_failed_gpu_request_exits_without_pausing_unfinished_work(self):
        child = Mock(pid=123)
        child.poll.return_value = None
        child.stdout = io.StringIO('{"ready":true}\n{"error":"GPU failed"}\n')
        signals = SimpleNamespace(SIGSTOP=19, SIGCONT=18)
        with patch.object(wsl_worker.subprocess, "Popen", return_value=child), \
             patch.object(wsl_worker.os, "kill") as kill, \
             patch.object(wsl_worker, "signal", signals), \
             patch.object(wsl_worker, "send") as send, \
             patch.object(wsl_worker.sys, "stdin", io.StringIO('{"audio":"data"}\n')):
            result = wsl_worker.supervise_gpu_worker(SimpleNamespace(cache=Path("cache"), model="tiny"))
        self.assertEqual(result, 1)
        self.assertEqual([call.args[1] for call in kill.call_args_list], [19,18,18])
        send.assert_called_with({"error":"GPU failed"})
        child.stdin.close.assert_called_once()


class PreparationTests(unittest.TestCase):
    def test_recording_preparation_and_dictation_share_one_model_load(self):
        from SpeakToBridge.whisper_engine import WhisperEngine
        entered = threading.Event()
        release = threading.Event()
        model = Mock()
        def load(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return model
        with patch("SpeakToBridge.whisper_engine._create_cpu_model", side_effect=load) as loader, \
             patch("SpeakToBridge.whisper_engine.rocm_import_attempted", return_value=False), \
             patch("SpeakToBridge.whisper_engine.rocm_runtime_installed", return_value=False), \
             patch.dict(__import__('sys').modules, {"torch":None}):
            engine = WhisperEngine("tiny", "en", "cpu", "off", Path("unused"))
            engine.prepare_async()
            self.assertTrue(entered.wait(1))
            engine.prepare_async()
            foreground = threading.Thread(target=engine.warm_model)
            foreground.start()
            release.set()
            foreground.join(2)
            engine._preparation_thread.join(2)
            self.assertFalse(foreground.is_alive())
            self.assertIs(engine._model, model)
            loader.assert_called_once()
            engine.close()
            with self.assertRaises(RuntimeError):
                engine.warm_model()
