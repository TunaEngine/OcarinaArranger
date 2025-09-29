"""Business logic for building preview data independent of Tk widgets."""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Sequence, Tuple

from ocarina_tools import (
    detect_tempo_bpm,
    favor_lower_register,
    get_note_events,
    get_time_signature,
    load_score,
    transform_to_ocarina,
)

from .settings import TransformSettings

Event = Tuple[int, int, int, int]


@dataclass(frozen=True)
class PreviewData:
    original_events: Sequence[Event]
    arranged_events: Sequence[Event]
    pulses_per_quarter: int
    beats: int
    beat_type: int
    original_range: Tuple[int, int]
    arranged_range: Tuple[int, int]
    tempo_bpm: int


def build_preview_data(input_path: str, settings: TransformSettings) -> PreviewData:
    _, root_original = load_score(input_path)
    events_original, pulses_per_quarter = get_note_events(root_original)
    beats, beat_type = get_time_signature(root_original)
    tempo_bpm = detect_tempo_bpm(root_original)

    # ``transform_to_ocarina`` mutates the supplied score. Deep copy the
    # original tree so we avoid re-loading the file from disk when only the
    # preview settings change (e.g. manual transpose).
    root_arranged = copy.deepcopy(root_original)
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
    )

    if settings.favor_lower:
        favor_lower_register(root_arranged, range_min=settings.range_min)

    events_arranged, _ = get_note_events(root_arranged)
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
    )


def _calculate_range(events: Sequence[Event], default_range: Tuple[int, int]) -> Tuple[int, int]:
    if not events:
        return default_range
    lowest = min(midi for (_, _, midi, _program) in events)
    highest = max(midi for (_, _, midi, _program) in events)
    return lowest, highest


def _trim_leading_silence(events: Sequence[Event]) -> list[Event]:
    if not events:
        return list(events)

    earliest_onset = min(onset for onset, _duration, _midi, _program in events)
    if earliest_onset <= 0:
        return list(events)

    offset_events = [
        (onset - earliest_onset, duration, midi, program)
        for onset, duration, midi, program in events
    ]
    return offset_events
