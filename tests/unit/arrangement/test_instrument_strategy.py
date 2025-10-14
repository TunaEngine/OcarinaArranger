from domain.arrangement.api import arrange
from domain.arrangement.config import (
    clear_instrument_registry,
    register_instrument_range,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def setup_function() -> None:
    clear_instrument_registry()


def _make_span(midi_values: list[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 480, duration=480, midi=midi)
        for index, midi in enumerate(midi_values)
    ]
    return PhraseSpan(tuple(notes))


def test_arrange_current_ignores_starred() -> None:
    span = _make_span([72, 74, 76])
    register_instrument_range("primary", InstrumentRange(min_midi=60, max_midi=84))

    result = arrange(
        span,
        instrument_id="primary",
        starred_ids=("secondary",),
        strategy="current",
    )

    assert result.strategy == "current"
    assert [candidate.instrument_id for candidate in result.comparisons] == ["primary"]


def test_arrange_starred_best_ranks_and_explains() -> None:
    span = _make_span([84, 72, 60])
    register_instrument_range("current", InstrumentRange(min_midi=60, max_midi=84, comfort_center=72))
    register_instrument_range("star_a", InstrumentRange(min_midi=55, max_midi=79, comfort_center=67))
    register_instrument_range("star_b", InstrumentRange(min_midi=62, max_midi=86, comfort_center=74))

    result = arrange(
        span,
        instrument_id="current",
        starred_ids=("star_a", "star_b"),
        strategy="starred-best",
    )

    assert result.strategy == "starred-best"
    ordered_ids = [candidate.instrument_id for candidate in result.comparisons]
    assert ordered_ids == ["star_a", "current", "star_b"]

    chosen = result.chosen
    assert chosen.instrument_id == "star_a"
    # Star A should minimise hard+very-hard exposure.
    assert chosen.difficulty.hard_and_very_hard <= result.comparisons[1].difficulty.hard_and_very_hard
    assert result.comparisons[1].difficulty.medium <= result.comparisons[2].difficulty.medium

