from __future__ import annotations

from domain.arrangement.constraints import (
    AlternativeFingering,
    BreathSettings,
    SubholeConstraintSettings,
    SubholePairLimit,
    TempoContext,
    TessituraSettings,
    compute_tessitura_bias,
    enforce_subhole_and_speed,
    plan_breaths,
    should_keep_high_octave_duplicate,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan


def _make_span(notes: tuple[PhraseNote, ...], pulses_per_quarter: int = 480) -> PhraseSpan:
    return PhraseSpan(notes, pulses_per_quarter=pulses_per_quarter)


def test_enforce_subhole_and_speed_drops_ornament_when_pair_rate_exceeds_limit() -> None:
    notes = (
        PhraseNote(onset=0, duration=120, midi=74, tags=frozenset({"subhole"})),
        PhraseNote(onset=120, duration=120, midi=76, tags=frozenset({"ornamental"})),
        PhraseNote(onset=240, duration=120, midi=74, tags=frozenset({"subhole"})),
        PhraseNote(onset=360, duration=120, midi=72),
        PhraseNote(onset=480, duration=120, midi=76, tags=frozenset({"ornamental"})),
        PhraseNote(onset=600, duration=120, midi=74, tags=frozenset({"subhole"})),
    )
    span = _make_span(notes)

    tempo = TempoContext(bpm=120, pulses_per_quarter=480)
    settings = SubholeConstraintSettings(
        max_changes_per_second=5.5,
        max_subhole_changes_per_second=4.0,
        pair_limits={frozenset({74, 76}): SubholePairLimit(max_hz=3.0, ease=0.6)},
    )

    result = enforce_subhole_and_speed(span, tempo, settings)

    assert len(result.span.notes) < len(span.notes)
    assert result.metrics.changes_per_second <= settings.max_changes_per_second
    assert result.metrics.subhole_changes_per_second <= settings.max_subhole_changes_per_second
    assert "drop-ornamental" in result.edits_applied


def test_enforce_subhole_and_speed_suggests_alternate_fingering_when_no_grace() -> None:
    notes = (
        PhraseNote(onset=0, duration=120, midi=70),
        PhraseNote(onset=120, duration=120, midi=72),
        PhraseNote(onset=240, duration=120, midi=70),
        PhraseNote(onset=360, duration=120, midi=72),
    )
    span = _make_span(notes)

    tempo = TempoContext(bpm=140, pulses_per_quarter=480)
    settings = SubholeConstraintSettings(
        max_changes_per_second=6.0,
        max_subhole_changes_per_second=3.0,
        pair_limits={frozenset({70, 72}): SubholePairLimit(max_hz=2.0, ease=0.5)},
        alternate_fingerings={
            72: (AlternativeFingering(shape="alt-high-D", ease=0.4, intonation=0.2),)
        },
    )

    result = enforce_subhole_and_speed(span, tempo, settings)

    assert result.span == span
    assert result.edits_applied == ("alt-fingering:72:alt-high-D",)
    pair_rates = dict(result.metrics.pair_rates)
    assert frozenset({70, 72}) in pair_rates


def test_subhole_settings_allow_faster_instrument_caps() -> None:
    notes = (
        PhraseNote(onset=0, duration=60, midi=67, tags=frozenset({"subhole"})),
        PhraseNote(onset=60, duration=30, midi=68, tags=frozenset({"ornamental"})),
        PhraseNote(onset=90, duration=60, midi=69, tags=frozenset({"subhole"})),
        PhraseNote(onset=150, duration=60, midi=67, tags=frozenset({"subhole"})),
        PhraseNote(onset=210, duration=60, midi=69, tags=frozenset({"subhole"})),
    )
    span = _make_span(notes)

    tempo = TempoContext(bpm=110, pulses_per_quarter=480)
    relaxed = SubholeConstraintSettings(
        max_changes_per_second=15.0,
        max_subhole_changes_per_second=15.0,
        pair_limits={frozenset({67, 69}): SubholePairLimit(max_hz=12.0, ease=0.7)},
    )
    strict = SubholeConstraintSettings(
        max_changes_per_second=5.0,
        max_subhole_changes_per_second=3.0,
        pair_limits={frozenset({67, 69}): SubholePairLimit(max_hz=1.5, ease=0.3)},
    )

    relaxed_result = enforce_subhole_and_speed(span, tempo, relaxed)
    strict_result = enforce_subhole_and_speed(span, tempo, strict)

    assert relaxed_result.span.notes == span.notes
    assert relaxed_result.edits_applied == ()
    assert strict_result.edits_applied == ("drop-ornamental",)


def test_plan_breaths_inserts_break_for_high_register_run() -> None:
    notes = (
        PhraseNote(onset=0, duration=1440, midi=82),
        PhraseNote(onset=1440, duration=1440, midi=84, tags=frozenset({"breath-candidate"})),
        PhraseNote(onset=2880, duration=1440, midi=83),
    )
    span = _make_span(notes)

    tempo = TempoContext(bpm=100, pulses_per_quarter=480)
    settings = BreathSettings(
        base_limit_seconds=5.0,
        tempo_factor=0.0,
        register_factor=3.0,
        min_limit_seconds=2.5,
        max_limit_seconds=6.0,
        register_reference_midi=80,
    )

    plan = plan_breaths(span, tempo, settings)

    assert plan.breath_points == (1440,)
    assert plan.segment_durations[0] <= settings.limit_for(tempo.bpm, 84)


def test_plan_breaths_scales_with_tempo() -> None:
    notes = tuple(
        PhraseNote(onset=i * 480, duration=480, midi=76, tags=frozenset({"breath-candidate"}))
        for i in range(16)
    )
    span = _make_span(notes)

    slow = TempoContext(bpm=90, pulses_per_quarter=480)
    fast = TempoContext(bpm=160, pulses_per_quarter=480)
    settings = BreathSettings(
        base_limit_seconds=8.0,
        tempo_factor=0.045,
        register_factor=0.0,
        min_limit_seconds=0.8,
        max_limit_seconds=8.0,
        register_reference_midi=76,
    )

    slow_plan = plan_breaths(span, slow, settings)
    fast_plan = plan_breaths(span, fast, settings)

    assert len(fast_plan.breath_points) >= len(slow_plan.breath_points)
    assert all(
        duration <= settings.limit_for(fast.bpm, 76)
        for duration in fast_plan.segment_durations
    )


def test_plan_breaths_scales_with_register_height() -> None:
    low_notes = tuple(
        PhraseNote(onset=i * 960, duration=960, midi=68, tags=frozenset({"breath-candidate"}))
        for i in range(12)
    )
    high_notes = tuple(
        PhraseNote(onset=i * 960, duration=960, midi=90, tags=frozenset({"breath-candidate"}))
        for i in range(12)
    )

    slow_span = _make_span(low_notes)
    high_span = _make_span(high_notes)

    tempo = TempoContext(bpm=110, pulses_per_quarter=480)
    settings = BreathSettings(
        base_limit_seconds=6.5,
        tempo_factor=0.0,
        register_factor=2.5,
        min_limit_seconds=2.0,
        max_limit_seconds=7.0,
        register_reference_midi=74,
    )

    low_plan = plan_breaths(slow_span, tempo, settings)
    high_plan = plan_breaths(high_span, tempo, settings)

    assert len(high_plan.breath_points) >= len(low_plan.breath_points)
    assert all(
        duration <= settings.limit_for(tempo.bpm, 90)
        for duration in high_plan.segment_durations
    )


def test_tessitura_bias_penalizes_high_line() -> None:
    centered_notes = (
        PhraseNote(onset=0, duration=480, midi=69),
        PhraseNote(onset=480, duration=480, midi=70),
    )
    high_notes = (
        PhraseNote(onset=0, duration=480, midi=82),
        PhraseNote(onset=480, duration=480, midi=84),
    )

    settings = TessituraSettings(comfort_center=69, tolerance=3.0, weight=0.05)

    centered_bias = compute_tessitura_bias(_make_span(centered_notes), settings)
    high_bias = compute_tessitura_bias(_make_span(high_notes), settings)

    assert centered_bias < high_bias
    assert high_bias > 0


def test_high_octave_duplicate_threshold() -> None:
    assert should_keep_high_octave_duplicate(0.9, 1.4, 0.5, threshold=0.6) is True
    assert should_keep_high_octave_duplicate(0.6, 1.1, 0.7, threshold=0.6) is False
