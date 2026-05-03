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
- Default model is `small`.
- English-only dictation.
- Default microphone only.
- Clipboard safety: existing clipboard text is backed up before paste and restored right after insertion.

## Release notes (v1.1.1)

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

## Run from source

```powershell
pip install -r requirements.txt
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

## Notes

- Faster Whisper model files are downloaded on first use and cached in local app data.
- Runtime is offline after model download unless you choose a new model that is not yet cached.
- The app runs as a single instance to prevent duplicate global listeners and duplicate paste behavior.

## Developer notes

- `CODE_WALKTHROUGH_LOCAL.md` is intentionally local-only learning documentation.
- It is ignored by Git and is not part of GitHub source history.

## Credits

Created by Shrey Bhatt.

Developed with assistance from OpenAI Codex.

Core stack: Python, PySide6, OpenAI Whisper (faster-whisper runtime).
