"""Optional Whisper inference on AMD GPUs through ROCm PyTorch.

ROCm intentionally exposes GPUs through torch.cuda; torch.version.hip is
what distinguishes an AMD build from NVIDIA CUDA or CPU-only PyTorch.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def amd_device() -> tuple[int, str] | None:
    try:
        import torch

        if not torch.version.hip or not torch.cuda.is_available():
            return None
        for index in range(torch.cuda.device_count()):
            name = torch.cuda.get_device_name(index)
            if "8060" in name:
                return index, name
        return 0, torch.cuda.get_device_name(0)
    except Exception:
        return None


class AmdWhisperModel:
    def __init__(self, model_name: str, cache_dir: Path, device_index: int) -> None:
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        self._torch = torch
        self._device = f"cuda:{device_index}"
        repository = f"openai/whisper-{model_name}"
        self._processor = WhisperProcessor.from_pretrained(repository, cache_dir=str(cache_dir))
        self._model = WhisperForConditionalGeneration.from_pretrained(
            repository,
            cache_dir=str(cache_dir),
            torch_dtype=torch.float16,
            # Standard attention avoids dependence on optional CUDA-only kernels.
            attn_implementation="eager",
            use_safetensors=True,
        ).to(self._device).eval()

    def transcribe(self, audio: np.ndarray, language: str, initial_prompt: str, vad: dict) -> str:
        if vad.get("vad_filter"):
            from faster_whisper.vad import get_speech_timestamps

            spans = get_speech_timestamps(audio, **vad.get("vad_parameters", {}))
            if not spans:
                return ""
            audio = np.concatenate([audio[span["start"]:span["end"]] for span in spans])
        # Preserve the entire recording: Whisper's sequential long-form decoding
        # handles audio beyond 30 seconds rather than truncating it.
        inputs = self._processor(
            audio, sampling_rate=16_000, return_tensors="pt",
            truncation=False, padding="longest", return_attention_mask=True,
        )
        inputs["input_features"] = inputs["input_features"].to(self._device, self._torch.float16)
        inputs["attention_mask"] = inputs["attention_mask"].to(self._device)
        options = dict(
            language=language, task="transcribe", num_beams=4,
            return_timestamps=True, condition_on_prev_tokens=True,
        )
        if initial_prompt:
            options["prompt_ids"] = self._processor.get_prompt_ids(
                initial_prompt, return_tensors="pt"
            ).to(self._device)
            options["prompt_condition_type"] = "all-segments"
        with self._torch.inference_mode():
            tokens = self._model.generate(**inputs, **options)
        return self._processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
