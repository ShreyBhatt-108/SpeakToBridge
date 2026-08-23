from __future__ import annotations

import unittest

from SpeakToBridge.controller import DictationController


def process(text: str) -> str:
    cleaned = DictationController._cleanup_transcript(text)
    return DictationController._finalize_transcript(cleaned)


class SpokenCommandTests(unittest.TestCase):
    def test_numbered_list_with_inferred_periods_and_repeated_new_lines(self) -> None:
        raw = (
            "Start list. 1. Check the microphone. 2. Check OBS settings. "
            "3. Start recording. End list. These are the steps that one must follow, "
            "new line, new line, new line, to be successful in this industry."
        )

        self.assertEqual(
            process(raw),
            "1. Check the microphone.\n"
            "2. Check OBS settings.\n"
            "3. Start recording.\n"
            "These are the steps that one must follow\n\n"
            "to be successful in this industry.",
        )

    def test_spoken_numbered_list_with_command_commas(self) -> None:
        raw = (
            "Start list, one, Check the microphone. two, Check OBS settings. "
            "three, Start recording. end list, These steps work."
        )

        self.assertEqual(
            process(raw),
            "1. Check the microphone.\n"
            "2. Check OBS settings.\n"
            "3. Start recording.\n"
            "These steps work.",
        )

    def test_punctuation_only_lines_are_discarded(self) -> None:
        self.assertEqual(process("First, new line, new line, second."), "First\n\nsecond.")


if __name__ == "__main__":
    unittest.main()
