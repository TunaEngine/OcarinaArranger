"""Data structures and helpers for arranged notes in the PDF exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ocarina_tools import midi_to_name as pitch_midi_to_name

from ..constants import midi_to_name as gui_midi_to_name
from ..constants import natural_of
from ..fingering import InstrumentSpec
from .types import NoteEvent


@dataclass(frozen=True)
class ArrangedNote:
    index: int
    midi: int
    note_name: str
    pattern_text: str
    pattern_state: Optional[Tuple[int, ...]]


@dataclass(frozen=True)
class PatternData:
    pattern: Tuple[int, ...]
    pattern_text: str
    note_names: Tuple[str, ...] = field(default_factory=tuple)
    lowest_midi: Optional[int] = None


def collect_arranged_notes(
    events: Sequence[NoteEvent],
    instrument: InstrumentSpec,
    prefer_flats: bool,
) -> List[ArrangedNote]:
    """Translate note events into arranged fingering metadata."""

    notes: List[ArrangedNote] = []
    for index, (_onset, _duration, midi, _program) in enumerate(events, start=1):
        note_name = pitch_midi_to_name(midi, flats=prefer_flats)
        pattern_text, pattern_state = _resolve_pattern(instrument, note_name, midi)
        notes.append(
            ArrangedNote(
                index=index,
                midi=midi,
                note_name=note_name,
                pattern_text=pattern_text,
                pattern_state=pattern_state,
            )
        )
    return notes


def group_patterns(
    notes: Sequence[ArrangedNote],
) -> Tuple[List[PatternData], List[str]]:
    """Collapse repeated patterns and highlight missing fingerings."""

    grouped: Dict[Tuple[int, ...], List[str]] = {}
    pattern_texts: Dict[Tuple[int, ...], str] = {}
    pattern_midis: Dict[Tuple[int, ...], List[int]] = {}
    missing: List[str] = []

    for note in notes:
        if note.pattern_state is None:
            missing.append(note.note_name)
            continue
        grouped.setdefault(note.pattern_state, []).append(note.note_name)
        pattern_texts.setdefault(note.pattern_state, note.pattern_text)
        pattern_midis.setdefault(note.pattern_state, []).append(note.midi)

    patterns: List[PatternData] = []
    for pattern, note_names in grouped.items():
        unique_names = tuple(dict.fromkeys(note_names))
        midi_values = pattern_midis.get(pattern, [])
        lowest_midi = min(midi_values) if midi_values else None
        patterns.append(
            PatternData(
                pattern=pattern,
                pattern_text=pattern_texts.get(pattern, ""),
                note_names=unique_names,
                lowest_midi=lowest_midi,
            )
        )

    patterns.sort(
        key=lambda entry: (
            entry.lowest_midi if entry.lowest_midi is not None else float("inf"),
            entry.note_names,
            entry.pattern_text,
        )
    )
    missing_sorted = sorted(dict.fromkeys(missing))
    return patterns, missing_sorted


def _resolve_pattern(
    instrument: InstrumentSpec, note_name: str, midi: int
) -> Tuple[str, Optional[Tuple[int, ...]]]:
    mapping = instrument.note_map.get(note_name)
    fallback_names: List[str] = []

    canonical = gui_midi_to_name(midi)
    natural = natural_of(midi)
    for candidate in (canonical, natural):
        if candidate and candidate not in fallback_names:
            fallback_names.append(candidate)

    selected = mapping
    if selected is None:
        for fallback in fallback_names:
            if fallback and fallback != note_name:
                candidate = instrument.note_map.get(fallback)
                if candidate is not None:
                    selected = candidate
                    break

    if selected is None:
        return "N/A", None

    holes = instrument.holes
    sequence = list(selected)
    if len(sequence) < len(holes):
        sequence.extend([0] * (len(holes) - len(sequence)))
    elif len(sequence) > len(holes):
        sequence = sequence[: len(holes)]

    symbol_map = {0: "O", 1: "/", 2: "X"}
    normalized = tuple(max(0, min(2, int(value))) for value in sequence)
    pattern_text = "".join(symbol_map.get(value, "?") for value in normalized)
    return pattern_text, normalized


__all__ = [
    "ArrangedNote",
    "PatternData",
    "collect_arranged_notes",
    "group_patterns",
]
