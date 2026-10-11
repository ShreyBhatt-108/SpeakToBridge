# Releasing Speak to Bridge

This project keeps source code in Git and publishes Windows binaries in GitHub Releases.

## What goes in Git

- Source code and packaging scripts:
  - `SpeakToBridge/`
  - `build.ps1`
  - `installer.iss`
  - `SpeakToBridge.spec`
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
   - Change `APP_VERSION` in `SpeakToBridge/constants.py`.
   - Python packaging, the running app, `build.ps1`, and Inno Setup all read that single value.
2. Build:
   - Run `.\build.ps1`
   - The build script must report a 64-bit Python interpreter before packaging (`AMD64` for x64 releases, `ARM64` for native Windows-on-ARM releases).
   - It installs only dependencies that match the hashes in `requirements.lock.txt` and `build-requirements.lock.txt`.
   - Optional signing: set `SPEAK_TO_BRIDGE_SIGNING_CERT_SHA1` to a valid code-signing certificate thumbprint before building.
3. Verify outputs:
   - `dist\SpeakToBridge\SpeakToBridge.exe`
   - `dist\SpeakToBridge-Setup.exe`
   - `dist\SpeakToBridge\_internal\_sounddevice_data\portaudio-binaries\libportaudio64bit.dll` for x64 builds
   - `dist\SpeakToBridge\_internal\_sounddevice_data\portaudio-binaries\libportaudioarm64.dll` for ARM64 builds
4. Commit and push source changes (not `dist/` or `build/`).
5. Create a GitHub Release tag (for example `v1.1`).
6. Upload `dist\SpeakToBridge-Setup.exe` to Release assets.
7. If distributing the portable build, zip the complete `dist\SpeakToBridge` directory. The EXE cannot run by itself without `_internal`.

## Notes

### AMD runtime release

Install the official ROCm 7.2.1 Windows SDK packages and PyTorch 2.9.1 wheel
listed in `scripts/setup_amd.ps1` into an x64 Python 3.12 build environment.
GPU availability is not required on the build host. Set
`SPEAK_TO_BRIDGE_BUILD_PYTHON` to that interpreter and run `build.ps1 -AmdRuntime`.
The script installs the ordinary hash lockfiles, reconciles the explicitly pinned
AMD model dependencies from `requirements-amd.txt`, verifies ROCm imports, and
bundles torch, Transformers and the ROCm SDK runtime packages. This AMD dependency layer
is version-pinned but does not yet have a complete hash lockfile.

The output is `dist\SpeakToBridge-AMD-Setup.exe`. Build the ordinary CPU installer
first if shipping both; its installer remains in `dist` while the portable folder
is replaced by the AMD build. Generated PyInstaller specs are stored under `build`.
Do not include private walkthroughs or local build-tool environments in a release.
The installer replaces the old `_internal` dependency directory during an upgrade
to prevent stale Python extensions and conflicting package metadata when switching
between CPU and AMD builds. App user data is stored outside that directory.

Before uploading, execute the packaged `SpeakToBridge.exe --check-hardware`
diagnostic and a CPU transcription test using `--cpu --wav`. For the AMD build,
verify `rocm_version` and `whisper_imports` even on a non-AMD build host. AMD GPU
matrix multiplication and actual speech inference must be checked on the target
hardware. Publish as a prerelease while that hardware validation is pending.

- End users should download `SpeakToBridge-Setup.exe` from Releases.
- The `dist\SpeakToBridge` directory is the portable build and does not provide a full install/uninstall experience.
- Do not commit or upload `CODE_WALKTHROUGH_LOCAL.md`; it is intentionally ignored and private to the local developer workspace.
- Normal uninstall preserves `%LOCALAPPDATA%\SpeakToBridge` user data.

### Startup and Windows trust checks

The installer is self-contained: end users need no Python installation. Its
internal Python version follows the native wheel ABI, not the user's Python.

`build.ps1` removes a versioned vendor ICU accidentally collected as
`_internal/icuuc.dll`, which otherwise shadows Windows ICU and prevents QtCore
from importing. Keep the DLL provenance and Qt startup checks in release QA.

When `SPEAK_TO_BRIDGE_SIGNING_CERT_SHA1` is set, the build signs unsigned or
invalidly signed EXE, DLL and PYD files before compiling the installer, preserving
valid vendor signatures. Use a trusted code-signing certificate for Smart App
Control compliance. The signing path still requires validation with a real
certificate; self-signed signatures do not establish that trust.

A CPU-required diagnostic must not import torch. GPU-required verification must
fail if actual transcription uses CPU. Include the complete optional runtime
traceback and `cpu_worker_isolated` field in target-hardware reports. A successful
CPU fallback after a blocked AMD DLL does not establish Radeon inference.


### WSL backend validation

The optional WSL transport keeps the Windows GUI and CPU engine while running
GPU inference in a separately installed, shared Linux environment. Its local
configuration and mounted worker path are machine-specific; do not ship this
laptop's AppData selection as a release default. `scripts/setup_wsl.sh` prepares
Ubuntu 24.04's `/opt/amd-ai` using GPU-specific ROCm 7.14.1/PyTorch 2.12.0 wheels.

For release QA, test packaged `--check-hardware --require-amd --wav` on actual
hardware: both `gpu_matrix_test` and an AMD ROCm WSL `actual_backend` must pass.
Also test `--cpu --wav` and an unavailable worker. The GPU-required check must
return nonzero when transcription falls back, even if the CPU transcript succeeds.
Verify model changes/cache refresh do not import native Windows ROCm when WSL
is selected. Preserve the isolated native CPU worker and shared model cache.
