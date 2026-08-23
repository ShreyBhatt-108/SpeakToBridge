from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path


LOGGER = logging.getLogger(__name__)

DEFAULT_WORD_BANK_TEXT = (
    "# Word Bank\n"
    "# One mapping per line: what_you_hear = correct_spelling\n"
    "# Example:\n"
    "# jawn = John\n"
    "# sara = Sarah\n"
)


class WordBank:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._raw_text = self._load_or_create()
        self._mapping = self._parse_mapping(self._raw_text)
        self._pattern = self._build_pattern(self._mapping)
        self._max_phrase_words = self._count_max_phrase_words(self._mapping)

    def get_raw_text(self) -> str:
        return self._raw_text

    def get_entries(self) -> list[tuple[str, str]]:
        return sorted(self._mapping.items(), key=lambda item: item[0])

    def save_raw_text(self, text: str) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = text.replace("\r\n", "\n")
        self._file_path.write_text(normalized, encoding="utf-8")
        self._raw_text = normalized
        self._mapping = self._parse_mapping(normalized)
        self._pattern = self._build_pattern(self._mapping)
        self._max_phrase_words = self._count_max_phrase_words(self._mapping)

    def save_entries(self, entries: list[tuple[str, str]]) -> None:
        lines = ["# Word Bank", "# Format: heard = Correct"]
        for wrong, right in entries:
            left = str(wrong).strip()
            correct = str(right).strip()
            if left and correct:
                lines.append(f"{left} = {correct}")
        self.save_raw_text("\n".join(lines) + "\n")

    def apply(self, transcript: str) -> str:
        if not transcript or not self._mapping or self._pattern is None:
            return transcript

        def repl(match: re.Match[str]) -> str:
            source = match.group(0)
            replacement = self._mapping.get(source.lower(), source)
            if source.isupper():
                return replacement.upper()
            if source.istitle():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        exact_text = self._pattern.sub(repl, transcript)
        return self._apply_retrieval_corrections(exact_text)

    def glossary_prompt(self) -> str:
        if not self._mapping:
            return ""
        pairs = [f"{heard} means {correct}" for heard, correct in self.get_entries()]
        return "Use these user dictionary corrections for names and special words: " + "; ".join(pairs) + "."

    def _load_or_create(self) -> str:
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(DEFAULT_WORD_BANK_TEXT, encoding="utf-8")
            return DEFAULT_WORD_BANK_TEXT
        try:
            return self._file_path.read_text(encoding="utf-8")
        except Exception:
            LOGGER.exception("Failed to read word bank file: %s", self._file_path)
            return DEFAULT_WORD_BANK_TEXT

    @staticmethod
    def _parse_mapping(raw_text: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            wrong, right = line.split("=", 1)
            wrong_clean = wrong.strip().lower()
            right_clean = right.strip()
            if wrong_clean and right_clean:
                mapping[wrong_clean] = right_clean
        return mapping

    @staticmethod
    def _build_pattern(mapping: dict[str, str]) -> re.Pattern[str] | None:
        if not mapping:
            return None
        terms = sorted(mapping.keys(), key=len, reverse=True)
        escaped = [re.escape(term) for term in terms]
        return re.compile(r"\b(" + "|".join(escaped) + r")\b", flags=re.IGNORECASE)

    @staticmethod
    def _count_max_phrase_words(mapping: dict[str, str]) -> int:
        max_words = 1
        for heard, correct in mapping.items():
            for phrase in (heard, correct):
                words = re.findall(r"\w+", phrase)
                if words:
                    max_words = max(max_words, len(words))
        return min(max_words, 6)

    def _apply_retrieval_corrections(self, transcript: str) -> str:
        word_matches = list(re.finditer(r"\b[\w']+\b", transcript))
        if not word_matches:
            return transcript

        replacements: list[tuple[int, int, str]] = []
        used_until = -1
        i = 0
        while i < len(word_matches):
            if word_matches[i].start() < used_until:
                i += 1
                continue

            best: tuple[float, int, int, str] | None = None
            max_end = min(len(word_matches), i + self._max_phrase_words)
            for end_index in range(max_end, i, -1):
                phrase_start = word_matches[i].start()
                phrase_end = word_matches[end_index - 1].end()
                phrase = transcript[phrase_start:phrase_end]
                candidate = self._retrieve_correction(phrase)
                if candidate is None:
                    continue
                score, replacement = candidate
                if best is None or score > best[0]:
                    best = (score, phrase_start, phrase_end, replacement)
                break

            if best is not None:
                _, start, end, replacement = best
                replacements.append((start, end, replacement))
                used_until = end
            i += 1

        if not replacements:
            return transcript

        output: list[str] = []
        last = 0
        for start, end, replacement in replacements:
            output.append(transcript[last:start])
            output.append(replacement)
            last = end
        output.append(transcript[last:])
        return "".join(output)

    def _retrieve_correction(self, phrase: str) -> tuple[float, str] | None:
        normalized_phrase = self._normalize_phrase(phrase)
        if len(normalized_phrase) < 3:
            return None

        best_score = 0.0
        best_replacement = ""
        for heard, correct in self._mapping.items():
            normalized_correct = self._normalize_phrase(correct)
            if normalized_phrase == normalized_correct and phrase != correct:
                return 1.0, self._match_case(phrase, correct)
            for query in (heard, correct):
                normalized_query = self._normalize_phrase(query)
                if not normalized_query or normalized_query == normalized_phrase:
                    continue
                score = SequenceMatcher(None, normalized_phrase, normalized_query).ratio()
                if score > best_score:
                    best_score = score
                    best_replacement = self._match_case(phrase, correct)

        if not best_replacement:
            return None
        if self._passes_retrieval_threshold(normalized_phrase, best_replacement, best_score):
            return best_score, best_replacement
        return None

    @staticmethod
    def _normalize_phrase(value: str) -> str:
        return " ".join(re.findall(r"\w+", value.lower()))

    @staticmethod
    def _passes_retrieval_threshold(phrase: str, replacement: str, score: float) -> bool:
        if phrase == WordBank._normalize_phrase(replacement):
            return False
        word_count = len(phrase.split())
        if word_count > 1:
            return score >= 0.86
        if len(phrase) <= 3:
            return score >= 0.93 and phrase[:1] == WordBank._normalize_phrase(replacement)[:1]
        return score >= 0.88

    @staticmethod
    def _match_case(source: str, replacement: str) -> str:
        if source.isupper():
            return replacement.upper()
        if source.istitle():
            return replacement[:1].upper() + replacement[1:]
        return replacement
