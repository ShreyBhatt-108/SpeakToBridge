# Releasing Severus AI

This project keeps source code in Git and publishes Windows binaries in GitHub Releases.

## What goes in Git

- Source code and packaging scripts:
  - `SeverusAI/`
  - `build.ps1`
  - `installer.iss`
  - `SeverusAI.spec`
  - `README.md`
  - `RELEASING.md`
  - pinned dependency input files and their hash-locked `*.lock.txt` files
  - `THIRD_PARTY_ASSETS.md`

## What does not go in Git

- Generated artifacts and local-only folders:
  - `dist/`
  - `build/`
  - `.venv/`
  - `__pycache__/`

## Release steps

1. Update version:
   - Change `APP_VERSION` in `SeverusAI/constants.py`.
   - Python packaging, the running app, `build.ps1`, and Inno Setup all read that single value.
2. Build:
   - Run `.\build.ps1`
   - The build script must report a 64-bit Python interpreter before packaging (`AMD64` for x64 releases, `ARM64` for native Windows-on-ARM releases).
   - It installs only dependencies that match the hashes in `requirements.lock.txt` and `build-requirements.lock.txt`.
   - Optional signing: set `SEVERUS_SIGNING_CERT_SHA1` to a valid code-signing certificate thumbprint before building.
3. Verify outputs:
   - `dist\SeverusAI\SeverusAI.exe`
   - `dist\SeverusAI-Setup.exe`
   - `dist\SeverusAI\_internal\_sounddevice_data\portaudio-binaries\libportaudio64bit.dll` for x64 builds
   - `dist\SeverusAI\_internal\_sounddevice_data\portaudio-binaries\libportaudioarm64.dll` for ARM64 builds
4. Commit and push source changes (not `dist/` or `build/`).
5. Create a GitHub Release tag (for example `v1.1`).
6. Upload `dist\SeverusAI-Setup.exe` to Release assets.
7. If distributing the portable build, zip the complete `dist\SeverusAI` directory. The EXE cannot run by itself without `_internal`.

## Notes

- End users should download `SeverusAI-Setup.exe` from Releases.
- The `dist\SeverusAI` directory is the portable build and does not provide a full install/uninstall experience.
- Do not commit or upload `CODE_WALKTHROUGH_LOCAL.md`; it is intentionally ignored and private to the local developer workspace.
- Normal uninstall preserves `%LOCALAPPDATA%\SeverusAI` user data.
