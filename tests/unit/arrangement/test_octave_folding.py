from __future__ import annotations

import pytest

from domain.arrangement.folding import (
    FoldingResult,
    FoldingSettings,
    fold_octaves_with_slack,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


@pytest.fixture
def alto_range() -> InstrumentRange:
    return InstrumentRange(min_midi=60, max_midi=72, comfort_center=66)


def _make_span(midis: list[int]) -> PhraseSpan:
    notes = tuple(
        PhraseNote(onset=index * 480, duration=480, midi=midi)
        for index, midi in enumerate(midis)
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_fold_octaves_shifts_down_high_notes(alto_range: InstrumentRange) -> None:
    span = _make_span([84, 83])

    result = fold_octaves_with_slack(span, alto_range)

    assert isinstance(result, FoldingResult)
    assert [note.midi for note in result.span.notes] == [72, 71]
    assert result.steps[0].shift == -1
    assert result.steps[1].shift == -1
    assert result.steps[0].substituted is False
    assert result.steps[0].register_penalty == pytest.approx(0.0)
    assert result.total_cost < 10.0
    assert result.span.notes[0].ottava_shifts
    assert result.span.notes[0].ottava_shifts[0].direction == "down"


def test_fold_octaves_prefers_neighbor_substitution_when_cheaper(alto_range: InstrumentRange) -> None:
    span = _make_span([73])
    settings = FoldingSettings(substitution_penalty=0.5, shift_penalty=2.0)

    result = fold_octaves_with_slack(span, alto_range, settings=settings)

    assert [note.midi for note in result.span.notes] == [72]
    assert result.steps[0].substituted is True
    assert result.steps[0].shift == 0
    assert result.steps[0].substitution_penalty > 0.0
    assert result.total_cost < 5.0


def test_fold_octaves_allows_out_of_range_with_finite_penalty(alto_range: InstrumentRange) -> None:
    span = _make_span([95])
    settings = FoldingSettings(out_of_range_weight=1.5)

    result = fold_octaves_with_slack(span, alto_range, settings=settings)

    assert result.span.notes[0].midi > alto_range.max_midi
    assert result.total_cost > 0.0
    assert result.steps[0].register_penalty > 0.0


def test_fold_octaves_discourages_large_leaps(alto_range: InstrumentRange) -> None:
    span = _make_span([60, 72])

    result = fold_octaves_with_slack(span, alto_range)

    assert [note.midi for note in result.span.notes] == [60, 60]
    assert result.steps[1].shift == -1
    assert result.steps[1].transition_penalty >= 0.0
