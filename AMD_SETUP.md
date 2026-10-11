# AMD Strix Halo / Radeon 8060S

The source now supports AMD ROCm GPU transcription in addition to existing
faster-whisper CPU and NVIDIA CUDA transcription. CPU mode needs no AMD runtime.
Automatic mode prefers an available ROCm GPU (the 8060S when present), then NVIDIA
CUDA, then CPU. AMD mode uses ROCm or falls back to CPU. GPU initialization or
transcription failures retry on CPU; Apply Processing Device allows a GPU retry.

## Install the bundled AMD release

Download `SpeakToBridge-AMD-Setup.exe` from the GitHub prerelease and install it.
It includes Python, ROCm PyTorch and Transformers; no separate Python setup is
needed. Quit the old app from the tray before installing. The graphics driver
is supplied separately by AMD/Lenovo and is not included in our installer.

Choose **Automatic GPU with CPU fallback** in Settings and dictate a sentence.
The **Loaded backend** and **Last transcription** fields report the actual
backend, such as **AMD ROCm GPU: AMD Radeon 8060S ... (FP16)**.
If it reports CPU, dictation still works but GPU acceleration was not activated.

The current prerelease targets Ryzen AI Max+ 388 / Radeon 8060S (`gfx1151`).
The bundled runtime is ROCm 7.2.1 / PyTorch 2.9.1; the legacy AMD 7.2.1 Windows
matrix lists the same gfx1151 architecture but does not explicitly name the 388.
The newer AMD ROCm documentation explicitly lists the 388. The original native Windows bundle has not passed GPU verification on this
388 under Smart App Control. The shared WSL backend described below has passed
real Tiny, Small and Large v3 GPU transcription on this hardware.

AMD's [Adrenalin 26.2.2 release page](https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-2-2.html)
contains the official driver download for the documented ROCm 7.2.1 combination.
For a Legion, use the Lenovo support page for your precise machine model if its
OEM driver is required. We have not tested newer graphics drivers with this build.

For a troubleshooting report, run the installed EXE from PowerShell:

```powershell
& 'C:\path\to\SpeakToBridge.exe' --check-hardware --require-amd
```

It writes `%LOCALAPPDATA%\SpeakToBridge\hardware-diagnostics.json`, including
CPU/GPU names, driver version, bundled runtime imports, and an FP16 GPU matrix
test. This is separate from real transcription verification. Add `--wav` with a
16 kHz mono PCM16 speech recording to also test Whisper and report its backend:

```powershell
& 'C:\path\to\SpeakToBridge.exe' --check-hardware --require-amd --wav 'C:\path\speech.wav'
```

## Run from source on the new Windows computer

1. Copy the updated SpeakToBridge project to the AMD computer.
2. Install **Windows 11**, **x64 Python 3.12**, and the AMD graphics driver supported
   by the ROCm 7.2.1 Windows release. AMD documents driver 26.2.2 for this release;
   follow the linked installation guide for a compatible driver.
3. In PowerShell, from the project folder, run:

   ```powershell
   .\scripts\setup_amd.ps1
   .\scripts\launch_amd.ps1
   ```

   If Python 3.12 is not registered with `py`, pass its executable:

   ```powershell
   .\scripts\setup_amd.ps1 -Python 'C:\path\to\Python312\python.exe'
   ```

4. Quit any old instance from the tray first. In the updated app, choose
   **Automatic GPU with CPU fallback** or **AMD GPU (ROCm) with CPU fallback**
   and press **Apply Processing Device**. Runtime Status reports the actual
   device after the first transcription, including the Radeon model name.

The setup script uses one reusable `%USERPROFILE%\.venvs\amd-rocm-7.2.1-py312`
environment without changing the ordinary Python environment. Pass
`-EnvironmentPath` to setup and launch, or set `SPEAK_TO_BRIDGE_AMD_ENV`, to use
another shared environment. The launcher also accepts an existing `.venv-amd`. It installs AMD's official ROCm 7.2.1 / PyTorch 2.9.1 Windows wheels
and Transformers 4.57.6, checks dependencies, and runs an FP16 GPU matrix test.
It intentionally fails verification if an AMD GPU is unavailable.

The standard `SpeakToBridge-Setup.exe` uses CPU/NVIDIA inference and does not
include the large AMD runtime. Use the AMD installer for the 8060S, or the source
launcher above. Both installers use the same app identity and preserve user data.

## Verify real transcription on the 8060S

Use a 16 kHz mono PCM16 WAV containing speech:

