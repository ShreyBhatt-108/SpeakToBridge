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
Runtime Status should report **AMD ROCm GPU: AMD Radeon 8060S ... (FP16)**.
If it reports CPU, dictation still works but GPU acceleration was not activated.

The current prerelease targets Ryzen AI Max+ 388 / Radeon 8060S (`gfx1151`).
The bundled runtime is ROCm 7.2.1 / PyTorch 2.9.1; the legacy AMD 7.2.1 Windows
matrix lists the same gfx1151 architecture but does not explicitly name the 388.
The newer AMD ROCm documentation explicitly lists the 388. Actual GPU inference
on the 388 remains a hardware validation step, not a completed test.

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

The setup script creates `.venv-amd` without changing the ordinary Python
environment. It installs AMD's official ROCm 7.2.1 / PyTorch 2.9.1 Windows wheels
and Transformers 4.57.6, checks dependencies, and runs an FP16 GPU matrix test.
It intentionally fails verification if an AMD GPU is unavailable.

The standard `SpeakToBridge-Setup.exe` uses CPU/NVIDIA inference and does not
include the large AMD runtime. Use the AMD installer for the 8060S, or the source
launcher above. Both installers use the same app identity and preserve user data.

## Verify real transcription on the 8060S

Use a 16 kHz mono PCM16 WAV containing speech:

```powershell
.\.venv-amd\Scripts\python.exe .\scripts\check_hardware.py --require-amd --transcribe 'C:\path\speech.wav' --model small
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
