# AMD GPU setup

The 1.5.1-rc.3 Windows candidate includes Python 3.14.8, AMD's official stable
ROCm SDK 10.1.0 / PyTorch 2.14.0+rocm10.1.0, and Transformers 5.20.0.
The HIP component reports 7.16.26385. Users do not need a system Python, a
virtual environment, WSL, or a separate ROCm installation to use this installer.
Another installed Python version does not affect it.

## Choose an installer

- `SpeakToBridge-Setup.exe`: small CPU package. Also supports an existing
  compatible NVIDIA CUDA/cuDNN runtime; otherwise uses CPU.
- `SpeakToBridge-CUDA-Setup.exe`: includes NVIDIA CUDA 12 / cuDNN 9 runtime
  DLLs. A compatible NVIDIA graphics driver is still needed for GPU execution.
- Hardware-specific `SpeakToBridge-AMD-gfxNNNN-Setup.exe`: native Windows
  AMD GPU runtime with matching/family kernels for the named target.

- `SpeakToBridge-AMD-StrixHalo-Setup.exe`: compact gfx1151/Radeon 8060S
  variant, with matching/family kernels and the same CPU fallback.

`SpeakToBridge-AMD-Universal-Setup.exe` contains all eight targets
(gfx1100/1101/1102/1103/1150/1151/1200/1201). It is for local testing; its
current size exceeds GitHub's 2 GiB per-asset limit. Release builds must select
a target explicitly, for example `build.ps1 -AmdRuntime -AmdTarget gfx1151`.

The v1.5.1-rc.3 release ships the CPU and Strix Halo variants; CUDA and other
GPU targets are outside this release's validated scope. All variants use the same
application identity and can replace each other without deleting settings,
Word Bank, statistics or models. Existing instances save and close during an
upgrade. Graphics drivers are separate, supplied by AMD/Lenovo or NVIDIA.

Choose **Automatic GPU with CPU fallback** in Settings. **Loaded backend**
shows the loaded engine; **Last transcription** shows what processed the last
recording. GPU initialization or transcription failures retry on CPU. Apply
Processing Device allows a GPU retry after fixing the cause.

## Verify a Windows installation

```powershell
& 'C:\path\SpeakToBridge.exe' --check-hardware --require-amd --wav 'C:\path\speech.wav'
```

Use 16 kHz mono PCM16 speech. The report at
`%LOCALAPPDATA%\SpeakToBridge\hardware-diagnostics.json` includes driver/runtime
versions, GPU matrix execution, transcript and actual backend. Matrix execution
alone does not establish successful Whisper transcription.

The new runtime passed actual Tiny and Large v3 transcription on Ryzen AI Max+
388 / Radeon 8060S with driver 32.0.22064.1003. CPU-only transcription and AMD
package CPU fallback passed too. See [release validation](RELEASE_VALIDATION.md)
for exact packaged tests and [security review](SECURITY_REVIEW.md) for audits.
Other included AMD targets still require real hardware testing; having their
kernels in the installer does not prove every driver/device combination works.

## Shared environment for development and AI experiments

Install x64 Python **3.14.8 or newer 3.14 maintenance**, then:

```powershell
.\scripts\setup_amd.ps1
.\scripts\launch_amd.ps1
```

Pass `-Python 'C:\path\Python314\python.exe'` if `py -3.14` is unavailable.
Setup creates/reuses `%USERPROFILE%\.venvs\amd-rocm-10.1-py314`, installs
hash-locked model dependencies and official AMD artifacts, checks dependencies
and performs an actual GPU matrix test. It does not change the ordinary Python
environment. Use `-EnvironmentPath` or `SPEAK_TO_BRIDGE_AMD_ENV` for another
location. `scripts\activate_amd.ps1` activates it for experiments and points
Hugging Face at the app's shared model cache. Existing older environments are
left alone; the installer does not depend on them.

## Model storage and CPU fallback

Models remain in `%LOCALAPPDATA%\SpeakToBridge\models` by default. AMD uses
OpenAI safetensors; CPU/NVIDIA use CTranslate2's converted format, so each format
needs its own weights. First use downloads the selected format; cached inference
is local. GPU downloads pin official OpenAI revisions and do not execute remote
model code. Settings lists both formats, confirms deletion, protects the selected
model and deletes other models in the background. Deleting a model never removes
Word Bank or settings.

ROCm and CTranslate2 CPU inference use separate processes to avoid their OpenMP
runtime conflict. CUDA inference also uses a worker, allowing CPU retry if a
native CUDA/cuDNN failure terminates that worker. Long recordings preserve audio
beyond Whisper's 30-second window.

## Optional WSL path and original failures

WSL remains optional for users who already configure its separate Linux runtime.
The installed native Windows package does not require or update that runtime.
Earlier Linux Tiny/Small/Medium/Large v3 tests are historical validation, not
verification of a new Linux dependency upgrade in this release.

The original v1.5 AMD startup failure involved a build-host Poppler ICU DLL
incompatible with Qt's imports, and Windows rejecting the official ROCm 7.2.1
OpenBLAS DLL under Smart App Control. The conflicting ICU collection and eager
GPU imports were repaired. No installer changes the user's Windows protection
settings. Current native verification took place after the owner had disabled
Smart App Control independently.

- [AMD stable packaging](https://github.com/ROCm/TheRock/blob/main/RELEASES.md)
- [CTranslate2 hardware support](https://opennmt.net/CTranslate2/hardware_support.html)
- [faster-whisper NVIDIA requirements](https://github.com/SYSTRAN/faster-whisper#gpu)

## Meeting notes in 1.6

Meetings reuse the selected native ROCm or CPU Whisper backend. Automatic notes
run in an isolated CPU llama.cpp process, using a separate 1.28 GB Qwen3 GGUF
model in the Windows app cache. They do not require another ROCm installation
or a change to the shared experimental Python environment.
