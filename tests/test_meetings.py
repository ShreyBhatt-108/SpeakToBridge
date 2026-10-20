import tempfile, threading, unittest, wave, json
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from SpeakToBridge.meetings import (
    MeetingStore,
    ChunkWriter,
    MeetingSession,
    trim_overlap,
)
from SpeakToBridge.meeting_notes import validate_notes


class MeetingTests(unittest.TestCase):
    def test_long_meeting_chunking_is_bounded_and_passes_five_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            chunks = []
            writer = ChunkWriter(
                Path(tmp), "microphone", lambda *args: chunks.append(args)
            )
            for _ in range(370):
                writer.feed(np.zeros(16000, dtype=np.float32))
            writer.close()
            self.assertGreater(len(chunks), 12)
            self.assertGreater(chunks[-1][2] + chunks[-1][3], 300)
            self.assertTrue(all(duration <= 30 for _, _, _, duration in chunks))
            self.assertAlmostEqual(chunks[-1][2] + chunks[-1][3], 370, places=3)

    def test_exact_chunk_has_no_duplicate_overlap_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            chunks = []
            writer = ChunkWriter(
                Path(tmp), "microphone", lambda *args: chunks.append(args)
            )
            writer.feed(np.zeros(30 * 16000, dtype=np.float32))
            writer.close()
            self.assertEqual(len(chunks), 1)

    def test_notes_and_transcript_round_trip_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MeetingStore.create(Path(tmp), "Weekly meeting", "microphone")
            entry = dict(
                start_seconds=301,
                source="Microphone",
                text="Alice will send the report.",
                duration_seconds=12,
            )
            store.add_entry(entry)
            store.save_notes("My own notes")
            store.save_ai_notes("AI draft")
            metadata, entries, notes = store.load()
            self.assertEqual(metadata["title"], "Weekly meeting")
            self.assertEqual(entries, [entry])
            self.assertEqual(notes, "My own notes")
            self.assertIn(
                "[00:05:01] Microphone: Alice will send", store.export_markdown()
            )
            self.assertIn("My own notes", store.export_markdown())

    def test_incomplete_tail_does_not_destroy_previous_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MeetingStore.create(Path(tmp), "Meeting", "microphone")
            entry = dict(
                start_seconds=0,
                source="Microphone",
                text="Saved speech",
                duration_seconds=1,
            )
            store.add_entry(entry)
            with (store.folder / "transcript.jsonl").open("a") as handle:
                handle.write("{incomplete")
            self.assertEqual(store.load()[1], [entry])

    def test_failed_transcription_retains_audio_for_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MeetingStore.create(Path(tmp), "Meeting", "file")
            path = store.folder / "audio" / "recording-000001.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(b"\0\0" * 16000)
            engine = Mock()
            engine.transcribe.side_effect = RuntimeError("GPU unavailable")
            session = MeetingSession(engine, store, Mock(), Mock(), Mock())
            session._chunks.put((path, "recording", 0, 1))
            session._chunks.put(None)
            session._transcribe()
            self.assertTrue(path.exists())
            self.assertEqual(len(session._errors), 1)

    def test_overlap_trimming_keeps_normal_repeated_single_words(self):
        self.assertEqual(
            trim_overlap("We will send the report", "send the report tomorrow"),
            "tomorrow",
        )
        self.assertEqual(trim_overlap("yes", "yes"), "yes")

    def test_microphone_meeting_does_not_use_dictation_timeout(self):
        from SpeakToBridge.app import SpeakToBridgeRuntime

        runtime = Mock()
        runtime._meeting_session = object()
        SpeakToBridgeRuntime._on_hotkey_pressed(runtime)
        runtime._controller.stop_recording_and_transcribe.assert_not_called()
        runtime._controller.start_recording.assert_not_called()

    def test_imported_recording_uses_same_engine_and_generates_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "input.wav"
            with wave.open(str(audio), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(b"\0\0" * 32000)
            store = MeetingStore.create(root / "meetings", "Test", "file")
            engine = Mock()
            engine.transcribe.return_value = "Alice will send the report on Friday."
            notes = Mock(return_value="## Summary\nA report was discussed.")
            completed = Mock()
            session = MeetingSession(
                engine, store, Mock(), Mock(), completed, notes_generator=notes
            )
            session._run("file", audio)
            self.assertEqual(len(store.load()[1]), 1)
            self.assertEqual(store.load()[0]["notes_status"], "ready")
            self.assertEqual(
                (store.folder / "ai-notes.md").read_text(),
                "## Summary\nA report was discussed.",
            )
            self.assertEqual(list((store.folder / "audio").iterdir()), [])
            self.assertTrue(audio.exists())
            completed.assert_called_once()

    def test_model_and_runtime_changes_are_blocked_during_meeting(self):
        from SpeakToBridge.app import SpeakToBridgeRuntime

        runtime = Mock()
        runtime._meeting_session = object()
        SpeakToBridgeRuntime._on_model_changed(runtime, "large-v3")
        SpeakToBridgeRuntime._on_runtime_changed(runtime, "cpu")
        runtime._controller.set_model.assert_not_called()
        runtime._controller.set_runtime.assert_not_called()


class NotesValidationTests(unittest.TestCase):
    def test_actions_require_verbatim_evidence(self):
        transcript = "Alice will send the report on Friday."
        result = validate_notes(
            dict(
                summary=["A report was discussed"],
                decisions=[],
                action_items=[
                    dict(
                        task="Send report",
                        owner="Alice",
                        due="Friday",
                        evidence=transcript,
                    ),
                    dict(
                        task="Delete the database",
                        owner="Bob",
                        due="Monday",
                        evidence="Bob will delete the database on Monday.",
                    ),
                ],
            ),
            transcript,
        )
        self.assertEqual(len(result["action_items"]), 1)
        self.assertEqual(result["action_items"][0]["owner"], "Alice")

    def test_unknown_owner_and_deadline_are_not_invented(self):
        evidence = "We need to send the report."
        result = validate_notes(
            dict(
                summary=[],
                decisions=[],
                action_items=[
                    dict(
                        task="Send report",
                        owner="Alice",
                        due="Friday",
                        evidence=evidence,
                    )
                ],
            ),
            evidence,
        )
        self.assertEqual(result["action_items"][0]["owner"], "")
        self.assertEqual(result["action_items"][0]["due"], "")

    def test_bad_schema_rejected(self):
        with self.assertRaises(ValueError):
            validate_notes(
                dict(summary="not a list", decisions=[], action_items=[]), ""
            )

    def test_discussions_and_dates_are_not_turned_into_tasks(self):
        source = "We agreed to keep the launch date November 5. We discussed a redesign but no decision was made. The next meeting is Tuesday."
        result = validate_notes(
            dict(
                summary=[],
                decisions=[],
                action_items=[
                    dict(
                        task="Confirm launch date",
                        owner="Agreed",
                        due="November 5",
                        evidence="We agreed to keep the launch date November 5.",
                    ),
                    dict(
                        task="Discuss redesign",
                        owner="",
                        due="",
                        evidence="We discussed a redesign but no decision was made.",
                    ),
                    dict(
                        task="Schedule meeting",
                        owner="",
                        due="Tuesday",
                        evidence="The next meeting is Tuesday.",
                    ),
                ],
            ),
            source,
        )
        self.assertEqual(result["action_items"], [])
        self.assertEqual(
            result["decisions"], ["We agreed to keep the launch date November 5."]
        )

    def test_explicit_commitment_is_recovered_when_model_omits_it(self):
        source = "Alice will send the report by Friday. Charlie will send the final agenda on Saturday."
        result = validate_notes(dict(summary=[], decisions=[], action_items=[]), source)
        self.assertEqual(
            [a["owner"] for a in result["action_items"]], ["Alice", "Charlie"]
        )
        self.assertEqual(
            [a["due"] for a in result["action_items"]], ["Friday", "Saturday"]
        )

    def test_predictions_are_not_extracted_as_commitments(self):
        source = "It will rain tomorrow. The budget will increase. The launch will happen next month."
        result = validate_notes(dict(summary=[], decisions=[], action_items=[]), source)
        self.assertEqual(result["action_items"], [])