```powershell
& "$env:USERPROFILE\.venvs\amd-rocm-7.2.1-py312\Scripts\python.exe" .\scripts\check_hardware.py --require-amd --transcribe 'C:\path\speech.wav' --model small
```

This prints a transcript and the actual backend. It exits with failure if GPU
inference falls back to CPU. Detection and matrix multiplication alone are not
proof of successful Whisper inference.

AMD GPU mode downloads original OpenAI Whisper models separately from the
existing Systran faster-whisper cache, into the same app models directory. The
first use needs internet access and extra disk space; subsequent cached model
loads and audio processing are local. Both cache formats appear in Settings.
VAD settings and Word Bank prompts are preserved. Long recordings use sequential
Whisper decoding rather than truncating at 30 seconds. Backend outputs may differ
slightly and GPU speed depends on model size, memory, and drivers.

## Validation on this connected computer

When ROCm PyTorch is loaded, CPU fallback runs faster-whisper in a separate
worker process. This avoids conflicting OpenMP libraries while retaining the
existing INT8 CPU engine. The worker exits when its model is released.

This computer reports an Intel i7-11390H and Iris Xe, not an AMD 8060S.
Automated tests cover ROCm selection, rejection of NVIDIA PyTorch as ROCm,
CPU-only mode, loading and inference fallback, prompt forwarding, long audio,
silence handling, and model caches. **Actual Radeon 8060S inference and performance
remain unverified until the command above is run on the new computer.**

The actual Transformers adapter also passed short and longer-than-30-second
speech inference on CPU. The ordinary packaged build passed a real CPU
transcription test. These checks do not establish GPU kernel compatibility.

## Upstream documentation

