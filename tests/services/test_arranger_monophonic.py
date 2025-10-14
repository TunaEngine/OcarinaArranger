"""Tests covering the arranger monophonic helper."""

from __future__ import annotations

from ocarina_tools.events import NoteEvent

from services.arranger_monophonic import ensure_monophonic


def test_ensure_monophonic_prefers_highest_on_simultaneous() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=0, duration=240, midi=72, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=240, midi=72, program=0),
    )


def test_ensure_monophonic_discards_lower_priority_overlap() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=240, duration=480, midi=60, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
    )


def test_ensure_monophonic_trims_when_later_note_is_preferred() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=240, duration=360, midi=74, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=240, midi=60, program=0),
        NoteEvent(onset=240, duration=360, midi=74, program=0),
    )
