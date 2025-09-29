"""Optional audio backend dependencies."""
from __future__ import annotations

try:  # pragma: no cover - optional dependency
    import simpleaudio  # type: ignore
except Exception:  # pragma: no cover - fallback when audio backend missing
    simpleaudio = None  # type: ignore

try:  # pragma: no cover - optional dependency on Windows
    import winsound  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - other platforms
    winsound = None  # type: ignore

__all__ = ["simpleaudio", "winsound"]
