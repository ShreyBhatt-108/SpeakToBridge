# SeverusAI Code Walkthrough

This guide explains how the app is built, how data flows through it, and where to change behavior safely.

## 1) High-level architecture

The app is split into focused modules:

- UI and app wiring:
  - `SeverusAI/app.py`
  - `SeverusAI/ui.py`
- Core dictation flow:
  - `SeverusAI/controller.py`
  - `SeverusAI/audio.py`
  - `SeverusAI/whisper_engine.py`
  - `SeverusAI/insertion.py`
- Hotkeys and accessibility:
  - `SeverusAI/hotkey.py`
- Custom user corrections:
  - `SeverusAI/word_bank.py`
- Model cache management:
  - `SeverusAI/model_storage.py`
- Settings, paths, and constants:
  - `SeverusAI/config.py`
  - `SeverusAI/paths.py`
  - `SeverusAI/constants.py`
- Logging and entrypoint:
  - `SeverusAI/logging_utils.py`
  - `SeverusAI/__main__.py`

## 2) Runtime flow (what happens when app starts)

1. `python -m SeverusAI` runs `SeverusAI/__main__.py`, which calls `run()` in `app.py`.
2. `app.py` creates `SeverusAIRuntime`.
3. Runtime loads config (`config.py`) and word bank (`word_bank.py`).
4. Runtime creates UI (`ui.py`), controller (`controller.py`), and hotkey listener (`hotkey.py`).
5. User presses configured hotkey:
   - `controller.start_recording()`
   - `audio.py` captures mic audio.
6. User presses hotkey again:
   - `controller.stop_recording_and_transcribe()`
   - `whisper_engine.py` transcribes
   - `word_bank.py` rewrites known mistakes
   - `insertion.py` pastes and restores clipboard.

## 3) File-by-file guide

## `SeverusAI/app.py`
- Main coordinator.
- Connects UI signals to controller methods.
- Handles status updates and tray notifications.
- Handles model apply, hotkey apply, word bank save, and model cache actions.

Safe edits:
- Tray text, status wording, app-level guardrails.
- Add new settings signals and handlers.

## `SeverusAI/ui.py`
- Settings window widgets and accessibility labels.
- Emits signals for model changes, hotkey changes, word bank save, and model cache actions.
- Includes:
  - Hotkey controls
  - Model selector
  - Word bank editor form
  - Model storage list with delete
  - Status + stats.

Safe edits:
- Layout, labels, styling, control order.
- Accessibility names/descriptions for JAWS.

## `SeverusAI/controller.py`
- Dictation state machine.
- Owns recorder, whisper engine, text insertion, word bank use.
- Manages recording/transcribe lifecycle and busy/preloading states.

Safe edits:
- New runtime rules (for example retries, timeouts, queueing).
- New post-processing after transcript.

## `SeverusAI/audio.py`
- Microphone recording abstraction.

Safe edits:
- Sample rate logic, buffer behavior, device selection support.

## `SeverusAI/whisper_engine.py`
- Lazy model loading and switching.
- Uses faster-whisper with cache folder.
- Handles local-cache vs download status messages.

Safe edits:
- Device/compute mode decisions.
- Model loading policies, retries, and timeout handling.

## `SeverusAI/insertion.py`
- Clipboard-safe paste insertion.
- Current behavior:
  1. read existing clipboard text
  2. copy transcript
  3. paste with `Ctrl+V`
  4. restore previous clipboard text
  5. retries on clipboard read/write.

Safe edits:
- Timing/retries, alternate insertion methods.

## `SeverusAI/hotkey.py`
- Global hotkey listener (pynput).
- Configurable activation hotkey parser and matcher.
- Fixed `Ctrl+F8` read-aloud trigger.

Safe edits:
- Add extra shortcuts, richer parser rules.

## `SeverusAI/word_bank.py`
- Persistent user correction map.
- Supports loading/saving and applying replacements case-insensitively.

Safe edits:
- Phrase-level replacement logic, import/export formats.

## `SeverusAI/model_storage.py`
- Lists cached model folders.
- Computes folder sizes.
- Marks cache as `ready` if `model.bin` exists.
- Deletes selected cached model.

Safe edits:
- Better readiness checks, more metadata in UI.

## `SeverusAI/audio_ducking.py`
- Best-effort system volume ducking while recording.
- Gracefully disables itself if endpoint API not supported.

Safe edits:
- Alternative ducking strategies, per-app session ducking.

## `SeverusAI/config.py`
- JSON config load/save.
- `AppConfig` dataclass fields:
  - model name
  - hotkey
  - language/runtime/etc placeholders.

Safe edits:
- Add new persisted settings with defaults.

## `SeverusAI/paths.py`
- Centralized app-data paths under `%LOCALAPPDATA%\SeverusAI`.

Safe edits:
- New storage file locations.

## `SeverusAI/constants.py`
- static choices and defaults.

Safe edits:
- add model choices, default values.

## `SeverusAI/logging_utils.py`
- Rotating file logger + console logger.
- Logs stored in `%LOCALAPPDATA%\SeverusAI\logs\app.log`.

## 4) Current user data locations

- Config: `%LOCALAPPDATA%\SeverusAI\config.json`
- Model cache: `%LOCALAPPDATA%\SeverusAI\models\`
- Word bank: `%LOCALAPPDATA%\SeverusAI\word_bank.txt`
- Logs: `%LOCALAPPDATA%\SeverusAI\logs\app.log`

## 5) Practical coding workflow for this project

1. Edit one module at a time.
2. Run syntax check:
   - `python -m py_compile SeverusAI\\*.py` (or per file)
3. Launch app:
   - `python -m SeverusAI`
4. If runtime issue:
   - inspect `%LOCALAPPDATA%\\SeverusAI\\logs\\app.log`
5. Fix, re-run, repeat.

## 6) Known reliability considerations

- First-time model download depends on Hugging Face network availability.
- If download is interrupted, cache can be incomplete; `Model Storage` now helps cleanup.
- Audio ducking may be unavailable on some systems and will auto-disable gracefully.

## 7) How to extend next (recommended)

- Add retry/backoff around model download failures.
- Add explicit “Model not ready yet” state in UI before allowing recording.
- Add model download progress indicator for user confidence.
- Add optional model import from local file for fully offline setup.
