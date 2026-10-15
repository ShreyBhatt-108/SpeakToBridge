# Local release validation: 1.5.1-rc.1

Built and tested on 14 October 2026, Windows 11 x64, Ryzen AI Max+ 388 / Radeon
8060S. These are local candidate artifacts, not an uploaded GitHub Release.

## Artifacts

| File | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| SpeakToBridge-Setup.exe | 99,949,541 | 67e9b86e9199c5cc27506b9809111d653ccdbfd70570bfce62705a3ab9c5388f |
| SpeakToBridge-AMD-Setup.exe | 2,042,864,455 | 24a94cf404c934e71da4b4a2ca01e19645560d51a1e8bbc4ec342bb98c0cb0f7 |

Both contain Python 3.12.10. The standard installer excludes PyTorch, ROCm and
Transformers; the AMD installer includes ROCm 7.2.1 / PyTorch 2.9.1.

## Checks passed

- 44 unittest regressions in the clean CPU environment and AMD build overlay.
- Packaged CPU automatic selection without torch; Tiny, Small and Medium speech.
- Generic CPU ISA and forced MKL Tiny transcription on the AMD host.
- Clean-profile first Tiny download and CPU transcription.
- Packaged Radeon Large v3 transcription and FP16 matrix execution.
- AMD-package explicit CPU transcription and GPU-hidden isolated fallback.
- Actual CPU → AMD → CPU transition without the reproduced OpenMP crash;
  retired CPU workers exited.
- 38.79-second CPU and Radeon recordings included all six repeated sentences.
- Actual standard-then-AMD installer upgrades; AMD upgrade gracefully closed
  the running standard app. No reboot was required.
- Installed CPU and GPU speech checks with PATH limited to Windows tools,
  excluding developer Python environments.
- Settings, Word Bank, stats and WSL preference hashes preserved across upgrades;
  model weight file inventory, sizes and timestamps unchanged.
- Fresh standard/AMD GUI startup with no native inference DLLs loaded. RAM was
  approximately 108/106 MiB; each used 0.00 CPU seconds over a five-second idle
  observation. Both loaded their own bundled python312.dll.

## What remains unverified

This exact candidate has not run on a physical Intel processor or NVIDIA GPU.
Generic ISA and forced MKL testing on AMD improve coverage but do not emulate
Intel hardware. An Intel-machine smoke test is required before claiming that
hardware has been verified. Earlier Intel results apply to earlier builds.

The installers are unsigned and the test host has Smart App Control disabled
by its owner. A trusted signing certificate and protected-machine testing are
still required for reliable Smart App Control distribution. No controlled
battery-life comparison or exhaustive microphone/application compatibility
study was performed.

The optimization check retained model accuracy/precision settings. It fixed
CPU-first OpenMP isolation, explicit worker cleanup and safe upgrade shutdown;
it did not reduce Whisper model size, FP16 precision or four-beam decoding.
