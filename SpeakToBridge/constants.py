APP_NAME = "Speak to Bridge"
APP_TAGLINE = "Speak. Bridge. Done."
APP_ORG = "SpeakToBridge"
APP_AUTHOR = "Shrey Bhatt"
APP_COPYRIGHT = "Copyright (C) 2026 Shrey Bhatt"
APP_VERSION = "1.3.1"

MODEL_CHOICES = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "high (large-v3)": "large-v3",
}

DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "en"
DEFAULT_RUNTIME_MODE = "cpu_auto_gpu"
DEFAULT_ACTIVATION_HOTKEY = "ctrl+f9"
DEFAULT_READ_HOTKEY = "ctrl+f8"
DEFAULT_VAD_MODE = "pause_preserving"
DEFAULT_MAX_RECORDING_SECONDS = 300
MIN_MAX_RECORDING_SECONDS = 30
MAX_MAX_RECORDING_SECONDS = 3600
