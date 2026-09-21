"""Small, dependency-free platform boundary for desktop-only client features."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapabilities:
    is_android: bool
    desktop_camera: bool
    client_liveness: bool
    image_picker: bool


def current_platform(platform_name: object | None = None) -> PlatformCapabilities:
    """Return conservative capabilities without importing native CV packages."""
    value = str(platform_name or os.getenv("FLET_PLATFORM") or sys.platform).casefold()
    android = "android" in value
    return PlatformCapabilities(
        is_android=android,
        desktop_camera=not android,
        client_liveness=not android,
        image_picker=True,
    )
