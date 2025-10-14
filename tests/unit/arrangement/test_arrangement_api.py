from __future__ import annotations

from domain.arrangement.api import (
    ArrangementResult,
    _difficulty_score,
    arrange_span,
    summarize_difficulty,
)
from domain.arrangement.config import FeatureFlags
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.salvage import default_salvage_cascade
from domain.arrangement.soft_key import InstrumentRange


def _make_span(midi_values: list[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 480, duration=480, midi=midi)
        for index, midi in enumerate(midi_values)
    ]
    return PhraseSpan(tuple(notes))


def test_arrange_span_returns_baseline_when_dp_flag_disabled() -> None:
    span = _make_span([84, 86])
    instrument = InstrumentRange(min_midi=60, max_midi=88)

    result = arrange_span(span, instrument=instrument, flags=FeatureFlags(dp_slack=False))

    assert isinstance(result, ArrangementResult)
    assert result.folding is None
    assert result.salvage is None
    assert -10 <= result.transposition <= 10
    final_midis = [note.midi for note in result.span.notes]
    assert all(instrument.min_midi <= midi <= instrument.max_midi for midi in final_midis)


def test_arrange_span_runs_dp_when_flag_enabled() -> None:
    span = _make_span([96])  # Above the instrument range.
    instrument = InstrumentRange(min_midi=60, max_midi=86)

    result = arrange_span(span, instrument=instrument, flags=FeatureFlags(dp_slack=True))

    assert result.folding is not None
    # DP should fold the note down an octave so it falls within range.
    assert result.span.notes[0].midi != span.notes[0].midi
    assert instrument.min_midi <= result.span.notes[0].midi <= instrument.max_midi
    assert result.salvage is None
    assert -10 <= result.transposition <= 10


def test_arrange_span_dp_preserves_neutral_passages() -> None:
    span = _make_span([70, 72])
    instrument = InstrumentRange(min_midi=60, max_midi=80)

    baseline = arrange_span(span, instrument=instrument, flags=FeatureFlags(dp_slack=False))
    with_dp = arrange_span(span, instrument=instrument, flags=FeatureFlags(dp_slack=True))

    assert baseline.span == with_dp.span
    assert baseline.transposition == 0
    assert with_dp.transposition == 0
    assert with_dp.folding is not None
    assert with_dp.salvage is None


def test_arrange_span_runs_salvage_when_cascade_provided() -> None:
    # Create a span where the first note is an ornamental out-of-range pitch.
    notes = [
        PhraseNote(
            onset=0,
            duration=240,
            midi=92,
        ).with_tags({"ornamental", "octave-shiftable"}),
        PhraseNote(
            onset=240,
            duration=720,
            midi=72,
        ).with_tags({"pivotal"}),
    ]
    span = PhraseSpan(tuple(notes))
    instrument = InstrumentRange(min_midi=60, max_midi=80)

    cascade = default_salvage_cascade(threshold=0.2)
    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=cascade,
    )

    assert result.salvage is not None
    assert "rhythm-simplify" in result.salvage.applied_steps or "OCTAVE_DOWN_LOCAL" in result.salvage.applied_steps
    assert result.salvage.difficulty <= result.salvage.starting_difficulty
    assert len(result.span.notes) <= len(span.notes)
    assert -10 <= result.transposition <= 10


def test_arrange_span_transposes_to_reduce_difficulty() -> None:
    span = _make_span([88, 90])
    instrument = InstrumentRange(min_midi=60, max_midi=80)

    result = arrange_span(span, instrument=instrument, flags=FeatureFlags(dp_slack=False))

    assert result.transposition < 0
    adjusted_midis = [note.midi for note in result.span.notes]
    assert max(adjusted_midis) <= instrument.max_midi


def test_arrange_span_clamps_out_of_range_long_note() -> None:
    pulses = 480
    note = PhraseNote(
        onset=0,
        duration=pulses * 4,
        midi=90,
    ).with_tags({"octave-shiftable"})
    span = PhraseSpan((note,), pulses_per_quarter=pulses)
    instrument = InstrumentRange(min_midi=60, max_midi=72)

    cascade = default_salvage_cascade(threshold=0.6)
    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=cascade,
    )

    assert result.salvage is not None
    assert all(
        instrument.min_midi <= note.midi <= instrument.max_midi
        for note in result.span.notes
    )
    assert "range-clamp" in result.salvage.applied_steps
    assert any(
        event.reason_code == "range-clamp" for event in result.salvage.explanations
    )


def test_difficulty_penalizes_large_leaps() -> None:
    instrument = InstrumentRange(min_midi=60, max_midi=84)
    smooth_span = _make_span([64, 65, 67, 69])
    leaping_span = _make_span([64, 81, 62, 80])

    smooth_summary = summarize_difficulty(smooth_span, instrument)
    leaping_summary = summarize_difficulty(leaping_span, instrument)

    assert leaping_summary.leap_exposure > smooth_summary.leap_exposure
    assert _difficulty_score(leaping_summary) > _difficulty_score(smooth_summary)
