# Severus AI

Windows-only local dictation app built with PySide6 + faster-whisper.

## v1 behavior

- System tray app with Settings window.
- Global activation hotkey is user-configurable in Settings (accessible modifier/key dropdowns for JAWS users).
- Toggle-to-talk:
  - press your configured activation hotkey to start recording
  - press the same activation hotkey again to stop, transcribe, and auto-insert
  - while recording, other system audio is ducked and restored automatically when recording stops
  - `dictation_begin.wav` plays on start
  - `reverse_dictation_end.mp3` plays when you end dictation
  - recording is capped at 300 seconds by default so an accidentally abandoned recording cannot consume memory indefinitely
  - the recording limit can be changed from 30 to 3600 seconds under **Show More Settings > Recording Limit**
- Accessible feedback:
  - status changes emit polite Qt accessibility announcements for screen readers
  - Runtime Status is a read-only, wrapped text area that exposes its current value to JAWS
  - press `Alt+S` in Settings to focus Runtime Status, then use normal text-reading commands
  - distinct short cues identify processing, successful insertion, and failure
- Read aloud:
  - press `Ctrl+F8` to have the Windows system voice read the last dictated transcript
- Word Bank:
  - edit the Word Bank box in Settings
  - use one mapping per line: `heard_word = CorrectWord`
  - save to apply corrections to future transcripts (useful for names/proper nouns)
- Model Storage:
  - cached models are shown in Settings with size and readiness status
  - old cached models can be deleted from Settings to free disk space
- Local-only transcription after model download.
- Pause-preserving VAD is enabled by default:
  - it trims dead air after roughly `1000 ms` of silence and keeps padding around speech
  - short and natural pauses are preserved so Whisper can still infer commas and periods from cadence
- Default model is `small`.
- English-only dictation.
- Default microphone only.
- Clipboard safety: existing clipboard text is backed up before paste and restored right after insertion.
- Settings follow the native Windows palette and font, including dark and high-contrast themes.
- Destructive and unsaved-change safeguards:
  - cached models require confirmation before deletion
  - Word Bank edits are marked unsaved and prompt to save before closing or quitting
  - uninstalling preserves configuration, the Word Bank, statistics, logs, and downloaded models in `%LOCALAPPDATA%\SeverusAI`
- Dictation Stats includes an **Overall total** field showing words and clips across every session. It is stored in `%LOCALAPPDATA%\SeverusAI\stats.json` and is a single keyboard-accessible JAWS stop.

## Release notes (v1.1.2)

This update focuses on making everyday dictation use more reliable and less confusing.

- The extra settings panel now opens in a more natural place, directly after the `Show More Settings` controls area, instead of appearing unexpectedly in the middle of the page.
- Hotkey handling is more robust for Windows key combinations:
  - better handling of generic and left/right modifier key events
  - improved support for combos like `Ctrl+Win`
  - more reliable key-release handling to prevent stuck recording states
- Dictation on/off behavior is stricter:
  - when dictation is off, dictation and read-aloud shortcuts stay off
  - prevents late transcript insertion after dictation has been disabled
- Exit behavior is clearer:
  - `Alt+F4` on the settings window minimizes Severus AI to tray
  - the settings window now includes a dedicated `Quit Severus AI` button that fully shuts down the program
- Word Bank behavior is smarter:
  - keeps exact replacements
  - adds local fuzzy matching for near-miss words/phrases
  - uses dictionary context as a transcription prompt to improve recognition for names and special terms
- Transcript cleanup is smarter by default:
  - removes common filler words and stutter artifacts
  - collapses accidental immediate word repeats
  - reduces punctuation artifacts from pauses (such as extra commas)
- Spoken numbered lists are now formatted into real numbered output when clear markers are detected:
  - examples: `one, ... two, ... three, ...` and `first law, one, ... two, ...`
  - intro text before the list and trailing text after the list are preserved

## Release notes (v1.2.0)

- Added a persistent overall word and clip count across application restarts.
- Reworked Runtime Status as a wrapped, keyboard-focusable text control for more reliable JAWS reading; `Alt+S` focuses it directly.
- Added polite screen-reader status announcements and distinct processing, success, and failure sounds.
- Added a configurable recording limit with an independent in-memory audio cap.
- Adopted native Windows fonts, colors, high contrast, dark mode, and focus behavior.
- Added confirmation before cached-model deletion and unsaved Word Bank warnings.
- Preserved settings, models, statistics, logs, and the Word Bank during uninstall.
- Moved read-aloud transcript transfer from the process command line to standard input.
- Added validated settings, pinned and hash-locked dependencies, vulnerability-audited build inputs, and optional Authenticode signing support.

## Run from source

```powershell
pip install --require-hashes -r requirements.lock.txt
python -m SeverusAI
```

## Build portable EXE + Windows installer

```powershell
.\build.ps1
```

Outputs:
- `dist\SeverusAI\SeverusAI.exe` (portable app folder build)
- `dist\SeverusAI-Setup.exe` (Windows installer, when Inno Setup 6 is installed)

If Inno Setup is not installed, the script still builds the EXE and tells you installer generation was skipped.

Builds install from hashed runtime and build lock files. To Authenticode-sign both the application executable and installer, install the Windows SDK and set `SEVERUS_SIGNING_CERT_SHA1` to the SHA-1 thumbprint of an available code-signing certificate before running `build.ps1`. Without that certificate, local builds remain unsigned.

## Notes

- Faster Whisper model files are downloaded on first use and cached in local app data.
- Runtime is offline after model download unless you choose a new model that is not yet cached.
- The app runs as a single instance to prevent duplicate global listeners and duplicate paste behavior.
- Read-aloud text is sent to Windows PowerShell through standard input rather than included in the process command line.
- Uninstall leaves `%LOCALAPPDATA%\SeverusAI` intact. Remove that folder manually only when you intentionally want to erase settings, models, the Word Bank, logs, and statistics.
- `SeverusAI/constants.py` is the application version source. Packaging reads that value rather than maintaining a separate installer version.
- Third-party feedback-sound provenance is recorded in `THIRD_PARTY_ASSETS.md`.

## Developer notes

- `CODE_WALKTHROUGH_LOCAL.md` is intentionally local-only learning documentation.
- It is ignored by Git and is not part of GitHub source history.

## Credits

Created by Shrey Bhatt.

Developed with assistance from OpenAI Codex.

Core stack: Python, PySide6, OpenAI Whisper (faster-whisper runtime).
