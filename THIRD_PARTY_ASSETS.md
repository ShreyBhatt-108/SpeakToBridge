# Third-party assets

The following short sound effects are bundled as application feedback cues. They were downloaded from Mixkit on August 10, 2026 and are used under the Mixkit Sound Effects Free License:

- `SpeakToBridge/status_processing.mp3` — “Software interface start” (asset 2574)
  - Source: https://assets.mixkit.co/active_storage/sfx/2574/2574-preview.mp3
- `SpeakToBridge/status_success.mp3` — “Correct answer tone” (asset 2870)
  - Source: https://assets.mixkit.co/active_storage/sfx/2870/2870-preview.mp3
- `SpeakToBridge/status_failure.mp3` — “Wrong answer fail notification” (asset 946)
  - Source: https://assets.mixkit.co/active_storage/sfx/946/946-preview.mp3

License: https://mixkit.co/license/

Mixkit does not require attribution for these sound effects, but the sources are recorded here for provenance and future license review.

`SpeakToBridge/status_success.wav` is a 450 ms PCM excerpt of
`status_success.mp3`, with a short fade at the end, used for immediate
completion feedback. It retains the source asset attribution above.

`SpeakToBridge/vad.py` adapts the VAD timestamp and Silero inference code from
faster-whisper 1.2.1 (SYSTRAN, MIT license). It reuses the already-bundled Silero
VAD v6 ONNX asset. The code's original license is retained in its header and in
`third_party/faster-whisper-LICENSE`, included in packaged builds under `licenses`.
Only asset lookup, float32 normalization and passive ONNX waiting are changed.
