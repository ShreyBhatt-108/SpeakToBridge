# Local candidate validation: 1.6.0-rc.1

CPU and Radeon frozen builds tested 18–19 October 2026 on Ryzen AI Max+ 388 /
Radeon 8060S. The two supported installers are published as v1.6.0-rc.1 GitHub Release assets.

- 104 automated tests passed in both CPU and AMD environments.
- Both frozen builds processed a synthetic 368.94-second meeting, including
  speech after six minutes, with local AI notes and all three expected task owners.
- CPU used Tiny INT8; Radeon used Small FP16. Different models and concurrent
  installer compression mean these runs are not a CPU/GPU speed benchmark.
- The CPU installer was upgraded and tested with the same long recording;
  settings, Word Bank, statistics and nine cached model files were preserved.
- Actual microphone capture, stop and cleanup passed without retaining test audio.
- The frozen notes runtime worked with developer Python removed from PATH.
- Native hotkey testing covered missed modifier releases and repeat suppression;
  unit tests cover Windows-key chords and the 30-second silence timeout.
- Bandit found no medium/high issues. Windows antivirus scanning of the CPU
  payload, including the new native notes runtime, returned without a detection.
- On 20 October, the installed AMD upgrade passed real Radeon GPU transcription
  and isolated CPU fallback. Settings, Word Bank, statistics and nine model files
  were preserved. Desktop startup reached GPU ready before recording; no restart
  was required.
- A later source-only wording correction labels per-session counts explicitly;
  the installers below predate that text correction. Persistent counts are unchanged.

| Installer | Bytes | SHA-256 |
|---|---:|---|
| SpeakToBridge-Setup.exe | 109,658,828 | `2357730be87a051c5856fb35df239492b5881804638a833cffb02d38d55e2331` |
| SpeakToBridge-AMD-StrixHalo-Setup.exe | 1,679,943,999 | `771c9e006b0987b740adbf401e72650bc88bf9ad95800566278b8061851efdf4` |

---

# Local release validation: 1.5.1-rc.3

Built and tested 15 October 2026 on Windows 11 25H2 x64, Ryzen AI Max+ 388 /
Radeon 8060S, driver 32.0.22064.1003. The v1.5.1-rc.3 release scope is the standard CPU and Strix Halo installers.
CUDA remains a local candidate; universal AMD is local testing only.

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
The independent [Windows CI run](https://github.com/ShreyBhatt-108/SpeakToBridge/actions/runs/38843858830)
passed all regression tests, built the standard installer, transcribed with
bundled Python and generic CPU instructions, and passed dependency audits.
Runner hardware is reported by diagnostics rather than assumed. Other AMD targets have kernel
selection regression coverage but need physical device/driver validation.
Installers remain unsigned; scanning and package audits are not code signing.

Temporary obsolete build environments, duplicate wheel downloads and tested
unpacked staging copies were removed after verification, reclaiming
19,543,706,052 bytes. Final installers, active build tools, installed application,
user data and shared experimental environments were retained.
