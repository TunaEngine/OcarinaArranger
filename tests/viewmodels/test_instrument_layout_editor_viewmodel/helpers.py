"""Helpers for instrument layout editor view-model tests."""

from __future__ import annotations

from ocarina_tools.pitch import parse_note_name


__all__ = ["note_sort_key"]


def note_sort_key(name: str) -> tuple[float, str]:
    """Sort notes by pitch, falling back to lexicographic order."""

    try:
        return (float(parse_note_name(name)), name)
    except ValueError:
        return (float("inf"), name)
