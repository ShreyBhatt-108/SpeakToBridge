# Security and storage review — 15 October 2026

Scope: SpeakToBridge 1.5.1-rc.3 source, Windows installers, model loading and
deletion, subprocess boundaries, locked runtime dependencies and inference.

## Dependency fixes

The earlier candidate contained Python 3.12.10, ROCm PyTorch 2.9.1 and
Transformers 4.57.6. Its AMD dependency audit returned 13 records covering 10
distinct advisory IDs. The final candidate replaces that runtime:

- Python **3.14.8**, including its current security maintenance fixes.
- AMD's official stable **PyTorch 2.14.0+rocm10.1.0** and ROCm SDK **10.1.0**.
  Its HIP component reports **7.16.26385**; SDK and HIP version strings differ.
- Transformers **5.20.0**, Hugging Face Hub **1.33.0**, safetensors **0.8.0**.
- Optional CUDA package: NVIDIA cuBLAS **12.9.2.10**, cuDNN **9.27.0.42**,
  CUDA runtime **12.9.79** and NVRTC **12.9.86**.

`pip-audit` returned no known findings for the 38 locked CPU dependencies, the
53 pinned AMD model/ordinary runtime dependencies, upstream PyTorch 2.14.0,
or the four NVIDIA packages. Vendor ROCm suffixes were removed only for the
upstream PyTorch advisory lookup. This is a published-advisory check, not an
audit of every native DLL or graphics-driver implementation.

Transformers 5.10 failed with the old Windows ROCm build's missing distributed
module. Current 5.20 imports successfully; the new PyTorch also includes the
distributed components. Actual Tiny and Large v3 GPU transcription and FP16
matrix execution passed on Radeon 8060S with the existing driver. All 68
regression tests passed under Python 3.14.8 in CPU-only and AMD environments.

PyPI artifacts and official AMD vendor artifacts have pinned versions and
SHA-256 hashes. The AMD metadata package builds with the pinned setuptools and
build isolation disabled. Release builds reject Python older than 3.14.8 and
AMD builds reject the superseded PyTorch runtime. Existing experimental Python
environments and optional legacy WSL installations are separate from the
bundled application and were not silently deleted or upgraded.

## Application fixes

- GPU model downloads pin official OpenAI repository revisions. Model loading
  uses safetensors, concrete Whisper classes, eager attention and no remote code.
  Local metadata is size bounded and rejects custom generation/attention code.
- Model deletion rejects traversal, symbolic links and Windows junctions,
  protects every cache layout of the selected model, runs in the background,
  handles errors and refreshes the list. WSL manifests change only following
  a confirmed worker response. Tests use disposable model folders.
- CUDA inference runs in an isolated process. A native worker failure can retry
  the same recording on CPU without taking the GUI down. Regression coverage
  verifies the original audio is retried and the failed worker is closed.
- The separate ROCm/CPU worker fix remains, preserving OpenMP isolation.
- System PowerShell/WSL paths are absolute. Speech text goes over stdin, and
  subprocess argument arrays avoid treating dictated text as executable code.
- The installer requests graceful shutdown using the original user's token.
  Settings, Word Bank and model caches remain outside the application payload.

Bandit reported no medium/high findings; remaining low findings were reviewed.
The review also checks executable startup, installed CPU/GPU inference,
installer transitions and preservation of user-data hashes/model inventory.
Final artifact measurements and upgrade results are in
[RELEASE_VALIDATION.md](RELEASE_VALIDATION.md).

## Accessibility and storage

Automatic messages retain the same two explicit Qt accessibility events per
status update, with shorter text. Detailed status remains in tooltips/logs;
microphone technical details have an accessible expansion control. Tests verify
Qt event text/counts; actual JAWS speech output was not recorded.

The AMD payload excludes 1,997,705,229 bytes of build-only headers, static
libraries and compiler executables. Shared runtime DLLs, required GPU kernels and licenses stay. The Strix Halo
profile removes a further 2,784,392,806 bytes of other GPU targets. Its installed
payload is about 45% smaller than rc.1, with no weight precision change.
The universal AMD package includes gfx1100/1101/1102/1103/1150/1151/1200/1201
kernels and is for local testing because it exceeds GitHub's 2 GiB asset
limit; publish target-specific builds. The CPU installer carries neither AMD nor NVIDIA runtimes; CUDA users
can use the separate CUDA installer with redistributable DLLs instead of a full
development toolkit. Existing user models, settings and experimental runtimes
are preserved. No model accuracy/precision reductions were made for storage.

## Primary references

- [AMD stable packaging and device extras](https://github.com/ROCm/TheRock/blob/main/RELEASES.md)
- [Upstream distributed-import fix](https://github.com/huggingface/transformers/issues/47603)
- [Python 3.14.8 security maintenance](https://www.python.org/downloads/release/python-3148/)
- [faster-whisper NVIDIA runtime requirements](https://github.com/SYSTRAN/faster-whisper#gpu)
- [Original-user installer helper](https://jrsoftware.org/ishelp/topic_isxfunc_execasoriginaluser.htm)
