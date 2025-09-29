"""Helper functions for instrument layout note mappings."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from ocarina_tools.pitch import parse_note_name

from .models import InstrumentLayoutState


def note_sort_key(name: str) -> Tuple[float, str]:
    """Return a sortable key that prefers musical ordering."""

    try:
        midi = float(parse_note_name(name))
    except ValueError:
        return (float("inf"), name)
    return (midi, name)


def sort_note_order(state: InstrumentLayoutState) -> None:
    """Sort the state's note order using musical pitch when possible."""

    combined = list(dict.fromkeys(list(state.note_order) + list(state.note_map.keys())))
    combined.sort(key=note_sort_key)
    state.note_order = combined


def normalize_pattern(pattern: Iterable[int], hole_count: int) -> List[int]:
    """Clamp and pad a note pattern to match the hole count."""

    normalized: List[int] = []
    for value in pattern:
        if isinstance(value, bool):
            number = 2 if value else 0
        else:
            number = int(value)
        if number < 0:
            number = 0
        elif number > 2:
            number = 2
        normalized.append(number)

    if len(normalized) > hole_count:
        normalized = normalized[:hole_count]
    elif len(normalized) < hole_count:
        normalized.extend([0] * (hole_count - len(normalized)))
    return normalized


def sync_note_map_length(
    state: InstrumentLayoutState,
    *,
    removed_index: Optional[int] = None,
) -> None:
    """Ensure each stored pattern matches the current hole count."""

    hole_count = len(state.holes)
    for note, pattern in state.note_map.items():
        values = list(pattern)
        if removed_index is not None and removed_index < len(values):
            del values[removed_index]
        adjusted = normalize_pattern(values, hole_count)
        state.note_map[note] = adjusted


def ensure_candidate_name(state: InstrumentLayoutState, note: str) -> None:
    """Add the note to the candidate set if missing."""

    normalized = str(note).strip()
    if not normalized:
        return
    if normalized not in state.candidate_notes:
        state.candidate_notes.append(normalized)


__all__ = [
    "ensure_candidate_name",
    "normalize_pattern",
    "note_sort_key",
    "sort_note_order",
    "sync_note_map_length",
]
