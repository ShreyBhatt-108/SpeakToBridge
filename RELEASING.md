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

## What does not go in Git

- Generated artifacts and local-only folders:
  - `dist/`
  - `build/`
  - `.venv/`
  - `__pycache__/`

## Release steps

1. Update version:
   - `SeverusAI/__init__.py` (`__version__`)
   - `installer.iss` (`AppVersion`)
2. Build:
   - Run `.\build.ps1`
   - The build script must report a 64-bit Python interpreter before packaging (`AMD64` for x64 releases, `ARM64` for native Windows-on-ARM releases).
3. Verify outputs:
   - `dist\SeverusAI.exe`
   - `dist\SeverusAI-Setup.exe`
   - `dist\SeverusAI\_internal\_sounddevice_data\portaudio-binaries\libportaudio64bit.dll` for x64 builds
   - `dist\SeverusAI\_internal\_sounddevice_data\portaudio-binaries\libportaudioarm64.dll` for ARM64 builds
4. Commit and push source changes (not `dist/` or `build/`).
5. Create a GitHub Release tag (for example `v1.1`).
6. Upload `dist\SeverusAI-Setup.exe` to Release assets.
7. Optional: also upload `dist\SeverusAI.exe` for portable users.

## Notes

- End users should download `SeverusAI-Setup.exe` from Releases.
- `SeverusAI.exe` is a portable build and does not provide a full install/uninstall experience.
