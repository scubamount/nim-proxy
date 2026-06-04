"""Centralized config from env vars. Pure stdlib."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

NIM_BASE: str = "https://integrate.api.nvidia.com/v1"
NIM_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")
LISTEN_HOST: str = os.environ.get("NIM_PROXY_HOST", "127.0.0.1")
LISTEN_PORT: int = int(os.environ.get("NIM_PROXY_PORT", "8001"))
OVERRIDES_PATH: Optional[Path] = (
    Path(p) if (p := os.environ.get("NIM_PROXY_OVERRIDES")) else None
)


def load_overrides() -> dict:
    """Return override dict. JSON file at $NIM_PROXY_OVERRIDES if set, else built-in."""
    from . import overrides as _overrides

    if OVERRIDES_PATH and OVERRIDES_PATH.is_file():
        with OVERRIDES_PATH.open() as f:
            return json.load(f)
    return dict(_overrides.MODEL_OVERRIDES)