- [AMD Windows compatibility matrix](https://rocmdocs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/windows/windows_compatibility.html)
- [AMD ROCm PyTorch installation](https://rocmdocs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/windows/install-pytorch.html)
- [CTranslate2 CPU instruction selection and GPU support](https://opennmt.net/CTranslate2/hardware_support.html)
- [Transformers Whisper long-form transcription](https://huggingface.co/docs/transformers/v4.57.6/en/model_doc/whisper)

## Legion laptop validation, October 10, 2026

The packaged app uses its own Python 3.12; users do not need Python installed,
and another system Python version (including 3.15) does not affect the installer.
The source ROCm environment requires 3.12 because AMD's pinned wheel is cp312.

Two release failures were reproduced on Ryzen AI Max+ 388 / Radeon 8060S:

- QtCore import failed with WinError 127. A Poppler ICU 78 DLL from the build
  host's PATH was collected as `_internal/icuuc.dll`. Its versioned exports do
  not match Qt's Windows ICU imports. SHA256 comparison identified the exact
  Poppler DLL. The build now removes that conflicting DLL from the app search
  path; Qt loads Windows ICU. No package version was changed for this repair.
- CTranslate2's optional converters eagerly imported torch during startup.
  Windows Smart App Control rejected AMD's unsigned `rocm-openblas.dll` with
  WinError 4551 / status 0xc0e90002. The installed file's SHA256 matched the
  official ROCm 7.2.1 wheel, ruling out corruption of that DLL during packaging.

Startup now defers optional torch loading. CPU diagnostics skip GPU imports,
blocked runtime errors are logged without a loader dialog, and CPU fallback
continues in an isolated worker after even a failed ROCm import. The Xet-disable
flag is now set before Hub imports, when its environment settings are read.

The repaired installed AMD executable opened Settings and transcribed a 16 kHz
mono speech WAV on CPU. The same WAV transcribed through the isolated CPU worker
after the real ROCm policy rejection. All 22 regression tests passed.
The GPU-required diagnostic correctly returned exit code 1: Radeon matrix
execution and GPU transcription remain unverified because Windows blocks ROCm.
Driver version reported by Windows was 32.0.22064.1003.

Initial CPU verification used the existing packaged AMD runtime and model cache.
A reusable native Windows environment was subsequently prepared, but remains
blocked by Smart App Control. The selected shared WSL environment is described below. Settings, Word Bank and existing
caches are not reset by these fixes.

A release that must run GPU inference with Smart App Control enabled needs
trusted signatures on its native dependencies, or trusted upstream artifacts.
Signing only the EXE and installer is insufficient. No trusted code-signing
certificate was available on this laptop, so that portion could not be tested.


## Reuse the environment for local AI experiments

From PowerShell in this checkout, run ` .\scripts\activate_amd.ps1`.
Then `python` and `pip` use the shared x64 Python 3.12 environment. The script
sets `HF_HUB_CACHE` to the existing SpeakToBridge model cache for this terminal,
so standard Hugging Face experiments can reuse compatible models. Whisper's
Transformers and CTranslate2 model formats remain separate files.
Run `deactivate` afterward. No system PATH or Python 3.15 packages are changed.

Installing ROCm outside the app does not remove Windows trust requirements.
AMD's current Windows prerequisites explicitly call for Smart App Control off:
https://rocm.docs.amd.com/en/docs-7.14.0/install/rocm.html#prepare-windows-for-rocm-installation
Windows Code Integrity has confirmed this policy blocks the official 7.2.1
OpenBLAS DLL on the Legion. Do not silently change security settings during
setup; obtain the user's decision and verify actual Radeon execution afterward.
The documented driver for this pinned runtime is Adrenalin 26.2.2. WSL is a
separate supported option for Strix Halo, requiring WSL2 and a compatible driver.


## Shared WSL ROCm environment

This Legion uses Ubuntu-24.04 in WSL2, keeping Windows Smart App Control enabled.
The Windows GUI connects to one shared Linux environment at `/opt/amd-ai`:
Python 3.12, ROCm 7.14.1, PyTorch 2.12.0+rocm7.14.1 with the gfx1151 device
packages, Transformers 4.57.6, Hub 0.36.2 and tokenizers 0.22.2. This supported
Linux stack differs from the original pinned Windows 7.2.1 stack.

After installing WSL2 and Ubuntu-24.04, run `scripts/setup_wsl.sh` as root in
Ubuntu. The script installs the GPU-specific AMD wheels and ROCDXG 1.2.1 using
AMD's documented sources. It reuses `/opt/amd-ai` and checks package requirements.

For local AI experiments, open Ubuntu with `wsl -d Ubuntu-24.04`, then run:

```bash
source /opt/amd-ai/bin/activate
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

These are Linux packages; Windows Python 3.15 remains independent. Within the
Linux environment, PyTorch uses its `torch.cuda` API for AMD HIP devices too.
Avoid reinstalling ROCm for each project unless incompatible dependencies require
another environment. SpeakToBridge uses `/opt/amd-ai/bin/python` directly, so
terminal activation is unnecessary for the desktop shortcut.

For an updated installed app built from this source, create
`%LOCALAPPDATA%/SpeakToBridge/wsl-runtime.json` with your actual checkout path:

```json
{
  "enabled": true,
  "distribution": "Ubuntu-24.04",
  "python": "/opt/amd-ai/bin/python",
  "worker": "C:\\path\\to\\SpeakToBridge\\scripts\\wsl_worker.py"
}
```

To run the setup script from PowerShell after Ubuntu is installed, use your
checkout's mounted drive path (the script installs system packages as root):

```powershell
wsl -d Ubuntu-24.04 -u root --exec bash /mnt/c/path/to/SpeakToBridge/scripts/setup_wsl.sh
```

The selected transport is persisted in
`%LOCALAPPDATA%/SpeakToBridge/wsl-runtime.json`, with the distribution, interpreter
and mounted `scripts/wsl_worker.py` path. Keep the checkout at that path.
`scripts/launch_wsl.ps1` provides terminal overrides; setting the persisted
`enabled` field to false selects native mode for a later Windows installation.

Windows retains microphone capture, hotkeys, insertion, settings, Word Bank and
CPU transcription. Local JSON-lines pipes carry audio and Word Bank prompts to
the long-running WSL worker; no network listener is opened. The worker requires
ROCm GPU detection and a passing FP16 matrix test. Windows performs VAD first.
Worker startup or inference failure retries on CPU without probing Windows ROCm
DLLs. Native ROCm's isolated CPU fallback remains intact for OpenMP conflicts.

GPU models are regular files under the existing app cache's
`models/openai-whisper-<size>` directories, downloaded with Hub `local_dir`.
The native AMD adapter recognizes completed downloads there, allowing a later
native setup to reuse them. For experiments, load those local directories with
Transformers to reuse these weights. CTranslate2 CPU weights use a different
format and remain separate; settings, Word Bank and existing caches are preserved.

Target hardware checks after restart: Radeon 8060S detection, FP16 matrix
execution and packaged Tiny/Small/Large v3 speech transcription passed. The runtime reported
18,141,939,712 bytes (16.90 GiB) of GPU memory with the firmware's 2 GB allocation.
Explicit CPU transcription and unavailable-WSL-worker CPU fallback passed.
32 regression tests passed, including persistent backend reporting. See the local troubleshooting report for the latest
Small-model and GUI results. No GPU-enabled release has been published.

AMD installation references:
- https://rocm.docs.amd.com/en/docs-7.14.1/install/rocm.html
- https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html
