from __future__ import annotations

from domain.arrangement.api import (
    ArrangementResult,
    _difficulty_score,
    arrange_span,
    summarize_difficulty,
)
from domain.arrangement.config import FeatureFlags, GraceSettings
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.salvage import default_salvage_cascade
from domain.arrangement.soft_key import InstrumentRange, InstrumentWindwayRange


def _make_span(midi_values: list[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 480, duration=480, midi=midi)
        for index, midi in enumerate(midi_values)
    ]
    return PhraseSpan(tuple(notes))


def _make_fast_windway_span(midi_values: list[int]) -> PhraseSpan:
    sixteenth = 120
    notes = [
        PhraseNote(onset=index * sixteenth, duration=sixteenth, midi=midi)
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


def test_fast_windway_weight_prioritizes_low_switch_transposition() -> None:
    instrument = InstrumentWindwayRange(
        min_midi=60,
        max_midi=80,
        windway_ids=("primary", "secondary", "tertiary"),
        windway_map={
            66: (0,),
            67: (0,),
            68: (0,),
            69: (0,),
            70: (1,),
            71: (1,),
            72: (1,),
            73: (2,),
        },
    )
    span = _make_fast_windway_span([68, 71, 68, 71])

    muted_weight = GraceSettings(fast_windway_switch_weight=0.0)
    heavy_weight = GraceSettings(fast_windway_switch_weight=3.0)

    muted_result = arrange_span(span, instrument=instrument, grace_settings=muted_weight)
    muted_summary = summarize_difficulty(
        muted_result.span, instrument, grace_settings=muted_weight
    )

    assert muted_result.transposition == 0
    assert muted_summary.fast_windway_switch_exposure > 0.0

    heavy_result = arrange_span(span, instrument=instrument, grace_settings=heavy_weight)
    heavy_summary = summarize_difficulty(
        heavy_result.span, instrument, grace_settings=heavy_weight
    )

    assert heavy_result.transposition == -2
    assert heavy_summary.fast_windway_switch_exposure == 0.0


def test_fast_windway_weight_overrides_range_bias_when_exposure_high() -> None:
    instrument = InstrumentWindwayRange(
        min_midi=62,
        max_midi=69,
        windway_ids=("primary", "secondary"),
        windway_map={
            62: (0,),
            63: (0,),
            64: (0,),
            65: (0,),
            66: (0,),
            67: (1,),
            68: (1,),
            69: (1,),
        },
    )
    notes = [
        PhraseNote(onset=0, duration=120, midi=64),
        PhraseNote(onset=120, duration=120, midi=69),
        PhraseNote(onset=240, duration=120, midi=64),
    ]
    span = PhraseSpan(tuple(notes), pulses_per_quarter=480)

    muted_settings = GraceSettings(fast_windway_switch_weight=0.0)
    muted_result = arrange_span(span, instrument=instrument, grace_settings=muted_settings)
    muted_summary = summarize_difficulty(muted_result.span, instrument, grace_settings=muted_settings)

    assert muted_result.transposition == 0
    assert muted_summary.fast_windway_switch_exposure > 0.0

    heavy_settings = GraceSettings(fast_windway_switch_weight=3.0)
    heavy_result = arrange_span(span, instrument=instrument, grace_settings=heavy_settings)
    heavy_summary = summarize_difficulty(heavy_result.span, instrument, grace_settings=heavy_settings)

    assert heavy_result.transposition != muted_result.transposition
    assert heavy_summary.fast_windway_switch_exposure < muted_summary.fast_windway_switch_exposure
