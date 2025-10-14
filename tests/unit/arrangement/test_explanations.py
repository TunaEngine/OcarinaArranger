from __future__ import annotations

import pytest

from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.phrase import PhraseNote, PhraseSpan


def test_explanation_event_builds_payload_and_bar_number() -> None:
    before = PhraseSpan(
        (
            PhraseNote(onset=1920, duration=480, midi=76),
            PhraseNote(onset=2160, duration=240, midi=74),
        ),
        pulses_per_quarter=480,
    )
    after = before.with_notes(note.with_midi(note.midi - 12) for note in before.notes)

    event = ExplanationEvent.from_step(
        schema_version=2,
        action="OCTAVE_DOWN_LOCAL",
        reason="Shifted phrase",
        before=before,
        after=after,
        difficulty_before=1.2,
        difficulty_after=0.8,
        span_id="span-custom",
        key_id="key-C",
        reason_code="manual-shift",
    )

    assert event.bar == 2
    assert event.difficulty_delta == pytest.approx(0.4)
    assert event.schema_version == 2
    assert event.reason_code == "manual-shift"
    assert event.span_id == "span-custom"
    assert event.key_id == "key-C"
    payload = event.to_payload()
    assert payload["bar"] == 2
    assert payload["action"] == "OCTAVE_DOWN_LOCAL"
    assert payload["difficulty_delta"] == pytest.approx(0.4)
    assert payload["before_note_count"] == 2
    assert payload["after_note_count"] == 2
    assert payload["schema_version"] == 2
    assert payload["reason_code"] == "manual-shift"
    assert payload["span_id"] == "span-custom"
    assert payload["key_id"] == "key-C"
    assert payload["span"] is None


def test_explanation_event_derives_reason_code_and_span_id() -> None:
    before = PhraseSpan((PhraseNote(onset=960, duration=480, midi=60),), pulses_per_quarter=480)
    after = before

    event = ExplanationEvent.from_step(
        action="drop-ornament",
        reason="  Dropped ornamental eighth  ",
        before=before,
        after=after,
        difficulty_before=0.9,
        difficulty_after=0.7,
    )

    assert event.reason_code == "dropped-ornamental-eighth"
    assert event.span_id == "span-960-1440"
    payload = event.to_payload()
    assert payload["reason_code"] == "dropped-ornamental-eighth"
    assert payload["span_id"] == "span-960-1440"


def test_explanation_event_payload_retains_legacy_fields() -> None:
    before = PhraseSpan((PhraseNote(onset=0, duration=480, midi=60),), pulses_per_quarter=480)
    event = ExplanationEvent.from_step(
        action="noop",
        reason="",
        before=before,
        after=before,
        difficulty_before=1.0,
        difficulty_after=1.0,
    )

    payload = event.to_payload()
    assert event.reason_code == "noop"
    assert "bar" in payload
    assert "reason" in payload
    assert "before_note_count" in payload
    assert "after_note_count" in payload


def test_explanation_event_requires_positive_beats_per_measure() -> None:
    span = PhraseSpan((PhraseNote(onset=0, duration=480, midi=60),), pulses_per_quarter=480)

    with pytest.raises(ValueError):
        ExplanationEvent.from_step(
            action="noop",
            reason="",
            before=span,
            after=span,
            difficulty_before=1.0,
            difficulty_after=0.8,
            beats_per_measure=0,
        )
