from __future__ import annotations

from ocarina_tools.events import NoteEvent

from domain.arrangement.importers import note_events_from_phrase, phrase_from_note_events


def test_phrase_from_note_events_propagates_grace_metadata() -> None:
    events = [
        NoteEvent(onset=0, duration=0, midi=60, program=0, is_grace=True, grace_type="acciaccatura"),
        NoteEvent(onset=60, duration=420, midi=62, program=0),
    ]

    span = phrase_from_note_events(events, 480)

    assert len(span.notes) == 2
    grace_note, anchor_note = span.notes

    assert grace_note.duration == 1
    assert "grace" in grace_note.tags
    assert "ornamental" in grace_note.tags
    assert "grace-type:acciaccatura" in grace_note.tags

    assert "grace" not in anchor_note.tags
    assert anchor_note.duration == 420

    round_trip = note_events_from_phrase(span, program=5)
    assert len(round_trip) == 2
    rt_grace, rt_anchor = round_trip
    assert rt_grace.is_grace
    assert rt_grace.grace_type == "acciaccatura"
    assert rt_grace.program == 5
    assert not rt_anchor.is_grace
