"""Pitch utility helpers for fingering specifications."""

from __future__ import annotations

from typing import Optional

from ocarina_tools.pitch import parse_note_name

__all__ = ["parse_note_name_safe"]


def parse_note_name_safe(note_name: str) -> Optional[int]:
    """Best-effort conversion of ``note_name`` to a MIDI integer."""

    try:
        return int(parse_note_name(note_name))
    except Exception:
        return None
