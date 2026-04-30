from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
import winsound
from ctypes import wintypes, windll
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .audio import AudioRecorder
from .audio_ducking import SystemAudioDucker
from .config import AppConfig
from .insertion import TextInserter
from .word_bank import WordBank
from .whisper_engine import WhisperEngine


LOGGER = logging.getLogger(__name__)
DICTATION_BEGIN_SOUND = Path(__file__).resolve().parent / "dictation_begin.wav"
DICTATION_END_SOUND = Path(__file__).resolve().parent / "reverse_dictation_end.mp3"


class DictationController(QObject):
    status_changed = Signal(str)
    transcript_ready = Signal(str)
    error_occurred = Signal(str)
    recording_changed = Signal(bool)
    busy_changed = Signal(bool)
    model_preload_finished = Signal(str, bool, str)

    def __init__(self, config: AppConfig, model_cache_dir, word_bank: WordBank) -> None:  # noqa: ANN001
        super().__init__()
        self._config = config
        self._recorder = AudioRecorder(sample_rate=16_000)
        self._inserter = TextInserter()
        self._audio_ducker = SystemAudioDucker()
        self._word_bank = word_bank
        self._engine = WhisperEngine(
            model_name=config.model_name,
            language=config.language,
            runtime_mode=config.runtime_mode,
            model_cache_dir=model_cache_dir,
            status_callback=self.status_changed.emit,
        )
        self._busy_lock = threading.Lock()
        self._speech_lock = threading.Lock()
        self._is_busy = False
        self._is_preloading = False
        self._last_transcript = ""

    @property
    def is_busy(self) -> bool:
        with self._busy_lock:
            return self._is_busy

    @property
    def is_preloading(self) -> bool:
        with self._busy_lock:
            return self._is_preloading

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    def set_model(self, model_name: str) -> None:
        self._engine.update_model(model_name)

    def preload_model_async(self, model_name: str | None = None) -> None:
        with self._busy_lock:
            if self._is_preloading:
                self.status_changed.emit("Model change already in progress.")
                return
            self._is_preloading = True
        self.busy_changed.emit(True)
        worker = threading.Thread(target=self._preload_model, args=(model_name,), daemon=True)
        worker.start()

    def start_recording(self) -> None:
        if self.is_preloading:
            self.status_changed.emit("Model is still preparing. Please wait for model ready.")
            return
        if self.is_busy:
            self.status_changed.emit("Please wait. Transcription in progress.")
            return
        if self._recorder.is_recording:
            return
        try:
            self._audio_ducker.duck()
            self._recorder.start()
            winsound.PlaySound(str(DICTATION_BEGIN_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.recording_changed.emit(True)
            self.status_changed.emit("Recording. Press Ctrl+F9 again to stop and transcribe.")
        except Exception as exc:
            self._audio_ducker.restore()
            LOGGER.exception("Microphone start failed")
            self.error_occurred.emit(f"Unable to start microphone ({exc}).")

    def stop_recording_and_transcribe(self) -> None:
        if not self._recorder.is_recording:
            return
        audio = self._recorder.stop()
        self._audio_ducker.restore()
        self._play_end_sound()
        self.recording_changed.emit(False)
        if audio.size == 0:
            self.status_changed.emit("No audio captured.")
            return

        with self._busy_lock:
            self._is_busy = True
        self.busy_changed.emit(True)
        self.status_changed.emit("Transcribing locally...")
        worker = threading.Thread(target=self._transcribe_and_insert, args=(audio,), daemon=True)
        worker.start()

    def cancel_recording(self) -> None:
        if not self._recorder.is_recording:
            return
        self._recorder.stop()
        self._audio_ducker.restore()
        self.recording_changed.emit(False)
        self.status_changed.emit("Recording canceled.")

    def read_last_transcript_aloud(self) -> None:
        text = self._last_transcript.strip()
        if not text:
            self.status_changed.emit("No dictated text available to read aloud yet.")
            return
        self.status_changed.emit("Reading dictated text aloud...")
        worker = threading.Thread(target=self._speak_text, args=(text,), daemon=True)
        worker.start()

    def _transcribe_and_insert(self, audio) -> None:  # noqa: ANN001
        try:
            self.status_changed.emit("Model ready check in progress...")
            text = self._engine.transcribe(audio)
            text = self._word_bank.apply(text)
            text = self._finalize_transcript(text)
            if not text:
                self.status_changed.emit("No speech detected.")
                return
            self._last_transcript = text
            self.status_changed.emit("Model ready. Transcript captured.")
            self.transcript_ready.emit(text)
            self.status_changed.emit("Inserting transcript...")
            inserted, msg = self._inserter.insert(text)
            self.status_changed.emit(msg)
            if not inserted:
                self.error_occurred.emit(msg)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Transcription flow failed")
            self.error_occurred.emit(f"Transcription failed ({exc}).")
        finally:
            with self._busy_lock:
                self._is_busy = False
            self.busy_changed.emit(False)

    def _preload_model(self, model_name: str | None = None) -> None:
        requested_model = model_name or self._config.model_name
        previous_model = self._config.model_name
        try:
            if model_name is not None:
                self.set_model(model_name)
            self.status_changed.emit("Preparing selected model...")
            self._engine.warm_model()
            self.status_changed.emit("Model ready.")
            self.model_preload_finished.emit(requested_model, True, "")
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Model preload failed")
            if model_name is not None and previous_model != model_name:
                self.set_model(previous_model)
            self.error_occurred.emit(f"Model preload failed ({exc}).")
            self.model_preload_finished.emit(requested_model, False, str(exc))
        finally:
            with self._busy_lock:
                self._is_preloading = False
                should_emit_idle = not self._is_busy
            if should_emit_idle:
                self.busy_changed.emit(False)

    def _play_end_sound(self) -> None:
        if not DICTATION_END_SOUND.exists():
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return
        alias = f"dictation_end_{int(time.time() * 1000)}"
        mci_send_string = windll.winmm.mciSendStringW
        mci_send_string.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
        mci_send_string.restype = wintypes.UINT
        mci_send_string(f'open "{DICTATION_END_SOUND}" type mpegvideo alias {alias}', None, 0, 0)
        mci_send_string(f"play {alias} from 0", None, 0, 0)

    def _speak_text(self, text: str) -> None:
        escaped = text.replace("'", "''")
        cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.Speak('{escaped}');"
        )
        try:
            with self._speech_lock:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            self.status_changed.emit("Read aloud complete.")
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Read-aloud failed")
            self.error_occurred.emit(f"Read-aloud failed ({exc}).")

    @staticmethod
    def _finalize_transcript(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        if re.search(r"[.!?][\"')\]]*$", cleaned):
            return cleaned
        if cleaned[-1].isalnum() or cleaned[-1] in ("\"", "'", ")", "]"):
            return f"{cleaned}."
        return cleaned
