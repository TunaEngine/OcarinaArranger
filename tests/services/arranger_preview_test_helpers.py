"""Shared helpers for arranger preview service tests."""

from __future__ import annotations

from typing import Sequence

from ocarina_gui.fingering import InstrumentSpec
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent


def make_spec(
    instrument_id: str,
    *,
    candidate_min: str,
    candidate_max: str,
    preferred_min: str,
    preferred_max: str,
) -> InstrumentSpec:
    """Construct a minimal instrument spec for arranger preview tests."""

    return InstrumentSpec.from_dict(
        {
            "id": instrument_id,
            "name": instrument_id,
            "title": instrument_id,
            "canvas": {"width": 120, "height": 120},
            "style": {
                "background_color": "#ffffff",
                "outline_color": "#000000",
                "outline_width": 2.0,
                "outline_smooth": True,
                "outline_spline_steps": 16,
                "hole_outline_color": "#000000",
                "covered_fill_color": "#000000",
            },
            "holes": [],
            "windways": [],
            "note_order": ["C4"],
            "note_map": {"C4": []},
            "preferred_range": {"min": preferred_min, "max": preferred_max},
            "candidate_range": {"min": candidate_min, "max": candidate_max},
        }
    )


def preview_fixture(events: Sequence[NoteEvent]) -> PreviewData:
    """Build a simple :class:`PreviewData` instance for arranger preview tests."""

    return PreviewData(
        original_events=tuple(events),
        arranged_events=tuple(events),
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 88),
        arranged_range=(60, 88),
        tempo_bpm=120,
        tempo_changes=(),
    )

