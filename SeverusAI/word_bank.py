from __future__ import annotations

import logging
import re
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

        return self._pattern.sub(repl, transcript)

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
