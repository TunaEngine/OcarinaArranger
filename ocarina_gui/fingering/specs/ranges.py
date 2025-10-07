"""Helpers for reasoning about instrument note ranges."""

from __future__ import annotations

from typing import List, Tuple

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name

from .instrument import InstrumentSpec
from .pitch import parse_note_name_safe

__all__ = ["collect_instrument_note_names", "preferred_note_window"]


def collect_instrument_note_names(instrument: InstrumentSpec) -> List[str]:
    """Return the instrument's configured note names in pitch order."""

    range_min = parse_note_name_safe(getattr(instrument, "candidate_range_min", ""))
    range_max = parse_note_name_safe(getattr(instrument, "candidate_range_max", ""))

    names: List[str] = []
    seen: set[str] = set()

    if range_min is not None and range_max is not None and range_min <= range_max:
        for midi in range(range_min, range_max + 1):
            name = pitch_midi_to_name(midi, flats=False)
            if name not in seen:
                names.append(name)
                seen.add(name)

    extra_sources = list(
        dict.fromkeys(
            list(getattr(instrument, "candidate_notes", ()))
            + list(instrument.note_order)
            + list(instrument.note_map.keys())
        )
    )
    for name in extra_sources:
        if name not in seen:
            names.append(name)
            seen.add(name)

    def _sort_key(note_name: str) -> tuple[float, int, str]:
        midi = parse_note_name_safe(note_name)
        if midi is None:
            return (float("inf"), 0, note_name)
        sharp_name = pitch_midi_to_name(midi, flats=False)
        preference = 0 if note_name == sharp_name else 1
        return (float(midi), preference, note_name)

    names.sort(key=_sort_key)
    return names


def preferred_note_window(instrument: InstrumentSpec) -> Tuple[str, str]:
    """Return a preferred note window for ``instrument``."""

    explicit_min = getattr(instrument, "preferred_range_min", "").strip()
    explicit_max = getattr(instrument, "preferred_range_max", "").strip()
    if explicit_min and explicit_max:
        return explicit_min, explicit_max

    ordered = collect_instrument_note_names(instrument)
    if not ordered:
        raise ValueError("Instrument must define at least one note.")

    midi_pairs: List[Tuple[int, str]] = []
    for name in ordered:
        midi = parse_note_name_safe(name)
        if midi is None:
            continue
        midi_pairs.append((midi, name))

    if not midi_pairs:
        return ordered[0], ordered[-1]

    midi_pairs.sort(key=lambda item: item[0])
    lowest_name = midi_pairs[0][1]
    highest_name = midi_pairs[-1][1]
    return lowest_name, highest_name
