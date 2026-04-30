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
- `dist\SeverusAI.exe` (portable app)
- `dist\SeverusAI-Setup.exe` (Windows installer, when Inno Setup 6 is installed)

If Inno Setup is not installed, the script still builds the EXE and tells you installer generation was skipped.

## Notes

- Faster Whisper model files are downloaded on first use and cached in local app data.
- Runtime is offline after model download unless you choose a new model that is not yet cached.
- Developer learning guide: see `CODE_WALKTHROUGH.md`.

## Credits

Created by Shrey Bhatt.

Developed with assistance from OpenAI Codex.

Core stack: Python, PySide6, OpenAI Whisper (faster-whisper runtime).
