from pathlib import Path

import pytest

from domain.arrangement.config import clear_instrument_registry
from ocarina_gui.fingering import InstrumentChoice, InstrumentSpec
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent
from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import PreviewPlaybackSnapshot
from services.arranger_preview import ArrangerComputation
from tests.viewmodels._fakes import FakeDialogs, StubScoreService
from viewmodels.arranger_models import ArrangerGPSettings
from viewmodels.main_viewmodel import (
    ARRANGER_STRATEGY_STARRED_BEST,
    MainViewModel,
)


def test_browse_for_input_updates_state(tmp_path: Path) -> None:
    file_path = tmp_path / "picked.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(file_path))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.state.pitch_list = ["C4"]
    viewmodel.update_preview_settings({"arranged": PreviewPlaybackSnapshot()})
    viewmodel.state.available_parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Part 1",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.state.selected_part_ids = ("P1",)

    assert viewmodel.browse_for_input() is True

    assert viewmodel.state.input_path == str(file_path)
    assert viewmodel.state.pitch_list == []
    assert viewmodel.state.available_parts == ()
    assert viewmodel.state.selected_part_ids == ()
    assert viewmodel.state.preview_settings == {}
    assert viewmodel.state.status_message == "Ready."


def test_browse_for_input_cancel_retains_state(tmp_path: Path) -> None:
    existing = tmp_path / "existing.musicxml"
    existing.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs(open_path=None)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.update_settings(input_path=str(existing))
    viewmodel.state.pitch_list = ["D4"]

    assert viewmodel.browse_for_input() is False

    assert viewmodel.state.input_path == str(existing)
    assert viewmodel.state.pitch_list == ["D4"]


def test_load_part_metadata_updates_state(tmp_path: Path) -> None:
    file_path = tmp_path / "parts.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=10,
            min_midi=60,
            max_midi=72,
            min_pitch="C4",
            max_pitch="C5",
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Accompaniment",
            midi_program=None,
            note_count=5,
            min_midi=55,
            max_midi=67,
            min_pitch="G3",
            max_pitch="G4",
        ),
    )
    service = StubScoreService(part_metadata=parts)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    loaded = viewmodel.load_part_metadata()

    assert loaded == parts
    assert viewmodel.state.available_parts == parts
    assert viewmodel.state.selected_part_ids == ("P1", "P2")
    assert service.part_metadata_calls == [str(file_path)]


def test_apply_part_selection_filters_unknown_parts() -> None:
    dialogs = FakeDialogs()
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    available = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Piano",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.update_settings(available_parts=available)

    selection = viewmodel.apply_part_selection(["P1", "P3", "P2"])

    assert selection == ("P1", "P2")
    assert viewmodel.state.selected_part_ids == ("P1", "P2")


def test_ask_select_parts_propagates_cancel() -> None:
    dialogs = FakeDialogs(part_selection=None)
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Solo",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )

    result = viewmodel.ask_select_parts(parts, ("P1",))

    assert result is None


def test_render_previews_sets_status(preview_data: PreviewData, tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.status_message == "Preview rendered."
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.transpose_offset == 0


def test_render_previews_propagates_error(tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview_error=RuntimeError("boom"))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path))

    result = viewmodel.render_previews()

    assert result.is_err()
    assert result.error == "boom"
    assert viewmodel.state.status_message == "Preview failed."


def test_render_previews_passes_manual_transpose(preview_data: PreviewData, tmp_path: Path) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    viewmodel.update_settings(input_path=str(file_path), transpose_offset=-4)

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.transpose_offset == -4


def test_render_previews_passes_filtered_part_selection(
    preview_data: PreviewData, tmp_path: Path
) -> None:
    file_path = tmp_path / "score.musicxml"
    file_path.write_text("<score />", encoding="utf-8")
    dialogs = FakeDialogs()
    service = StubScoreService(preview=preview_data)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)
    parts = (
        MusicXmlPartInfo(
            part_id="P1",
            name="Lead",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
        MusicXmlPartInfo(
            part_id="P2",
            name="Harmony",
            midi_program=None,
            note_count=0,
            min_midi=None,
            max_midi=None,
            min_pitch=None,
            max_pitch=None,
        ),
    )
    viewmodel.update_settings(input_path=str(file_path), available_parts=parts)
    viewmodel.apply_part_selection(["P2", "PX"])

    result = viewmodel.render_previews()

    assert result.is_ok()
    assert viewmodel.state.selected_part_ids == ("P2",)
    assert service.last_preview_settings is not None
    assert service.last_preview_settings.selected_part_ids == ("P2",)


def test_render_previews_populates_arranger_results(
    monkeypatch, tmp_path: Path
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
    comparisons = viewmodel.state.arranger_strategy_summary
    assert len(comparisons) == 2
    assert sum(1 for row in comparisons if row.is_winner) == 1
    summary = viewmodel.state.arranger_result_summary
    assert summary is not None
    assert summary.instrument_name in {"Alto C", "Soprano C"}
    assert isinstance(summary.transposition, int)
    total_ratio = summary.easy + summary.medium + summary.hard + summary.very_hard
    assert total_ratio == pytest.approx(1.0, abs=1e-6)
    preview_out = result.unwrap()
    assert isinstance(preview_out, PreviewData)


def test_render_previews_passes_gp_settings(monkeypatch, preview_data: PreviewData, tmp_path: Path) -> None:
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
        return ArrangerComputation(summaries=(), result_summary=None, strategy=kwargs.get("strategy", "gp"))

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


def test_new_input_path_clears_preview_settings(tmp_path: Path) -> None:
    first = tmp_path / "first.musicxml"
    first.write_text("<score />", encoding="utf-8")
    second = tmp_path / "second.musicxml"
    second.write_text("<score />", encoding="utf-8")

    dialogs = FakeDialogs()
    service = StubScoreService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service)

    viewmodel.update_settings(input_path=str(first))
    viewmodel.update_preview_settings(
        {
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=150.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=1.0,
                loop_end_beat=3.0,
            )
        }
    )

    # Updating with the same path should preserve the snapshot
    viewmodel.update_settings(input_path=str(first))
    assert "arranged" in viewmodel.state.preview_settings

    # Selecting a different file clears any prior playback adjustments
    viewmodel.update_settings(input_path=str(second))
    assert viewmodel.state.preview_settings == {}


def test_render_previews_applies_best_effort_transposition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
