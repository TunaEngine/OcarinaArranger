from __future__ import annotations

from pathlib import Path

import pytest

from domain.arrangement.config import clear_instrument_registry
from ocarina_gui.fingering import InstrumentChoice, InstrumentSpec
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent
from services.arranger_preview import ArrangerComputation
from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.arranger_models import (
    ArrangerEditBreakdown,
    ArrangerGPSettings,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
)
from viewmodels.main_viewmodel import (
    ARRANGER_STRATEGY_STARRED_BEST,
    MainViewModel,
)


def test_render_previews_populates_arranger_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_instrument_registry()
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    events = [
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=480, duration=480, midi=79, program=0),
        NoteEvent(onset=960, duration=480, midi=83, program=0),
    ]
    preview = PreviewData(
        original_events=events,
        arranged_events=events,
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 90),
        arranged_range=(60, 90),
        tempo_bpm=120,
        tempo_changes=(),
    )
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(
        input_path=str(file_path),
        arranger_mode="best_effort",
        instrument_id="alto_c",
    )
    viewmodel.state.arranger_strategy = ARRANGER_STRATEGY_STARRED_BEST
    viewmodel.state.starred_instrument_ids = ("soprano_c",)

    def _instrument_spec(
        instrument_id: str,
        candidate_min: str,
        candidate_max: str,
        preferred_min: str,
        preferred_max: str,
    ) -> InstrumentSpec:
        return InstrumentSpec.from_dict(
            {
                "id": instrument_id,
                "name": instrument_id.replace("_", " ").title(),
                "title": instrument_id,
                "canvas": {"width": 100, "height": 100},
                "style": {
                    "background_color": "#ffffff",
                    "outline_color": "#000000",
                    "outline_width": 2.0,
                    "outline_smooth": True,
                    "outline_spline_steps": 16,
                    "hole_outline_color": "#000000",
                    "covered_fill_color": "#000000",
                },
                "holes": [],
                "windways": [],
                "note_order": ["C4"],
                "note_map": {"C4": []},
                "preferred_range": {"min": preferred_min, "max": preferred_max},
                "candidate_range": {"min": candidate_min, "max": candidate_max},
            }
        )

    alto_spec = _instrument_spec("alto_c", "B3", "A5", "C4", "G5")
    soprano_spec = _instrument_spec("soprano_c", "C4", "C6", "D4", "A5")

    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: alto_spec if instrument_id == "alto_c" else soprano_spec,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: [
            InstrumentChoice("alto_c", "Alto C"),
            InstrumentChoice("soprano_c", "Soprano C"),
        ],
    )

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.instrument_id == "soprano_c"
    assert viewmodel.state.range_min == "D4"
    assert viewmodel.state.range_max == "A5"
    comparisons = viewmodel.state.arranger_strategy_summary
    assert len(comparisons) == 1
    assert sum(1 for row in comparisons if row.is_winner) == 1
    assert comparisons[0].instrument_id == "soprano_c"
    summary = viewmodel.state.arranger_result_summary
    assert summary is not None
    assert summary.instrument_name == "Soprano C"
    assert isinstance(summary.transposition, int)
    total_ratio = summary.easy + summary.medium + summary.hard + summary.very_hard
    assert total_ratio == pytest.approx(1.0, abs=1e-6)


def test_render_previews_applies_summary_winner_when_service_omits_resolution(
    monkeypatch: pytest.MonkeyPatch, preview_data: PreviewData, tmp_path: Path
) -> None:
    clear_instrument_registry()
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(
        input_path=str(file_path),
        arranger_mode="gp",
        instrument_id="f_maj_6",
    )
    viewmodel.state.arranger_strategy = ARRANGER_STRATEGY_STARRED_BEST
    viewmodel.state.starred_instrument_ids = ("alto_c_12", "a_major_12")

    summaries = (
        ArrangerInstrumentSummary(
            instrument_id="f_maj_6",
            instrument_name="6-hole F Major",
            easy=0.10,
            medium=0.30,
            hard=0.30,
            very_hard=0.30,
            tessitura=0.50,
        ),
        ArrangerInstrumentSummary(
            instrument_id="alto_c_12",
            instrument_name="12-hole Alto C",
            easy=0.40,
            medium=0.30,
            hard=0.20,
            very_hard=0.10,
            tessitura=0.35,
            transposition=0,
            is_winner=True,
        ),
    )
    result_summary = ArrangerResultSummary(
        instrument_id="alto_c_12",
        instrument_name="12-hole Alto C",
        transposition=0,
        easy=0.40,
        medium=0.30,
        hard=0.20,
        very_hard=0.10,
        tessitura=0.35,
        starting_difficulty=0.80,
        final_difficulty=0.40,
        difficulty_threshold=0.60,
        met_threshold=True,
        difficulty_delta=0.40,
        applied_steps=(),
        edits=ArrangerEditBreakdown(),
    )
    computation = ArrangerComputation(
        summaries=summaries,
        result_summary=result_summary,
        strategy="starred-best",
        resolved_instrument_id=None,
        resolved_starred_ids=("alto_c_12", "a_major_12"),
        arranged_events=tuple(),
        resolved_instrument_range=("D4", "A5"),
    )

    monkeypatch.setattr(
        "viewmodels.main_viewmodel_arranger_helpers.compute_arranger_preview",
        lambda *_args, **_kwargs: computation,
    )

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.instrument_id == "alto_c_12"
    assert viewmodel.state.range_min == "D4"
    assert viewmodel.state.range_max == "A5"
    preview_out = result.unwrap()
    assert isinstance(preview_out, PreviewData)


