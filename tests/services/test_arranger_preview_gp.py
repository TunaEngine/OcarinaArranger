"""Tests covering the GP arranger preview path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
    assert called["kwargs"] == {
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
    }
    assert computation.summaries
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == 2
    assert computation.telemetry
    assert computation.arranged_events is not None
    assert computation.strategy == "current"


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
        gp_settings=ArrangerGPSettings(),
        transpose_offset=5,
    )

    expected_midis = tuple(midi + 5 for midi in (60, 62, 64))
    assert captured["phrase_midis"] == expected_midis
    assert computation.arranged_events is not None
    assert tuple(event.midi for event in computation.arranged_events) == expected_midis
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == 5
    assert captured.get("kwargs", {}).get("manual_transposition") == 5


def test_gp_session_config_applies_advanced_settings() -> None:
    settings = ArrangerGPSettings(
        generations=5,
        population_size=20,
        archive_size=9,
        random_program_count=7,
        crossover_rate=0.55,
        mutation_rate=0.25,
        log_best_programs=5,
        random_seed=42,
        time_budget_seconds=18.0,
        playability_weight=0.8,
        fidelity_weight=2.4,
        tessitura_weight=0.6,
        program_size_weight=0.4,
        contour_weight=0.45,
        lcs_weight=0.55,
        pitch_weight=0.6,
    )

    config = _gp_session_config(settings)

    assert config.generations == 5
    assert config.population_size == 20
    assert config.archive_size == 9
    assert config.random_program_count == 7
    assert config.crossover_rate == pytest.approx(0.55)
    assert config.mutation_rate == pytest.approx(0.25)
    assert config.log_best_programs == 5
    assert config.random_seed == 42
    assert config.time_budget_seconds == pytest.approx(18.0)

    fitness = config.fitness_config
    assert fitness is not None
    assert fitness.playability.weight == pytest.approx(0.8)
    assert fitness.fidelity.weight == pytest.approx(2.4)
    assert fitness.tessitura.weight == pytest.approx(0.6)
    assert fitness.program_size.weight == pytest.approx(0.4)
    assert fitness.fidelity_components.contour_weight == pytest.approx(0.45)
    assert fitness.fidelity_components.lcs_weight == pytest.approx(0.55)
    assert fitness.fidelity_components.pitch_weight == pytest.approx(0.6)
