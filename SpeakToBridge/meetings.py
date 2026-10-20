"""Local meeting storage and chunked capture/transcription, independent of dictation."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import queue
import re
import threading
import time
import uuid
import wave
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16000
CHUNK_SECONDS = 30
OVERLAP_SECONDS = 1


def timestamp(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}"


def trim_overlap(previous, text):
    old = previous.split()
    new = text.split()
    clean = lambda word: re.sub(r"[^\w]", "", word).casefold()
    for count in range(min(24, len(old), len(new)), 2, -1):
        if [clean(w) for w in old[-count:]] == [clean(w) for w in new[:count]]:
            return " ".join(new[count:])
    return text


class MeetingStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self._lock = threading.RLock()

    @classmethod
    def create(cls, root, title, source, keep_audio=False):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        folder = root / (
            dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        )
        folder.mkdir()
        (folder / "audio").mkdir()
        store = cls(folder)
        store.update(
            title=str(title).strip()[:200] or "Meeting",
            source=source,
            created_at=dt.datetime.now().astimezone().isoformat(),
            status="starting",
            keep_audio=bool(keep_audio),
        )
        store.save_notes("")
        return store

    def update(self, **values):
        with self._lock:
            path = self.folder / "meeting.json"
            current = (
                json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            )
            current.update(values)
            temporary = self.folder / "meeting.json.tmp"
            temporary.write_text(
                json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            temporary.replace(path)

    def add_entry(self, entry):
        with self._lock:
            with (self.folder / "transcript.jsonl").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def save_notes(self, text):
        with self._lock:
            temporary = self.folder / "notes.md.tmp"
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(self.folder / "notes.md")

    def load(self):
        with self._lock:
            metadata = json.loads(
                (self.folder / "meeting.json").read_text(encoding="utf-8")
            )
            entries = []
            path = self.folder / "transcript.jsonl"
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        LOGGER.warning(
                            "Ignoring incomplete final meeting transcript line"
                        )
            notes_path = self.folder / "notes.md"
            notes = (
                notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
            )
            return metadata, entries, notes

    def save_ai_notes(self, text):
        with self._lock:
            temporary = self.folder / "ai-notes.md.tmp"
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(self.folder / "ai-notes.md")

    def export_markdown(self):
        metadata, entries, notes = self.load()
        lines = [
            "# " + metadata["title"],
            "",
            metadata["created_at"],
            "",
            notes,
            "",
            "## Transcript",
            "",
        ]
        lines += [
            f"[{timestamp(entry['start_seconds'])}] {entry['source']}: {entry['text']}"
            for entry in entries
        ]
        return "\n".join(lines) + "\n"


class ChunkWriter:
    def __init__(self, folder, source, on_chunk, chunk_seconds=CHUNK_SECONDS):
        self.folder = Path(folder)
        self.source = source
        self.on_chunk = on_chunk
        self.chunk_samples = int(chunk_seconds * SAMPLE_RATE)
        self._parts = []
        self._size = 0
        self._total = 0
        self._index = 0
        self._start = 0

    def feed(self, audio):
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        position = 0
        while position < len(audio):
            count = min(self.chunk_samples - self._size, len(audio) - position)
            self._parts.append(audio[position : position + count].copy())
            self._size += count
            self._total += count
            position += count
            if self._size == self.chunk_samples:
                self._flush(overlap=True)

    def _flush(self, overlap):
        if not self._size:
            return
        audio = np.concatenate(self._parts)
        self._index += 1
        path = self.folder / f"{self.source}-{self._index:06d}.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
        start = self._start / SAMPLE_RATE
        self.on_chunk(path, self.source, start, len(audio) / SAMPLE_RATE)
        tail = (
            audio[-SAMPLE_RATE * OVERLAP_SECONDS :].copy()
            if overlap
            else np.array([], dtype=np.float32)
        )
        self._parts = [tail] if len(tail) else []
        self._size = len(tail)
        # Overlap is copied context, not additional captured meeting duration.
        self._start = self._total - len(tail)
        self._total = self._start + len(tail)

    def close(self):
        # Do not write a redundant overlap-only tail after an exact full chunk.
        if self._index and self._size <= SAMPLE_RATE * OVERLAP_SECONDS:
            self._parts = []
            self._size = 0
            return
        self._flush(overlap=False)


class MeetingSession:
    def __init__(
        self,
        engine,
        store,
        on_entry,
        on_status,
        on_finished,
        transform=None,
        notes_generator=None,
        model_cache_dir=None,
    ):
        self.engine = engine
        self.store = store
        self.on_entry = on_entry
        self.on_status = on_status
        self.on_finished = on_finished
        self.transform = transform or (lambda text: text)
        self._stopped = threading.Event()
        self._chunks = queue.Queue()
        self._thread = None
        self._errors = []
        self._previous = {}
        self._error_lock = threading.Lock()
        self._capture_started = threading.Event()
        self._cancelled = threading.Event()
        self._notes_generator = notes_generator
        self._model_cache_dir = model_cache_dir

    def start(self, source, audio_file=None):
        if source not in ("microphone", "file", "notes"):
            raise ValueError("Invalid meeting source")
        self._thread = threading.Thread(
            target=self._run,
            args=(source, audio_file),
            daemon=True,
            name="speak-to-bridge-meeting",
        )
        self._thread.start()

    def stop(self):
        self._stopped.set()

    def cancel_for_shutdown(self):
        self._cancelled.set()
        self._stopped.set()

    def _error(self, text):
        with self._error_lock:
            self._errors.append(str(text))
        LOGGER.error("Meeting error: %s", text)
        self.on_status(str(text))

    def _enqueue(self, path, source, start, duration):
        self._chunks.put((path, source, start, duration))

    def _run(self, source, audio_file):
        consumer = threading.Thread(
            target=self._transcribe,
            daemon=True,
            name="speak-to-bridge-meeting-transcription",
        )
        consumer.start()
        captures = []
        try:
            self.store.update(
                status="recording" if source != "file" else "transcribing"
            )
            if source == "notes":
                pass
            elif source == "file":
                self._import_file(Path(audio_file))
            else:
                names = ("microphone",)
                for name in names:
                    thread = threading.Thread(
                        target=self._capture,
                        args=(name,),
                        daemon=True,
                        name="speak-to-bridge-meeting-" + name,
                    )
                    captures.append(thread)
                    thread.start()
                self.on_status("Meeting recording. Use Stop Meeting when finished.")
                while not self._stopped.wait(0.2):
                    if not any(t.is_alive() for t in captures):
                        break
        except Exception as exc:
            LOGGER.exception("Meeting setup/import failed")
            self._error(f"Meeting could not continue: {exc}")
        finally:
            self._stopped.set()
            for thread in captures:
                thread.join(timeout=5)
            if any(t.is_alive() for t in captures):
                self._error(
                    "An audio device did not stop promptly. Restart the app before recording again."
                )
            self.store.update(status="finishing")
            self.on_status("Finishing meeting transcript...")
            self._chunks.put(None)
            consumer.join()
            if not self._cancelled.is_set():
                try:
                    from .meeting_notes import generate_meeting_notes

                    self.store.update(
                        status="generating_notes", notes_status="generating"
                    )
                    generator = self._notes_generator or generate_meeting_notes
                    notes = generator(
                        self.store,
                        self._model_cache_dir,
                        self.on_status,
                        self._cancelled,
                    )
                    self.store.save_ai_notes(notes)
                    self.store.update(notes_status="ready")
                except Exception as exc:
                    from .meeting_notes import NotesCancelled

                    if isinstance(exc, NotesCancelled):
                        self.store.update(notes_status="cancelled")
                    else:
                        self.store.update(notes_status="failed")
                        self._error(
                            f"Transcript saved; AI notes could not be generated: {exc}"
                        )
            else:
                self.store.update(notes_status="cancelled")
            final = "completed" if not self._errors else "needs_attention"
            self.store.update(status=final, errors=self._errors)
            self.on_finished(str(self.store.folder), list(self._errors))

    def _capture(self, source):
        import sounddevice as sd

        frames = queue.Queue(maxsize=200)
        overflow = threading.Event()
        writer = ChunkWriter(self.store.folder / "audio", source, self._enqueue)

        def receive(indata, count, timing, status):
            if self._stopped.is_set():
                return
            if status:
                LOGGER.warning("Meeting microphone status: %s", status)
            try:
                frames.put_nowait(indata.copy())
            except queue.Full:
                overflow.set()

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=1600,
                callback=receive,
            ):
                self._capture_started.set()
                while not self._stopped.is_set() or not frames.empty():
                    if overflow.is_set():
                        raise RuntimeError(
                            "Audio storage could not keep up; captured chunks have been retained"
                        )
                    try:
                        audio = frames.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    writer.feed(audio.reshape(-1))
        except Exception as exc:
            LOGGER.exception("Meeting microphone capture failed")
            self._error(f"Microphone capture failed: {exc}")
            self._stopped.set()
        finally:
            writer.close()

    def _import_file(self, path):
        import av

        writer = ChunkWriter(self.store.folder / "audio", "recording", self._enqueue)
        self.on_status("Transcribing selected recording...")
        try:
            with av.open(str(path)) as container:
                resampler = av.AudioResampler(
                    format="flt", layout="mono", rate=SAMPLE_RATE
                )
                for frame in container.decode(audio=0):
                    if self._stopped.is_set():
                        break
                    for converted in resampler.resample(frame):
                        writer.feed(converted.to_ndarray().reshape(-1))
                for converted in resampler.resample(None):
                    writer.feed(converted.to_ndarray().reshape(-1))
        finally:
            writer.close()

    def _transcribe(self):
        metadata, _, _ = self.store.load()
        while True:
            item = self._chunks.get()
            if item is None:
                return
            path, source, start, duration = item
            if self._cancelled.is_set():
                self.store.update(pending_audio=True)
                continue
            try:
                with wave.open(str(path), "rb") as handle:
                    audio = (
                        np.frombuffer(
                            handle.readframes(handle.getnframes()), dtype="<i2"
                        ).astype(np.float32)
                        / 32768
                    )
                text = self.transform(self.engine.transcribe(audio)).strip()
                if text:
                    text = trim_overlap(self._previous.get(source, ""), text)
                    if text:
                        entry = dict(
                            source={
                                "microphone": "Microphone",
                                "computer": "Computer audio",
                                "recording": "Recording",
                            }[source],
                            start_seconds=start,
                            duration_seconds=duration,
                            text=text,
                        )
                        self.store.add_entry(entry)
                        self.on_entry(entry)
                        self._previous[source] = text
                if not metadata["keep_audio"]:
                    # Only delete this session's successfully processed generated chunks.
                    if (
                        path.parent.resolve() != (self.store.folder / "audio").resolve()
                        or path.is_symlink()
                    ):
                        raise ValueError("Unexpected meeting chunk path")
                    path.unlink()
            except Exception as exc:
                LOGGER.exception("Meeting chunk failed; audio retained")
                self._error(
                    f"Could not transcribe {timestamp(start)}. Audio retained for recovery: {exc}"
                )
