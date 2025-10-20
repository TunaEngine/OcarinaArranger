"""Tests covering the GP arranger preview path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain.arrangement.config import DEFAULT_GRACE_SETTINGS
from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.gp import GlobalTranspose
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange
from ocarina_gui.fingering import InstrumentChoice
from ocarina_tools.events import NoteEvent

from services.arranger_preview import compute_arranger_preview
from services.arranger_preview_gp import _gp_session_config
from viewmodels.arranger_models import ArrangerGPSettings

from tests.services.arranger_preview_test_helpers import make_spec, preview_fixture


def test_compute_arranger_preview_runs_gp_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=72, program=0),
        NoteEvent(onset=240, duration=240, midi=74, program=0),
    )
    preview = preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    spec = make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: spec,
    )

    instrument = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    phrase_notes = (
        PhraseNote(onset=0, duration=240, midi=72),
        PhraseNote(onset=240, duration=240, midi=74),
    )
    original_span = PhraseSpan(phrase_notes, pulses_per_quarter=480)
    candidate_span = original_span.transpose(2)
    difficulty = summarize_difficulty(candidate_span, instrument)
    explanation = ExplanationEvent.from_step(
        action="transpose",
        reason="Test",
        before=original_span,
        after=candidate_span,
        difficulty_before=0.8,
        difficulty_after=0.4,
    )

    called: dict[str, object] = {}

    def _fake_arrange_v3_gp(*args, **kwargs):
        called["kwargs"] = kwargs
        candidate = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=instrument,
            program=(GlobalTranspose(2),),
            span=candidate_span,
            difficulty=difficulty,
            fitness=None,
            explanations=(explanation,),
        )
        return SimpleNamespace(
            chosen=candidate,
            winner_candidate=candidate,
            comparisons=(candidate,),
            session=SimpleNamespace(generations=3, elapsed_seconds=1.25),
            termination_reason="generation_limit",
            archive_summary=(object(),),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(generations=4, population_size=10, time_budget_seconds=8.0),
    )

    assert called, "Expected arrange_v3_gp to be invoked"
    kwargs = dict(called["kwargs"])
    progress_cb = kwargs.pop("progress_callback", None)
    if progress_cb is not None:
        assert callable(progress_cb)
    grace_settings = kwargs.pop("grace_settings", None)
    assert grace_settings == DEFAULT_GRACE_SETTINGS
    assert kwargs == {
        "instrument_id": "alto_c_12",
        "starred_ids": (),
        "config": _gp_session_config(
            ArrangerGPSettings(
                generations=4,
                population_size=10,
                time_budget_seconds=8.0,
            )
        ),
        "manual_transposition": 0,
        "transposition": 0,
        "preferred_register_shift": 0,
    }
    assert computation.summaries
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == 2
    assert computation.telemetry
    assert computation.arranged_events is not None
    assert computation.strategy == "current"


def test_compute_arranger_preview_gp_current_strategy_ignores_starred_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=72, program=0),
        NoteEvent(onset=240, duration=240, midi=74, program=0),
    )
    preview = preview_fixture(events)

    choices = (
        InstrumentChoice("alto_c_12", "12-hole Alto C"),
        InstrumentChoice("bass_c_12", "12-hole Bass C"),
    )
    alto_spec = make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )
    bass_spec = make_spec(
        "bass_c_12",
        candidate_min="A3",
        candidate_max="F5",
        preferred_min="A3",
        preferred_max="F5",
    )

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: alto_spec if instrument_id == "alto_c_12" else bass_spec,
    )

    captured: dict[str, object] = {}

    def _fake_arrange_v3_gp(*args, **kwargs):
        captured["kwargs"] = kwargs
        candidate = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=InstrumentRange(min_midi=57, max_midi=81, comfort_center=69),
            program=(),
            span=PhraseSpan(
                (
                    PhraseNote(onset=0, duration=240, midi=72),
                    PhraseNote(onset=240, duration=240, midi=74),
                ),
                pulses_per_quarter=480,
            ),
            difficulty=summarize_difficulty(
                PhraseSpan(
                    (
                        PhraseNote(onset=0, duration=240, midi=72),
                        PhraseNote(onset=240, duration=240, midi=74),
                    ),
                    pulses_per_quarter=480,
                ),
                InstrumentRange(min_midi=57, max_midi=81, comfort_center=69),
            ),
            fitness=None,
            explanations=(),
        )
        return SimpleNamespace(
            chosen=candidate,
            winner_candidate=candidate,
            comparisons=(candidate,),
            session=SimpleNamespace(generations=1, elapsed_seconds=0.5),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=("bass_c_12",),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(),
    )

    kwargs = dict(captured.get("kwargs", {}))
    assert kwargs.get("starred_ids") == ()
    assert computation.resolved_starred_ids == ("bass_c_12",)


def test_compute_arranger_preview_gp_starred_updates_resolved_instrument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=72, program=0),
        NoteEvent(onset=240, duration=240, midi=74, program=0),
    )
    preview = preview_fixture(events)

    choices = (
        InstrumentChoice("alto_c_12", "12-hole Alto C"),
        InstrumentChoice("soprano_c_6", "6-hole Soprano C"),
    )
    alto_spec = make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )
    soprano_spec = make_spec(
        "soprano_c_6",
        candidate_min="C4",
        candidate_max="C6",
        preferred_min="D4",
        preferred_max="A5",
    )

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: alto_spec if instrument_id == "alto_c_12" else soprano_spec,
    )

    soprano_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    alto_range = InstrumentRange(min_midi=57, max_midi=81, comfort_center=69)
    phrase_notes = (
        PhraseNote(onset=0, duration=240, midi=72),
        PhraseNote(onset=240, duration=240, midi=74),
    )
    span = PhraseSpan(phrase_notes, pulses_per_quarter=480)
    alto_span = span.transpose(-2)

    def _fake_arrange_v3_gp(*_args, **_kwargs):
        base_candidate = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=alto_range,
            program=(GlobalTranspose(-2),),
            span=alto_span,
            difficulty=summarize_difficulty(alto_span, alto_range),
            fitness=None,
            explanations=(),
        )
        starred_candidate = SimpleNamespace(
            instrument_id="soprano_c_6",
            instrument=soprano_range,
            program=(),
            span=span,
            difficulty=summarize_difficulty(span, soprano_range),
            fitness=None,
            explanations=(),
        )
        return SimpleNamespace(
            chosen=starred_candidate,
            winner_candidate=base_candidate,
            comparisons=(starred_candidate, base_candidate),
            session=SimpleNamespace(generations=2, elapsed_seconds=0.75),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
            strategy="starred-best",
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=("soprano_c_6",),
        strategy="starred-best",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(),
    )

    assert computation.result_summary is not None
    assert computation.result_summary.instrument_id == "soprano_c_6"
    assert computation.result_summary.transposition == 0
    assert computation.resolved_instrument_id == "soprano_c_6"
    assert computation.resolved_instrument_range == ("D4", "A5")
    assert computation.summaries
    assert computation.summaries[0].instrument_id == "soprano_c_6"
    assert computation.summaries[0].is_winner is True
    assert computation.arranged_events is not None
    assert tuple(event.midi for event in computation.arranged_events) == (72, 74)
    assert sum(1 for row in computation.summaries if row.is_winner) == 1


def test_compute_arranger_preview_gp_respects_manual_transpose(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=480, duration=480, midi=62, program=0),
        NoteEvent(onset=960, duration=480, midi=64, program=0),
    )
    preview = preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    instrument_spec = make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )
    instrument_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: instrument_spec,
    )

    captured: dict[str, object] = {}

    def _fake_arrange_v3_gp(span, *args, **kwargs):
        captured["phrase_midis"] = tuple(note.midi for note in span.notes)
        captured["kwargs"] = kwargs
        difficulty = summarize_difficulty(span, instrument_range)
        candidate = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=instrument_range,
            program=(),
            span=span,
            difficulty=difficulty,
            fitness=None,
            explanations=(),
        )
        return SimpleNamespace(
            chosen=candidate,
            winner_candidate=candidate,
            comparisons=(candidate,),
            session=SimpleNamespace(generations=1, elapsed_seconds=0.1),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(apply_program_preference="ranked"),
        transpose_offset=5,
    )

    expected_midis = tuple(midi + 5 for midi in (60, 62, 64))
    assert captured["phrase_midis"] == expected_midis
    assert computation.arranged_events is not None
    assert tuple(event.midi for event in computation.arranged_events) == expected_midis
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == 5
    assert captured.get("kwargs", {}).get("manual_transposition") == 5
    assert captured.get("kwargs", {}).get("transposition") == 5
    assert captured.get("kwargs", {}).get("preferred_register_shift") == 0


def test_compute_arranger_preview_gp_uses_chosen_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=480, duration=480, midi=60, program=0),
    )
    preview = preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    instrument_spec = make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )
    instrument_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: instrument_spec,
    )

    chosen_span = PhraseSpan(
        (
            PhraseNote(onset=0, duration=480, midi=72),
            PhraseNote(onset=480, duration=480, midi=74),
        ),
        pulses_per_quarter=480,
    )
    runner_up_span = PhraseSpan(
        (
            PhraseNote(onset=0, duration=480, midi=67),
            PhraseNote(onset=480, duration=480, midi=69),
        ),
        pulses_per_quarter=480,
    )
    chosen_candidate = SimpleNamespace(
        instrument_id="alto_c_12",
        instrument=instrument_range,
        program=(GlobalTranspose(12),),
        span=chosen_span,
        difficulty=summarize_difficulty(chosen_span, instrument_range),
        fitness=None,
        explanations=(),
    )
    runner_up = SimpleNamespace(
        instrument_id="alto_c_12",
        instrument=instrument_range,
        program=(GlobalTranspose(0),),
        span=runner_up_span,
        difficulty=summarize_difficulty(runner_up_span, instrument_range),
        fitness=None,
        explanations=(),
    )

    def _fake_arrange_v3_gp(*args, **kwargs):
        return SimpleNamespace(
            chosen=chosen_candidate,
            winner_candidate=runner_up,
            comparisons=(chosen_candidate, runner_up),
            session=SimpleNamespace(generations=1, elapsed_seconds=0.2),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(apply_program_preference="ranked"),
    )

    assert computation.arranged_events is not None
    arranged_midis = tuple(event.midi for event in computation.arranged_events)
    assert arranged_midis == (72, 74)
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == 12


