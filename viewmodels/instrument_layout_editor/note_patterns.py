"""Helper functions for instrument layout note mappings."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name, parse_note_name

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


def normalize_pattern(
    pattern: Iterable[int], hole_count: int, windway_count: int
) -> List[int]:
    """Clamp and pad a note pattern to match the hole and windway counts."""

    total = hole_count + windway_count
    normalized: List[int] = []
    for value in pattern:
        if len(normalized) >= total:
            break
        if isinstance(value, bool):
            number = 2 if value else 0
        else:
            number = int(value)
        position = len(normalized)
        if position < hole_count:
            if number < 0:
                number = 0
            elif number > 2:
                number = 2
        else:
            number = 0 if number <= 0 else 2
        normalized.append(number)

    if len(normalized) < total:
        normalized.extend([0] * (total - len(normalized)))
    return normalized


def sync_note_map_length(
    state: InstrumentLayoutState,
    *,
    removed_offset: Optional[int] = None,
    previous_hole_count: Optional[int] = None,
    previous_windway_count: Optional[int] = None,
) -> None:
    """Ensure each stored pattern matches the current hole count."""

    hole_count = len(state.holes)
    windway_count = len(state.windways)
    prev_holes = previous_hole_count if previous_hole_count is not None else hole_count
    prev_windways = (
        previous_windway_count if previous_windway_count is not None else windway_count
    )
    prev_total = prev_holes + prev_windways
    for note, pattern in state.note_map.items():
        values = list(pattern)
        if prev_total:
            if len(values) < prev_total:
                values.extend([0] * (prev_total - len(values)))
            elif len(values) > prev_total:
                values = values[:prev_total]

        hole_values = list(values[:prev_holes])
        windway_values = list(values[prev_holes: prev_holes + prev_windways])

        if removed_offset is not None:
            if removed_offset < prev_holes:
                if removed_offset < len(hole_values):
                    del hole_values[removed_offset]
            else:
                adjusted_index = removed_offset - prev_holes
                if adjusted_index < len(windway_values):
                    del windway_values[adjusted_index]

        if len(hole_values) > hole_count:
            hole_values = hole_values[:hole_count]
        elif len(hole_values) < hole_count:
            hole_values.extend([0] * (hole_count - len(hole_values)))

        if len(windway_values) > windway_count:
            windway_values = windway_values[:windway_count]
        elif len(windway_values) < windway_count:
            windway_values.extend([0] * (windway_count - len(windway_values)))

        normalized_holes = normalize_pattern(hole_values, hole_count, 0)
        normalized_windways = normalize_pattern(windway_values, 0, windway_count)
        state.note_map[note] = normalized_holes + normalized_windways


def ensure_candidate_name(state: InstrumentLayoutState, note: str) -> None:
    """Add the note to the candidate set if missing."""

    normalized = str(note).strip()
    if not normalized:
        return
    if normalized not in state.candidate_notes:
        state.candidate_notes.append(normalized)

    try:
        midi = parse_note_name(normalized)
    except ValueError:
        return

    changed = False
    try:
        current_min = parse_note_name(state.candidate_range_min)
    except ValueError:
        current_min = None
    try:
        current_max = parse_note_name(state.candidate_range_max)
    except ValueError:
        current_max = None

    if current_min is None or midi < current_min:
        state.candidate_range_min = pitch_midi_to_name(midi, flats=False)
        current_min = midi
        changed = True
    if current_max is None or midi > current_max:
        state.candidate_range_max = pitch_midi_to_name(midi, flats=False)
        changed = True

    if changed:
        state.has_explicit_candidate_range = True
        state.dirty = True


__all__ = [
    "ensure_candidate_name",
    "normalize_pattern",
    "note_sort_key",
    "sort_note_order",
    "sync_note_map_length",
]
