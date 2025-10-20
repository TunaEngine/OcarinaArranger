"""Business logic for building preview data independent of Tk widgets."""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Sequence, Tuple

from ocarina_tools import (
    NoteEvent,
    TempoChange,
    detect_tempo_bpm,
    favor_lower_register,
    filter_parts,
    get_note_events,
    get_tempo_changes,
    get_time_signature,
    load_score,
    transform_to_ocarina,
)
from .settings import TransformSettings

@dataclass(frozen=True)
class PreviewData:
    original_events: Sequence[NoteEvent]
    arranged_events: Sequence[NoteEvent]
    pulses_per_quarter: int
    beats: int
    beat_type: int
    original_range: Tuple[int, int]
    arranged_range: Tuple[int, int]
    tempo_bpm: int
    tempo_changes: Sequence[TempoChange]


def build_preview_data(input_path: str, settings: TransformSettings) -> PreviewData:
    _, root_original = load_score(input_path)
    root_filtered = copy.deepcopy(root_original)
    if settings.selected_part_ids:
        filter_parts(root_filtered, settings.selected_part_ids)

    importer_grace = settings.grace_settings.to_importer()

    events_original, pulses_per_quarter = get_note_events(
        root_filtered, grace_settings=importer_grace
    )
    beats, beat_type = get_time_signature(root_filtered)
    tempo_bpm = detect_tempo_bpm(root_filtered)
    tempo_changes = get_tempo_changes(root_filtered, default_bpm=tempo_bpm)

    # ``transform_to_ocarina`` mutates the supplied score. Deep copy the
    # original tree so we avoid re-loading the file from disk when only the
    # preview settings change (e.g. manual transpose).
    root_arranged = copy.deepcopy(root_filtered)
    tree_arranged = ET.ElementTree(root_arranged)
    transform_to_ocarina(
        tree_arranged,
        root_arranged,
        prefer_mode=settings.prefer_mode,
        range_min=settings.range_min,
        range_max=settings.range_max,
        prefer_flats=settings.prefer_flats,
        collapse_chords=settings.collapse_chords,
        transpose_offset=settings.transpose_offset,
        selected_part_ids=settings.selected_part_ids,
    )

    if settings.favor_lower:
        favor_lower_register(root_arranged, range_min=settings.range_min)

    events_arranged, _ = get_note_events(
        root_arranged, grace_settings=importer_grace
    )
    events_arranged = _trim_leading_silence(events_arranged)

    original_range = _calculate_range(events_original, default_range=(48, 84))
    arranged_range = _calculate_range(events_arranged, default_range=(69, 89))

    return PreviewData(
        original_events=events_original,
        arranged_events=events_arranged,
        pulses_per_quarter=pulses_per_quarter,
        beats=beats,
        beat_type=beat_type,
        original_range=original_range,
        arranged_range=arranged_range,
        tempo_bpm=tempo_bpm,
        tempo_changes=tuple(tempo_changes),
    )


def _calculate_range(events: Sequence[NoteEvent], default_range: Tuple[int, int]) -> Tuple[int, int]:
    if not events:
        return default_range
    lowest = min(event.midi for event in events)
    highest = max(event.midi for event in events)
    return lowest, highest


def _trim_leading_silence(events: Sequence[NoteEvent]) -> list[NoteEvent]:
    if not events:
        return list(events)

    earliest_onset = min(event.onset for event in events)
    if earliest_onset <= 0:
        return list(events)

    return [event.shift(-earliest_onset) for event in events]
