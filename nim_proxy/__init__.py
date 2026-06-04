"""scubamount-nim-proxy: OpenAI-compatible bridge to NVIDIA NIM with per-model override injection."""

from .app import app, _apply_override
from .config import (
    NIM_BASE,
    NIM_API_KEY,
    LISTEN_HOST,
    LISTEN_PORT,
    OVERRIDES_PATH,
    load_overrides,
)

__all__ = [
    "app",
    "_apply_override",
    "NIM_BASE",
    "NIM_API_KEY",
    "LISTEN_HOST",
    "LISTEN_PORT",
    "OVERRIDES_PATH",
    "load_overrides",
]
