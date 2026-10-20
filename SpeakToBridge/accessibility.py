"""Short automatic messages; diagnostic detail remains in the application log."""
from __future__ import annotations

import re


def concise_status(message: str) -> str:
    text = message.split(" Processing: ", 1)[0].strip()
    lower = text.lower()
    if lower.startswith("recording. press "):
        match = re.search(r"Press (.+?) again", text)
        return f"Recording. {match.group(1)} to stop." if match else "Recording."
    if lower.startswith("ready. press "):
        match = re.search(r"Press (.+?) to start", text)
        return f"Ready. {match.group(1)} to dictate." if match else "Ready."
    if lower.startswith("transcript ready:"):
        match = re.search(r"(\d+) words", text)
        return f"Done. {match.group(1)} words." if match else "Done."
    if lower.startswith("model ready"):
        return "Model ready. GPU." if "gpu" in lower else "Model ready. CPU." if "cpu" in lower else "Model ready."
    if lower.startswith("transcribing with"):
        return "Transcribing on GPU." if "gpu" in lower else "Transcribing on CPU."
    if lower.startswith("transcribing"):
        return "Transcribing."
    patterns = (
        (("starting amd gpu", "starting wsl pytorch", "preparing native amd"), "Starting GPU."),
        (("reading cached model", "loading model", "checking local gpu", "packing model weights"), "Loading model."),
        (("moving model weights",), "Loading GPU model."),
        (("warming radeon",), "Preparing GPU."),
        (("gpu initialization failed",), "GPU unavailable. Using CPU."),
        (("gpu transcription failed",), "GPU failed. Retrying on CPU."),
        (("processing device saved",), "Device saved. Preparing model."),
        (("word bank saved",), "Word Bank saved."),
        (("unable to start microphone",), "Microphone unavailable. Check microphone settings."),
        (("transcription failed",), "Transcription failed. Details are in the log."),
        (("maximum recording length reached",), "Recording limit reached. Transcribing."),
        (("30 seconds without speech",), "Silence timeout. Transcribing."),
        (("downloading missing gpu model", "downloading model"), "Downloading model."),
    )
    for prefixes, brief in patterns:
        if lower.startswith(prefixes):
            return brief
    # Keep unknown errors/actions intact: truncation can remove recovery advice.
    return text