def test_render_previews_keeps_current_instrument_for_current_strategy(
    monkeypatch: pytest.MonkeyPatch, preview_data: PreviewData, tmp_path: Path
) -> None:
    clear_instrument_registry()
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(
        input_path=str(file_path),
        arranger_mode="gp",
        instrument_id="alto_c_12",
    )
    viewmodel.state.arranger_strategy = "current"
    viewmodel.state.starred_instrument_ids = ("bass_c_12",)
    viewmodel.state.range_min = "C4"
    viewmodel.state.range_max = "G5"

    summaries = (
        ArrangerInstrumentSummary(
            instrument_id="bass_c_12",
            instrument_name="12-hole Bass C",
            easy=0.20,
            medium=0.30,
            hard=0.30,
            very_hard=0.20,
            tessitura=0.45,
            transposition=0,
            is_winner=True,
        ),
    )
    result_summary = ArrangerResultSummary(
        instrument_id="alto_c_12",
        instrument_name="12-hole Alto C",
        transposition=0,
        easy=0.25,
        medium=0.35,
        hard=0.25,
        very_hard=0.15,
        tessitura=0.40,
        starting_difficulty=0.70,
        final_difficulty=0.45,
        difficulty_threshold=0.60,
        met_threshold=True,
        difficulty_delta=0.25,
        applied_steps=(),
        edits=ArrangerEditBreakdown(),
    )
    computation = ArrangerComputation(
        summaries=summaries,
        result_summary=result_summary,
        strategy="current",
        resolved_instrument_id="alto_c_12",
        resolved_starred_ids=("bass_c_12",),
        arranged_events=tuple(),
        resolved_instrument_range=None,
    )

    monkeypatch.setattr(
        "viewmodels.main_viewmodel_arranger_helpers.compute_arranger_preview",
        lambda *_args, **_kwargs: computation,
    )

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.instrument_id == "alto_c_12"
    assert viewmodel.state.range_min == "C4"
    assert viewmodel.state.range_max == "G5"
    assert viewmodel.state.starred_instrument_ids == ("bass_c_12",)


def test_render_previews_passes_gp_settings(
    monkeypatch: pytest.MonkeyPatch, preview_data: PreviewData, tmp_path: Path
) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(
        input_path=str(file_path),
        arranger_mode="gp",
        instrument_id="alto_c",
        arranger_gp_settings={
            "generations": 6,
            "population_size": 18,
            "time_budget_seconds": 12.0,
        },
    )

    captured: dict[str, object] = {}

    def _fake_compute(preview: PreviewData, **kwargs) -> ArrangerComputation:
        captured.update(kwargs)
        return ArrangerComputation(
            summaries=(), result_summary=None, strategy=kwargs.get("strategy", "gp")
        )

    monkeypatch.setattr(
        "viewmodels.main_viewmodel_arranger_helpers.compute_arranger_preview",
        _fake_compute,
    )

    result = viewmodel.render_previews()

    assert result.is_ok()
    gp_settings = captured.get("gp_settings")
    assert isinstance(gp_settings, ArrangerGPSettings)
    assert gp_settings.generations == 6
    assert gp_settings.population_size == 18
    assert gp_settings.time_budget_seconds == 12.0
    assert captured.get("transpose_offset") == viewmodel.state.transpose_offset


def test_render_previews_applies_best_effort_transposition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clear_instrument_registry()
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    events = [
        NoteEvent(onset=i * 480, duration=480, midi=midi, program=0)
        for i, midi in enumerate([84, 86, 88, 79, 88])
    ]
    preview = PreviewData(
        original_events=tuple(events),
        arranged_events=tuple(events),
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 90),
        arranged_range=(60, 90),
        tempo_bpm=120,
        tempo_changes=(),
    )
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(
        input_path=str(file_path),
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
    )

    def _spec(identifier: str) -> InstrumentSpec:
        return InstrumentSpec.from_dict(
            {
                "id": identifier,
                "name": identifier,
                "title": identifier,
                "canvas": {"width": 120, "height": 120},
                "style": {
                    "background_color": "#ffffff",
                    "outline_color": "#000000",
                    "outline_width": 2.0,
                    "outline_smooth": True,
                    "outline_spline_steps": 16,
                    "hole_outline_color": "#000000",
                    "covered_fill_color": "#000000",
                },
                "holes": [],
                "windways": [],
                "note_order": ["C4"],
                "note_map": {"C4": []},
                "preferred_range": {"min": "C4", "max": "G5"},
                "candidate_range": {"min": "B3", "max": "A5"},
            }
        )

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: [InstrumentChoice("alto_c_12", "12-hole Alto C")],
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: _spec(instrument_id),
    )

    result = viewmodel.render_previews()

    assert result.is_ok()
    preview_out = result.unwrap()
    arranged_midis = [event.midi for event in preview_out.arranged_events]
    assert arranged_midis == [72, 74, 76, 79, 76]
    summary = viewmodel.state.arranger_result_summary
    assert summary is not None
    assert summary.transposition == 0
