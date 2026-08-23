from __future__ import annotations

import logging
from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


LOGGER = logging.getLogger(__name__)


class SystemAudioDucker:
    def __init__(self, duck_level: float = 0.25) -> None:
        self._duck_level = max(0.0, min(1.0, duck_level))
        self._endpoint = None
        self._restore_volume: float | None = None
        self._available = True

    def duck(self) -> None:
        if not self._available:
            return
        endpoint = self._get_endpoint()
        if endpoint is None:
            return
        if self._restore_volume is not None:
            return
        try:
            self._restore_volume = float(endpoint.GetMasterVolumeLevelScalar())
            target = min(self._restore_volume, self._duck_level)
            endpoint.SetMasterVolumeLevelScalar(target, None)
        except Exception:
            LOGGER.exception("Failed to duck system audio")
            self._restore_volume = None

    def restore(self) -> None:
        if not self._available:
            return
        endpoint = self._get_endpoint()
        if endpoint is None:
            self._restore_volume = None
            return
        if self._restore_volume is None:
            return
        try:
            endpoint.SetMasterVolumeLevelScalar(self._restore_volume, None)
        except Exception:
            LOGGER.exception("Failed to restore system audio")
        finally:
            self._restore_volume = None

    def _get_endpoint(self):  # noqa: ANN001
        if not self._available:
            return None
        if self._endpoint is not None:
            return self._endpoint
        try:
            device = AudioUtilities.GetSpeakers()
            if hasattr(device, "Activate"):
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            elif hasattr(device, "EndpointVolume"):
                self._endpoint = device.EndpointVolume
            else:
                raise AttributeError("Unsupported pycaw AudioDevice interface")
            return self._endpoint
        except Exception:
            LOGGER.exception("Unable to open default audio endpoint for ducking")
            self._available = False
            return None
