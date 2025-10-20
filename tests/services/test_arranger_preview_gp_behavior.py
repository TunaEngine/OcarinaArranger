"""Focused tests covering GP preview behaviour and tuning knobs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain.arrangement.difficulty import summarize_difficulty
from domain.arrangement.gp import GlobalTranspose
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools.events import NoteEvent
from ocarina_gui.fingering import InstrumentChoice

from services.arranger_preview import compute_arranger_preview
from services.arranger_preview_gp import _gp_session_config
from services.arranger_preview_utils import _auto_register_shift
from viewmodels.arranger_models import ArrangerGPSettings

from tests.services.arranger_preview_test_helpers import make_spec, preview_fixture


def test_compute_arranger_preview_gp_can_apply_session_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=60, program=0),
        NoteEvent(onset=240, duration=240, midi=62, program=0),
    )
    preview = preview_fixture(events)

    instrument = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    original_span = PhraseSpan(
        tuple(PhraseNote(onset=idx * 240, duration=240, midi=note.midi) for idx, note in enumerate(events)),
        pulses_per_quarter=480,
    )
    winner_span = original_span.transpose(12)
    winner_difficulty = summarize_difficulty(winner_span, instrument)

    def _fake_arrange(*_args, **_kwargs):
        winner = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=instrument,
            program=(GlobalTranspose(12),),
            span=winner_span,
            difficulty=winner_difficulty,
            fitness=None,
            explanations=(),
        )
        ranked = SimpleNamespace(
            instrument_id="alto_c_12",
            instrument=instrument,
            program=(),
            span=original_span,
            difficulty=summarize_difficulty(original_span, instrument),
            fitness=None,
            explanations=(),
        )
        return SimpleNamespace(
            chosen=ranked,
            winner_candidate=winner,
            comparisons=(ranked,),
            session=SimpleNamespace(generations=2, elapsed_seconds=0.5),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(generations=2),
    )

    assert computation.result_summary is not None
    assert computation.arranged_events
    arranged_midis = [event.midi for event in computation.arranged_events]
    expected_midis = [note.midi + 12 for note in events]
    assert arranged_midis == expected_midis


def test_compute_arranger_preview_gp_auto_register_shift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=69, program=0),
        NoteEvent(onset=240, duration=240, midi=70, program=0),
    )
    preview = preview_fixture(events)
    spec = make_spec(
        "alto_c_12",
        candidate_min="A4",
        candidate_max="F6",
        preferred_min="B4",
        preferred_max="E6",
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: (InstrumentChoice("alto_c_12", "12-hole Alto C"),),
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda _instrument_id: spec,
    )

    captured: dict[str, object] = {}

    def _fake_arrange(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            chosen=SimpleNamespace(
                instrument_id="alto_c_12",
                instrument=InstrumentRange(min_midi=69, max_midi=89, comfort_center=79),
                program=(),
                span=PhraseSpan(
                    tuple(
                        PhraseNote(onset=idx * 240, duration=240, midi=event.midi)
                        for idx, event in enumerate(events)
                    ),
                    pulses_per_quarter=480,
                ),
                difficulty=summarize_difficulty(
                    PhraseSpan(
                        tuple(
                            PhraseNote(onset=idx * 240, duration=240, midi=event.midi)
                            for idx, event in enumerate(events)
                        ),
                        pulses_per_quarter=480,
                    ),
                    InstrumentRange(min_midi=69, max_midi=89, comfort_center=79),
                ),
                fitness=None,
                explanations=(),
            ),
            winner_candidate=None,
            comparisons=(),
            session=SimpleNamespace(generations=1, elapsed_seconds=0.25),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange)

    compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(),
    )

    expected_shift = _auto_register_shift(
        PhraseSpan(
            tuple(
                PhraseNote(onset=idx * 240, duration=240, midi=event.midi)
                for idx, event in enumerate(events)
            ),
            pulses_per_quarter=480,
        ),
        InstrumentRange(min_midi=69, max_midi=89, comfort_center=79),
    )
    assert captured.get("preferred_register_shift") == expected_shift


def test_compute_arranger_preview_reports_intermediate_gp_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=60, program=0),
        NoteEvent(onset=240, duration=240, midi=62, program=0),
    )
    preview = preview_fixture(events)
    instrument_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)
    span = PhraseSpan(
        tuple(PhraseNote(onset=idx * 240, duration=240, midi=note.midi) for idx, note in enumerate(events)),
        pulses_per_quarter=480,
    )
    difficulty = summarize_difficulty(span, instrument_range)

    progress_updates: list[tuple[float, str]] = []

    def _progress(percent: float, message: str) -> None:
        progress_updates.append((percent, message))

    def _fake_arrange_v3_gp(*_args, **_kwargs):
        progress = _kwargs.get("progress_callback")
        if progress is not None:
            total = 5
            for index in range(total):
                progress(index, total)
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
            session=SimpleNamespace(generations=5, elapsed_seconds=1.0),
            termination_reason="generation_limit",
            archive_summary=(),
            fallback=None,
        )

    monkeypatch.setattr("services.arranger_preview.arrange_v3_gp", _fake_arrange_v3_gp)

    compute_arranger_preview(
        preview,
        arranger_mode="gp",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        gp_settings=ArrangerGPSettings(generations=5),
        progress_callback=_progress,
    )

    percents = [percent for percent, _ in progress_updates]
    assert percents[0] == 0.0
    assert 10.0 in percents
    assert any(10.0 < value < 99.0 for value in percents)
    assert percents[-1] == 100.0
    assert (99.0, "Running GP generation 5/5") in progress_updates


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
        fidelity_priority_weight=4.5,
        range_clamp_penalty=750.0,
        range_clamp_melody_bias=1.5,
        melody_shift_weight=3.0,
        rhythm_simplify_weight=1.75,
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
    penalties = config.scoring_penalties
    assert penalties.fidelity_weight == pytest.approx(4.5)
    assert penalties.range_clamp_penalty == pytest.approx(750.0)
    assert penalties.range_clamp_melody_bias == pytest.approx(1.5)
    assert penalties.melody_shift_weight == pytest.approx(3.0)
    assert penalties.rhythm_simplify_weight == pytest.approx(1.75)


__all__ = [
    "test_compute_arranger_preview_gp_auto_register_shift",
    "test_compute_arranger_preview_gp_can_apply_session_winner",
    "test_compute_arranger_preview_reports_intermediate_gp_progress",
    "test_gp_session_config_applies_advanced_settings",
]
