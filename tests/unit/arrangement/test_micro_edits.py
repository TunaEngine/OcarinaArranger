from __future__ import annotations

import pytest

from domain.arrangement.micro_edits import (
    drop_ornamental_eighth,
    lengthen_pivotal_note,
    shift_short_phrase_octave,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from shared.ottava import OttavaShift


@pytest.fixture
def base_span() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=480, midi=64),
        PhraseNote(onset=480, duration=240, midi=66, tags=frozenset({"ornamental"})),
        PhraseNote(onset=720, duration=240, midi=67, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=960, duration=240, midi=69, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=1200, duration=480, midi=71, tags=frozenset({"pivotal"})),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_drop_ornamental_eighth_extends_previous_note(base_span: PhraseSpan) -> None:
    span = drop_ornamental_eighth(base_span)
    assert len(span.notes) == 4
    first, second, third, fourth = span.notes
    assert first.duration == 720
    assert second.onset == 720
    assert third.tags == frozenset({"octave-shiftable"})
    assert fourth.tags == frozenset({"pivotal"})


def test_lengthen_pivotal_note_consumes_available_slack() -> None:
    notes = (
        PhraseNote(onset=0, duration=480, midi=64),
        PhraseNote(onset=480, duration=480, midi=66),
        PhraseNote(onset=960, duration=240, midi=67, tags=frozenset({"pivotal"})),
        PhraseNote(onset=1680, duration=240, midi=69),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)
    extended = lengthen_pivotal_note(span)
    assert [note.duration for note in extended.notes] == [480, 480, 720, 240]


def test_shift_short_phrase_octave_marks_micro_edit(base_span: PhraseSpan) -> None:
    span = drop_ornamental_eighth(base_span)
    shifted = shift_short_phrase_octave(span, direction="down")
    altered = [note for note in shifted.notes if note.tags == frozenset({"octave-shiftable"})]
    assert altered
    for note in altered:
        assert note.midi in {55, 57}
        assert note.ottava_shifts and note.ottava_shifts[-1] == OttavaShift(
            source="micro-edit",
            direction="down",
            size=8,
            number=None,
        )


def test_shift_short_phrase_octave_rejects_invalid_direction(base_span: PhraseSpan) -> None:
    with pytest.raises(ValueError):
        shift_short_phrase_octave(base_span, direction="sideways")
