from __future__ import annotations

import logging
import re
import subprocess
import threading
import winsound
import os
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .audio import AudioRecorder
from .audio_ducking import SystemAudioDucker
from .config import AppConfig
from .insertion import TextInserter
from .sound_feedback import SoundFeedbackPlayer
from .word_bank import WordBank
from .whisper_engine import WhisperEngine


LOGGER = logging.getLogger(__name__)
DICTATION_BEGIN_SOUND = Path(__file__).resolve().parent / "dictation_begin.wav"
DICTATION_END_SOUND = Path(__file__).resolve().parent / "reverse_dictation_end.mp3"
PROCESSING_SOUND = Path(__file__).resolve().parent / "status_processing.mp3"
SUCCESS_SOUND = Path(__file__).resolve().parent / "status_success.mp3"
FAILURE_SOUND = Path(__file__).resolve().parent / "status_failure.mp3"
SMART_DICTATION_PROMPT = (
    "Produce clean written dictation. Remove filler words (um, uh, er, ah), false starts, and stutters. "
    "Collapse accidental repeated words. Prefer readable punctuation and paragraphing. "
    "When speech clearly indicates list items, format as a bulleted or numbered list. "
    "Respect spoken formatting commands like new line, start list, end list, and quotation marks."
)
SPOKEN_NUMBER_WORDS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


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
        self._recorder = AudioRecorder(
            sample_rate=16_000,
            max_duration_seconds=config.max_recording_seconds,
        )
        self._inserter = TextInserter()
        self._audio_ducker = SystemAudioDucker()
        self._sound_feedback = SoundFeedbackPlayer()
        self._word_bank = word_bank
        self._engine = WhisperEngine(
            model_name=config.model_name,
            language=config.language,
            runtime_mode=config.runtime_mode,
            vad_mode=config.vad_mode,
            model_cache_dir=model_cache_dir,
            status_callback=self.status_changed.emit,
        )
        self._busy_lock = threading.Lock()
        self._speech_lock = threading.Lock()
        self._is_busy = False
        self._is_preloading = False
        self._last_transcript = ""
        self._enabled = True
        self._activation_hotkey_display = config.activation_hotkey.upper()
        self._recording_timer = QTimer(self)
        self._recording_timer.setSingleShot(True)
        self._recording_timer.timeout.connect(self._on_recording_timeout)

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

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_model(self, model_name: str) -> None:
        self._engine.update_model(model_name)

    def set_activation_hotkey_display(self, display: str) -> None:
        self._activation_hotkey_display = display

    def set_max_recording_seconds(self, seconds: int) -> None:
        self._config.max_recording_seconds = int(seconds)
        self._recorder.set_max_duration_seconds(seconds)

    def play_failure_feedback(self) -> None:
        self._sound_feedback.play(FAILURE_SOUND)

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
        if not self._enabled:
            self.status_changed.emit("Dictation is disabled.")
            return
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
            self._recording_timer.start(self._config.max_recording_seconds * 1000)
            winsound.PlaySound(str(DICTATION_BEGIN_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.recording_changed.emit(True)
            self.status_changed.emit(
                f"Recording. Press {self._activation_hotkey_display} again to stop and transcribe. "
                f"Maximum length: {self._config.max_recording_seconds} seconds."
            )
        except Exception as exc:
            self._recording_timer.stop()
            self._audio_ducker.restore()
            LOGGER.exception("Microphone start failed")
            self.error_occurred.emit(f"Unable to start microphone ({exc}).")

    def stop_recording_and_transcribe(self, maximum_reached: bool = False) -> None:
        if not self._recorder.is_recording:
            return
        self._recording_timer.stop()
        audio = self._recorder.stop()
        self._audio_ducker.restore()
        self._sound_feedback.play(DICTATION_END_SOUND)
        self.recording_changed.emit(False)
        if audio.size == 0:
            self._sound_feedback.play(FAILURE_SOUND)
            self.status_changed.emit("No audio captured.")
            return

        with self._busy_lock:
            self._is_busy = True
        self.busy_changed.emit(True)
        self._sound_feedback.play(PROCESSING_SOUND)
        if maximum_reached:
            self.status_changed.emit("Maximum recording length reached. Recording stopped; transcribing locally...")
        else:
            self.status_changed.emit("Transcribing locally...")
        worker = threading.Thread(target=self._transcribe_and_insert, args=(audio,), daemon=True)
        worker.start()

    def cancel_recording(self) -> None:
        if not self._recorder.is_recording:
            return
        self._recording_timer.stop()
        self._recorder.stop()
        self._audio_ducker.restore()
        self.recording_changed.emit(False)
        self.status_changed.emit("Recording canceled.")

    def read_last_transcript_aloud(self) -> None:
        if not self._enabled:
            self.status_changed.emit("Dictation is disabled.")
            return
        text = self._last_transcript.strip()
        if not text:
            self.status_changed.emit("No dictated text available to read aloud yet.")
            return
        self.status_changed.emit("Reading dictated text aloud...")
        worker = threading.Thread(target=self._speak_text, args=(text,), daemon=True)
        worker.start()

    def shutdown(self) -> None:
        self._recording_timer.stop()
        if self._recorder.is_recording:
            self._recorder.stop()
            self._audio_ducker.restore()
        self._sound_feedback.close()

    def _on_recording_timeout(self) -> None:
        if self._recorder.is_recording:
            self.stop_recording_and_transcribe(maximum_reached=True)

    def _transcribe_and_insert(self, audio) -> None:  # noqa: ANN001
        try:
            self.status_changed.emit("Model ready check in progress...")
            initial_prompt_parts = [SMART_DICTATION_PROMPT]
            glossary_prompt = self._word_bank.glossary_prompt()
            if glossary_prompt:
                initial_prompt_parts.append(glossary_prompt)
            text = self._engine.transcribe(audio, initial_prompt=" ".join(initial_prompt_parts))
            text = self._word_bank.apply(text)
            text = self._cleanup_transcript(text)
            text = self._finalize_transcript(text)
            if not text:
                self._sound_feedback.play(FAILURE_SOUND)
                self.status_changed.emit("No speech detected.")
                return
            if not self._enabled:
                self.status_changed.emit("Dictation disabled. Transcript was not inserted.")
                return
            self._last_transcript = text
            self.status_changed.emit("Model ready. Transcript captured.")
            self.transcript_ready.emit(text)
            self.status_changed.emit("Inserting transcript...")
            inserted, msg = self._inserter.insert(text)
            self.status_changed.emit(msg)
            if not inserted:
                self.error_occurred.emit(msg)
            else:
                self._sound_feedback.play(SUCCESS_SOUND)
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
            self._sound_feedback.play(SUCCESS_SOUND)
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

    def _speak_text(self, text: str) -> None:
        cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$text = [Console]::In.ReadToEnd(); "
            "$synth.Speak($text);"
        )
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
                r"System32\WindowsPowerShell\v1.0\powershell.exe"
            )
            with self._speech_lock:
                subprocess.run(
                    [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", cmd],
                    input=text,
                    check=True,
                    capture_output=True,
                    text=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    env=os.environ.copy(),
                )
            self.status_changed.emit("Read aloud complete.")
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Read-aloud failed")
            self.error_occurred.emit(f"Read-aloud failed ({exc}).")

    @staticmethod
    def _cleanup_transcript(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned

        # Remove common filler words in standalone form.
        cleaned = re.sub(r"\b(uh+|um+|er+|ah+|mm+|hmm+)\b", "", cleaned, flags=re.IGNORECASE)

        # Remove short stutter patterns like "I-I", "th-th-the", "w-when".
        cleaned = re.sub(r"\b([A-Za-z])-\1+\b", r"\1", cleaned)
        cleaned = re.sub(r"\b([A-Za-z]{1,3})-\1+([A-Za-z]*)\b", r"\1\2", cleaned)

        # Collapse immediate repeated words: "the the" -> "the".
        cleaned = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", cleaned, flags=re.IGNORECASE)

        # Normalize punctuation artifacts from pauses/fillers.
        cleaned = re.sub(r"^[,.;:!?]+\s+", "", cleaned)
        cleaned = re.sub(r",\s*,+", ", ", cleaned)
        cleaned = re.sub(r"\s+,", ",", cleaned)
        cleaned = re.sub(r",\s*([.!?])", r"\1", cleaned)

        # Normalize spacing after removals.
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        cleaned = re.sub(r"^[,.;:!?]+\s*", "", cleaned)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = DictationController._apply_voice_commands(cleaned)
        cleaned = DictationController._format_spoken_numbered_list(cleaned)
        # Keep quotation marks tight inside the quote, while preserving boundary spacing.
        cleaned = re.sub(r'["“]\s+(\S)', r'"\1', cleaned)
        cleaned = re.sub(r'(\S)\s+["”]', r'\1"', cleaned)
        cleaned = re.sub(r'(\w)"([^"\n]+)"(\w)', r'\1 "\2" \3', cleaned)
        return cleaned

    @staticmethod
    def _apply_voice_commands(text: str) -> str:
        marker_start = "<<START_LIST>>"
        marker_end = "<<END_LIST>>"
        quote_open = r"(?:open quote|open quotation mark|quote)"
        quote_close = r"(?:close quote|close quotation mark|unquote|quote)"

        # First, fold paired spoken quote commands into a clean quoted span.
        # This absorbs common comma artifacts from pauses around the command words.
        pair_re = re.compile(
            rf"\b{quote_open}\b\s*[,;:]*\s*(.+?)\s*[,;:]*\s*\b{quote_close}\b",
            flags=re.IGNORECASE,
        )
        commandized = text
        for _ in range(8):
            commandized, replacements = pair_re.subn(r'"\1"', commandized)
            if replacements == 0:
                break

        # Fallback: handle unmatched spoken quote commands one by one.
        commandized = re.sub(r"\b(open quote|open quotation mark)\b", "\"", commandized, flags=re.IGNORECASE)
        commandized = re.sub(r"\b(close quote|close quotation mark)\b", "\"", commandized, flags=re.IGNORECASE)
        commandized = re.sub(r"\bquote\b", "\"", commandized, flags=re.IGNORECASE)
        commandized = re.sub(r"\bunquote\b", "\"", commandized, flags=re.IGNORECASE)
        commandized = re.sub(r'"\s*[,;:]+\s*', '"', commandized)
        commandized = re.sub(r'\s*[,;:]+\s*"', '"', commandized)

        # Common contraction miss: "does it" (ASR) for "doesn't" (intended).
        commandized = re.sub(
            r"\b(it|that|this|there|he|she)\s+does it\s+([a-z][a-z']*)\b",
            r"\1 doesn't \2",
            commandized,
            flags=re.IGNORECASE,
        )

        # Whisper commonly surrounds spoken commands with inferred punctuation,
        # for example "Start list. 1. ..." or ", new line,". Treat that
        # punctuation as part of the command rather than as dictated content.
        commandized = re.sub(
            r"[ \t]*[,;:]?[ \t]*\bstart\s+list\b[ \t]*[.,;:]?[ \t]*",
            f"\n{marker_start}\n",
            commandized,
            flags=re.IGNORECASE,
        )
        commandized = re.sub(
            r"[ \t]*[,;:]?[ \t]*\bend\s+list\b[ \t]*[.,;:]?[ \t]*",
            f"\n{marker_end}\n",
            commandized,
            flags=re.IGNORECASE,
        )
        commandized = re.sub(
            r"[ \t]*[,;:]?[ \t]*\bnew\s+line\b[ \t]*[,;:]?[ \t]*",
            "\n",
            commandized,
            flags=re.IGNORECASE,
        )
        # Avoid punctuation junk right before list start.
        commandized = re.sub(r"[,\-;]\s*\n" + re.escape(marker_start), "\n" + marker_start, commandized)

        list_mode = False
        rendered_lines: list[str] = []
        for raw_line in commandized.splitlines():
            line = raw_line.strip()
            if not line:
                if rendered_lines and rendered_lines[-1] != "":
                    rendered_lines.append("")
                continue
            if re.fullmatch(r"[,.;:!?-]+", line):
                continue
            if line == marker_start:
                list_mode = True
                continue
            if line == marker_end:
                list_mode = False
                continue

            if list_mode:
                # Convert inline numbered items into a real multi-line list,
                # whether Whisper emitted "one," or the punctuation form "1.".
                inline_numbered = DictationController._extract_inline_spoken_numbered_items(line)
                if inline_numbered:
                    for item_no, content in inline_numbered:
                        rendered_lines.append(f"{item_no}. {content}")
                    continue

                if re.match(r"^(\d+\.\s+|[-*]\s+)", line):
                    rendered_lines.append(line)
                else:

                    # If user did not explicitly say "new line" between items,
                    # split common spoken list separators into separate bullets.
                    parts = [
                        part.strip()
                        for part in re.split(r"\s*(?:;|,\s+and\s+|,\s+then\s+|,)\s*", line)
                        if part.strip()
                    ]
                    if len(parts) <= 1:
                        rendered_lines.append(f"- {line}")
                    else:
                        for part in parts:
                            rendered_lines.append(f"- {part}")
            else:
                rendered_lines.append(line)

        result = "\n".join(rendered_lines).strip()
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = re.sub(r"[,\-;]\s*\n(?=(?:- |\d+\. ))", "\n", result)
        result = DictationController._normalize_numbered_bullet_lists(result)
        return result

    @staticmethod
    def _extract_inline_spoken_numbered_items(line: str) -> list[tuple[int, str]]:
        token_re = re.compile(
            r"(?<!\w)([1-9]|one|two|three|four|five|six|seven|eight|nine)"
            r"(?:\b|(?=\D))[\s).,:;-]*",
            re.IGNORECASE,
        )
        matches = list(token_re.finditer(line))
        if len(matches) < 2:
            return []

        items: list[tuple[int, str]] = []
        for i, match in enumerate(matches):
            marker = match.group(1).lower()
            if marker.isdigit():
                item_no = int(marker)
            elif marker in SPOKEN_NUMBER_WORDS:
                item_no = SPOKEN_NUMBER_WORDS.index(marker) + 1
            else:
                continue
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            content = line[start:end].strip(" \t\r\n,;:-")
            if content:
                items.append((item_no, content))

        if len(items) < 2:
            return []

        expected = list(range(items[0][0], items[0][0] + len(items)))
        actual = [item_no for item_no, _ in items]
        if actual != expected:
            return []
        return items

    @staticmethod
    def _normalize_numbered_bullet_lists(text: str) -> str:
        marker_to_number = {
            **{word: idx + 1 for idx, word in enumerate(SPOKEN_NUMBER_WORDS)},
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
        }
        bullet_re = re.compile(
            r"^[-*]\s+(?:(\d+)|(" + "|".join(marker_to_number) + r"))[\s).,:;-]+(.+)$",
            re.IGNORECASE,
        )

        lines = text.splitlines()
        rendered: list[str] = []
        i = 0
        while i < len(lines):
            block: list[tuple[str, int, str]] = []
            j = i
            while j < len(lines):
                line = lines[j]
                match = bullet_re.match(line.strip())
                if not match:
                    break
                marker = match.group(1) or match.group(2)
                item_no = int(marker) if marker.isdigit() else marker_to_number[marker.lower()]
                content = match.group(3).strip(" \t\r\n,;:-")
                if not content:
                    break
                block.append((line, item_no, content))
                j += 1

            numbers = [item_no for _, item_no, _ in block]
            if len(block) >= 2 and numbers == list(range(numbers[0], numbers[0] + len(block))):
                rendered.extend(f"{item_no}. {content}" for _, item_no, content in block)
                i = j
                continue

            rendered.append(lines[i])
            i += 1

        return "\n".join(rendered)

    @staticmethod
    def _format_spoken_numbered_list(text: str) -> str:
        lowered = text.lower()
        marker_count = len(re.findall(r"\b(one|two|three|four|five|six|seven|eight|nine)\b\s*[,.:;-]", lowered))
        if marker_count < 2:
            return text

        # Break on spoken-number boundaries (including "first law, one, ...")
        # and rebuild as a numbered list.
        pattern = re.compile(
            r"(?:\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\s+law\b\s*,\s*)?"
            r"\b(one|two|three|four|five|six|seven|eight|nine)\b\s*[,.:;-]\s*",
            flags=re.IGNORECASE,
        )
        matches = list(pattern.finditer(text))
        if len(matches) < 2:
            return text

        items: list[tuple[int, str, int, int]] = []
        for i, match in enumerate(matches):
            word = match.group(1).lower()
            if word not in SPOKEN_NUMBER_WORDS:
                continue
            item_no = SPOKEN_NUMBER_WORDS.index(word) + 1
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip(" \t\r\n,;:-")
            if content:
                items.append((item_no, content, start, end))

        if len(items) < 2:
            return text

        # Keep only forward unique sequence (1,2,3...) and ignore stray repeats.
        deduped: list[tuple[int, str, int, int]] = []
        seen_numbers: set[int] = set()
        for item_no, content, start, end in items:
            if item_no in seen_numbers:
                continue
            seen_numbers.add(item_no)
            deduped.append((item_no, content, start, end))

        if len(deduped) < 2:
            return text

        expected = list(range(deduped[0][0], deduped[0][0] + len(deduped)))
        actual = [item_no for item_no, _, _, _ in deduped]
        if actual != expected:
            return text

        list_body = "\n".join(f"{item_no}. {content}" for item_no, content, _, _ in deduped)
        prefix = text[:matches[0].start()].strip(" \t\r\n,;:-")
        suffix = text[deduped[-1][3]:].strip(" \t\r\n,;:-")

        sections: list[str] = []
        if prefix:
            sections.append(prefix)
        sections.append(list_body)
        if suffix:
            sections.append(suffix)
        return "\n".join(sections)

    @staticmethod
    def _finalize_transcript(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        if "\n" in cleaned:
            return cleaned
        if re.search(r"[.!?][\"')\]]*$", cleaned):
            return cleaned
        # Only auto-periodize full sentence-like fragments; avoid forcing punctuation
        # on short commands, fragments, and terse dictation.
        word_count = len(re.findall(r"\b\w+\b", cleaned))
        if word_count >= 4 and (cleaned[-1].isalnum() or cleaned[-1] in ("\"", "'", ")", "]")):
            return f"{cleaned}."
        return cleaned
