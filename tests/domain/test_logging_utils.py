from domain.arrangement.difficulty import DifficultySummary
from domain.arrangement.logging_utils import (
    describe_difficulty,
    describe_instrument,
    describe_melody_actions,
    describe_span,
)
from domain.arrangement.melody import MelodyIsolationAction
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def test_describe_span_with_notes() -> None:
    span = PhraseSpan(
        (
            PhraseNote(onset=0, duration=120, midi=62),
            PhraseNote(onset=240, duration=120, midi=74),
        ),
        pulses_per_quarter=480,
    )

    description = describe_span(span)

    assert "notes=2" in description
    assert "D4" in description
    assert "D5" in description


def test_describe_span_empty() -> None:
    span = PhraseSpan((), pulses_per_quarter=360)

    description = describe_span(span)

    assert "notes=0" in description
    assert "pulses_per_quarter=360" in description


def test_describe_instrument_includes_range() -> None:
    instrument = InstrumentRange(min_midi=60, max_midi=72)

    description = describe_instrument(instrument)

    assert "C4" in description
    assert "C5" in description


def test_describe_difficulty_formats_summary() -> None:
    summary = DifficultySummary(
        easy=1.0,
        medium=2.0,
        hard=3.0,
        very_hard=4.0,
        tessitura_distance=1.5,
        leap_exposure=0.25,
        fast_windway_switch_exposure=0.0,
        subhole_transition_duration=0.0,
        subhole_exposure=0.0,
    )

    description = describe_difficulty(summary)

    assert "difficulty=score" in description
    assert "hvh=7.000" in description
    assert "tess=1.500" in description


def test_describe_melody_actions_limits_preview() -> None:
    actions = [
        MelodyIsolationAction(
            measure=index + 1,
            action="KEEP",
            reason="register_anchor",
            kept_voice=0,
            removed_voice=1,
        )
        for index in range(6)
    ]

    description = describe_melody_actions(actions, limit=3)

    assert description.startswith("actions=6[")
    assert "m1:KEEP:register_anchor" in description
    assert "…(+3 more)" in description
