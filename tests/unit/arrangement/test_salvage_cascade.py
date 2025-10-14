from __future__ import annotations

import pytest

from domain.arrangement.micro_edits import drop_ornamental_eighth, shift_short_phrase_octave
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.salvage import SalvageBudgets, SalvageCascade, SalvageStep


def _difficulty_for_high_notes(span: PhraseSpan) -> float:
    return 1.2 if any(note.midi > 72 for note in span.notes) else 0.5


def _difficulty_for_density(span: PhraseSpan) -> float:
    return 1.1 if len(span.notes) > 3 else 0.6


def test_salvage_cascade_applies_octave_down_then_stops() -> None:
    notes = (
        PhraseNote(onset=0, duration=480, midi=76, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=480, duration=480, midi=74, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=960, duration=480, midi=71),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)

    cascade = SalvageCascade(
        threshold=0.9,
        steps=(
            SalvageStep(
                "OCTAVE_DOWN_LOCAL",
                lambda span: shift_short_phrase_octave(span, direction="down"),
                budget_key="octave",
            ),
            SalvageStep("rhythm-simplify", drop_ornamental_eighth, budget_key="rhythm"),
        ),
    )

    result = cascade.run(span, _difficulty_for_high_notes)

    assert result.success is True
    assert result.applied_steps == ("OCTAVE_DOWN_LOCAL",)
    assert all(note.midi <= 72 for note in result.span.notes)
    assert result.starting_difficulty == 1.2
    assert result.difficulty_delta == pytest.approx(0.7)
    assert len(result.explanations) == 1
    explanation = result.explanations[0]
    assert explanation.action == "OCTAVE_DOWN_LOCAL"
    assert explanation.difficulty_delta == pytest.approx(0.7)
    assert result.edits_used["octave"] == 1
    assert result.edits_used["total"] == 1


def test_salvage_cascade_progresses_to_next_step_when_no_change() -> None:
    notes = (
        PhraseNote(onset=0, duration=240, midi=65),
        PhraseNote(onset=240, duration=240, midi=67),
        PhraseNote(onset=480, duration=240, midi=69, tags=frozenset({"ornamental"})),
        PhraseNote(onset=720, duration=240, midi=71),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)

    cascade = SalvageCascade(
        threshold=0.9,
        steps=(
            SalvageStep("OCTAVE_DOWN_LOCAL", lambda span: span, budget_key="octave"),
            SalvageStep(
                "rhythm-simplify",
                drop_ornamental_eighth,
                explain=lambda before, after, before_diff, after_diff: "Removed ornament",
                budget_key="rhythm",
            ),
        ),
    )

    result = cascade.run(span, _difficulty_for_density)

    assert result.success is True
    assert result.applied_steps == ("rhythm-simplify",)
    assert len(result.span.notes) == 3
    assert len(result.explanations) == 1
    assert result.explanations[0].reason == "Removed ornament"
    assert result.edits_used.get("rhythm", 0) == 1
    assert result.edits_used["total"] == 1


def test_salvage_cascade_reports_failure_when_threshold_not_met() -> None:
    notes = (
        PhraseNote(onset=0, duration=240, midi=65),
        PhraseNote(onset=240, duration=240, midi=67),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)

    cascade = SalvageCascade(
        threshold=0.8,
        steps=(SalvageStep("noop", lambda span: span),),
    )

    result = cascade.run(span, lambda _: 1.1)

    assert result.success is False
    assert result.applied_steps == ("not-recommended",)
    assert result.difficulty == 1.1
    assert result.explanations
    assert result.explanations[-1].action == "not-recommended"
    assert result.edits_used["total"] == 0


def test_salvage_stops_when_budget_spent() -> None:
    notes = (
        PhraseNote(onset=0, duration=480, midi=76, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=480, duration=480, midi=74, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=960, duration=480, midi=71, tags=frozenset({"ornamental"})),
    )
    span = PhraseSpan(notes, pulses_per_quarter=480)

    cascade = SalvageCascade(
        threshold=0.7,
        steps=(
            SalvageStep("OCTAVE_DOWN_LOCAL", lambda span: shift_short_phrase_octave(span, direction="down"), budget_key="octave"),
            SalvageStep("rhythm-simplify", drop_ornamental_eighth, budget_key="rhythm"),
        ),
        budgets=SalvageBudgets(max_octave_edits=1, max_rhythm_edits=0, max_substitutions=0, max_steps_per_span=1),
    )

    def difficulty_fn(current: PhraseSpan) -> float:
        midi_penalty = 0.3 if any(note.midi > 72 for note in current.notes) else 0.0
        density_penalty = 0.3 if len(current.notes) > 2 else 0.0
        return 0.6 + midi_penalty + density_penalty

    result = cascade.run(span, difficulty_fn)

    assert result.success is False
    assert result.applied_steps == ("OCTAVE_DOWN_LOCAL", "not-recommended")
    assert result.edits_used["octave"] == 1
    assert result.edits_used["total"] == 1
    # rhythm step skipped due to zero budget and total steps limit
    assert "rhythm" not in result.edits_used or result.edits_used["rhythm"] == 0
