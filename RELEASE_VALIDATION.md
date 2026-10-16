# Local release validation: 1.5.1-rc.3

Built and tested 15 October 2026 on Windows 11 25H2 x64, Ryzen AI Max+ 388 /
Radeon 8060S, driver 32.0.22064.1003. These installers are local candidates;
no GitHub Release binaries have been uploaded.

| Installer | Bytes | SHA-256 |
|---|---:|---|
| SpeakToBridge-Setup.exe | 101,528,904 | `1360716d030da0249e008b585ad391550de1eadca54c6a92bee698418932b17f` |
| SpeakToBridge-CUDA-Setup.exe | 1,111,938,206 | `cb5c57e4fe2bd522107c9006319cc4f3a37239117970728648c3ad1a0ef2d636` |
| SpeakToBridge-AMD-StrixHalo-Setup.exe | 1,671,504,715 | `90b2b06557368951530611488a9cac6f48e531a001ec0dc5b7cfae6030e98401` |
| SpeakToBridge-AMD-Universal-Setup.exe | 2,928,054,634 | `f5b147f68ec46afc2ae04df66b626f5d3d4eeb0c737da43c9c4e3d530df0aeb0` |

The universal AMD installer exceeds GitHub's 2 GiB per-asset limit and is for
local testing. Publish hardware-specific AMD packages instead. The Strix Halo
package retains gfx1151/family kernels and shared runtime DLLs. Its unpacked
payload is 3,804,550,161 bytes versus rc.1's 6,906,792,132 bytes (about 45%
smaller). Headers/static libraries/compiler executables remove 1,997,705,229
bytes; targeting removes a further 2,784,392,806 bytes from the new universal
payload. Models retain their original precision and decoding settings.

## Functional checks

- All **68 tests passed in both CPU-only and AMD Python 3.14.8 environments**.
- Standard frozen CPU package: actual Tiny/Small/Medium transcription, automatic
  CPU selection without PyTorch, generic instruction dispatch and forced MKL
  checks passed on this AMD host. Final Medium also transcribed a 38.79-second
  recording containing six sentences beyond Whisper's 30-second window.
- Native Radeon GPU: actual Tiny/Small/Medium/Large v3 transcription passed.
  Final universal Large v3 passed the same 38.79-second six-sentence recording.
  FP16 matrix execution passed; transcription reports confirmed the AMD backend.
- Final standard → CUDA → universal AMD → Strix Halo installer upgrades passed.
  Installed GUI startup, Radeon Large v3 inference, explicit CPU fallback and
  CUDA-package automatic CPU fallback passed with developer Python removed
  from PATH. Final compact Tiny/Small/Medium/Large v3 checks passed too.
- Config, Word Bank, statistics, WSL preference and model inventory were compared
  across actual upgrades and preserved. Desktop application ends on Strix Halo.
- Actual Qt model-management integration passed confirm/cancel, background
  deletion, refresh, selected-model protection and restored controls. Disposable
  caches tested traversal/junction rejection and WSL deletion confirmation.
  Real Word Bank CRUD and busy-state behavior are regression covered.
- Shortened accessibility text preserves both Qt accessibility events per
  status update. Detailed status remains available; microphone details can be
  expanded with the keyboard. Actual JAWS speech output was not captured.

## Runtime, performance and security

Python 3.14.8; official AMD PyTorch 2.14.0+rocm10.1.0 / ROCm SDK 10.1.0
(HIP reports 7.16.26385); Transformers 5.20.0. CPU and AMD inference retain
separate processes to avoid conflicting OpenMP runtimes. CUDA workers can retry
the same recording on CPU after a native worker failure.

A quiet native Large v3 measurement prepared in about 20.4 seconds and processed
the 6.46-second speech fixture in 1.36 seconds, then 1.25 seconds on repeat.
Idle inference CPU time was zero during a 10-second observation. Cold preparation
is heavier than the older runtime's approximately 11.5-second measurement;
this release does not claim to eliminate cold-loading costs or establish battery
life. Synthetic warm-up limits generation to two tokens; real dictation keeps
normal token limits, four beams and timestamp processing.

Advisory scans returned zero known findings for 38 CPU dependencies, 53 ordinary
AMD/model dependencies, upstream PyTorch 2.14.0 and four NVIDIA runtime packages.
Bandit returned no medium/high findings. Final frozen payloads were scanned by
Windows Defender without detections. Version/hash locks, pinned model revisions,
safetensors-only loading and deletion/subprocess fixes are documented in
[security review](SECURITY_REVIEW.md).

No physical NVIDIA GPU or separate Intel CPU was available for this local run.
CUDA DLL loading and fallback passed; these do not verify actual NVIDIA inference.
The pinned Windows CI workflow builds and transcribes on its runner after push;
runner hardware is reported rather than assumed. Other AMD targets have kernel
selection regression coverage but need physical device/driver validation.
Installers remain unsigned; scanning and package audits are not code signing.
