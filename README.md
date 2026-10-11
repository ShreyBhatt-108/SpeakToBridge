# Speak to Bridge

> **Speak. Bridge. Done.**

An accessible, privacy-conscious dictation application for Windows.

Speak to Bridge records speech on demand, transcribes it locally with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), and inserts the
result into the application you are using. It was designed around keyboard and
screen-reader access rather than treating accessibility as a later addition.

> **Project status:** Speak to Bridge is a personal, independently developed project.
> It currently supports Windows, English dictation, and the default microphone.

## Why this project exists

Many dictation tools depend on cloud transcription or make their most important
controls difficult to use with a screen reader. Speak to Bridge explores a different
approach: local transcription, predictable keyboard control, persistent user
preferences, and status feedback that works with JAWS.

## Highlights

AMD Strix Halo / Radeon 8060S GPU processing is available through the optional
ROCm backend. See [AMD setup and verification](AMD_SETUP.md). CPU processing
continues to work without the optional runtime.

- **Local transcription:** recorded audio stays on the computer after the
  selected Whisper model has been downloaded.
- **Keyboard-first operation:** a configurable global hotkey starts and stops
  dictation without moving focus away from the current application.
- **Screen-reader feedback:** Runtime Status is keyboard-focusable, exposes its
  current value to accessibility tools, and emits polite status announcements.
- **Optional sound cues:** short, distinct sounds identify recording,
  processing, success, and failure without requiring the user to inspect the
  window. Users can turn every cue off from Settings.
- **Automatic insertion:** completed text is pasted into the active application
  while preserving the user's existing clipboard text.
- **Personal Word Bank:** custom corrections improve names, terminology, and
  phrases that Whisper commonly mishears.
- **Lifetime statistics:** the application tracks the total number of dictated
  words and completed clips across sessions.
- **Safety limits:** recording duration is configurable and independently capped
  in memory to prevent an abandoned recording from growing indefinitely.
- **Windows-aware presentation:** the interface follows native fonts, colours,
  dark mode, high-contrast settings, and focus behaviour.

## Accessibility

Accessibility features include:

- JAWS-readable labels, values, status updates, and keyboard focus order;
- `Alt+S` to move directly to Runtime Status;
- accessible controls for choosing the activation hotkey;
- confirmation before deleting a downloaded model;
- warnings before closing with unsaved Word Bank changes; and
- a single keyboard stop for the overall word and clip count.

Accessibility is an ongoing part of development. Bug reports describing the
screen reader, keyboard sequence, expected result, and actual result are
especially useful.

## Install

Download the current installer from
[GitHub Releases](https://github.com/ShreyBhatt-108/SpeakToBridge/releases/latest),
then run `SpeakToBridge-Setup.exe`.

The current installer is not digitally signed, so Windows may display an
unknown-publisher or SmartScreen warning. Verify that the download came from
this repository's Releases page before running it.

On first transcription, the selected Whisper model is downloaded and stored in
local application data. Transcription can run offline after that model is ready.

## Everyday use

1. Open **Speak to Bridge Settings** and choose an activation hotkey.
2. Place the cursor in the application where text should appear.
3. Press the activation hotkey to begin recording.
4. Press it again to stop, transcribe, and insert the text.
5. Press `Ctrl+F8` to have the Windows system voice read the most recent
   transcript aloud.

The default recording limit is 300 seconds. It can be set from 30 to 3,600
seconds under **Show More Settings > Recording Limit**.

The **Play sound effects** checkbox controls the recording, processing, success,
and failure cues. It is enabled by default, takes effect immediately, and is
remembered across restarts. Runtime Status continues to provide accessible text
feedback when sounds are disabled.

### Spoken formatting commands

- Say `new line` to insert a line break. Say it twice for a blank line between
  paragraphs.
- Say `start list`, dictate items separated by commas, semicolons, `and`, or
  `then`, and say `end list` to create bullets.
- For a numbered list, use sequential markers from one through nine between
  `start list` and `end list`, for example: `one, first item, two, second item`.
- Use `open quote` and `close quote` (or `quote` and `unquote`) around quoted
  text.

Whisper may infer punctuation around these phrases; Speak to Bridge removes
that command punctuation before formatting. Editing phrases such as `scratch
that`, `delete that`, and `undo` are not currently implemented.

### Word Bank

Enter one correction per line:

```text
heard_word = CorrectWord
```

Save the Word Bank to apply those corrections to future transcripts.

## Privacy and local data

Speech is transcribed locally after the selected model has been downloaded.
Read-aloud text is passed to Windows PowerShell through standard input rather
than being placed on the process command line.

Settings, models, logs, the Word Bank, and lifetime statistics are stored under:

```text
%LOCALAPPDATA%\SpeakToBridge
```

Uninstalling or upgrading the program preserves this folder. Delete it manually
only when you intentionally want to remove all Speak to Bridge user data.

## Run from source

Python 3.11 or newer is required.

```powershell
git clone https://github.com/ShreyBhatt-108/SpeakToBridge.git
cd SpeakToBridge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements.lock.txt
python -m SpeakToBridge
```

## Build the application

Run the release build from PowerShell:

```powershell
.\build.ps1
```

The script installs the hash-locked runtime and build dependencies, packages the
application with PyInstaller, and uses Inno Setup 6 when available.

Build outputs:

- `dist\SpeakToBridge\SpeakToBridge.exe` — portable folder build;
- `dist\SpeakToBridge-Setup.exe` — Windows installer.

`SpeakToBridge/constants.py` is the single source of the application version. To
Authenticode-sign a release, install the Windows SDK and set
`SPEAK_TO_BRIDGE_SIGNING_CERT_SHA1` to the thumbprint of an available code-signing
certificate before running the build.

## Project structure

```text
SpeakToBridge/
  app.py             Application startup and single-instance handling
  controller.py      Dictation workflow and application coordination
  audio.py           Microphone recording
  ui.py              Settings window and accessible controls
  config.py          Validated user settings
  stats_store.py     Persistent word and clip totals
  sound_feedback.py  Non-visual status cues
build.ps1             Reproducible Windows release build
installer.iss         Inno Setup installer definition
```

The more detailed `CODE_WALKTHROUGH_LOCAL.md` is intentionally ignored by Git
because it is the author's private learning documentation.

## Release notes

Version 1.4.0 adds a persistent, accessible setting for disabling every sound
cue while retaining Runtime Status feedback. It also closes a running tray
instance before uninstalling, preventing locked program files and incomplete
removal notices while continuing to preserve user data. Version 1.3.1 made
spoken list and line-break commands resilient to punctuation inferred by
Whisper. Version 1.3.0 introduced the Speak to Bridge name and “Speak. Bridge.
Done.” welcome message. See
[all releases](https://github.com/ShreyBhatt-108/SpeakToBridge/releases) for
downloadable builds and release history.

## Authorship and AI assistance

Speak to Bridge was conceived, directed, tested, and published by **Shrey Bhatt**.
OpenAI Codex assisted with code review, implementation, documentation, testing,
and release preparation. Shrey Bhatt remains responsible for the project's
design decisions, quality, security, licensing, and published releases.

## Copyright and licensing

Copyright © 2026 Shrey Bhatt. All rights reserved.

The Speak to Bridge source code is publicly viewable, but no permission to copy,
modify, or redistribute it is granted except where required by the licenses of
its third-party components. See [LICENSE](LICENSE) for the project terms and
[THIRD_PARTY_ASSETS.md](THIRD_PARTY_ASSETS.md) for bundled sound provenance.

Python packages and other third-party components remain subject to their own
licenses. The names and trademarks of third parties belong to their respective
owners.
