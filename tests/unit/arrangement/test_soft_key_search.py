from __future__ import annotations

from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange, soft_key_search


def test_soft_key_search_prioritizes_transpositions_that_fit_range() -> None:
    notes = (
        PhraseNote(onset=0, duration=480, midi=74),
        PhraseNote(onset=480, duration=480, midi=76),
        PhraseNote(onset=960, duration=480, midi=71),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)
    instrument = InstrumentRange(min_midi=60, max_midi=72, comfort_center=72)

    fits = soft_key_search(span, instrument=instrument, top_k=2)

    assert [fit.transposition for fit in fits] == [-4, -5]
    assert fits[0].in_range_ratio == 1.0
    assert fits[0].time_above_high == 0.0
    assert fits[0].score > fits[1].score


def test_soft_key_search_limits_results_to_top_k() -> None:
    notes = (
        PhraseNote(onset=0, duration=240, midi=65),
        PhraseNote(onset=240, duration=240, midi=67),
        PhraseNote(onset=480, duration=240, midi=69),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)
    instrument = InstrumentRange(min_midi=60, max_midi=72, comfort_center=67)

    fits = soft_key_search(span, instrument=instrument, top_k=1)

    assert len(fits) == 1
    assert fits[0].transposition == 0
