from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from services.project_service import LoadedProject, PreviewPlaybackSnapshot
from shared.result import Result
from tests.viewmodels._fakes import FakeDialogs, StubProjectService, StubScoreService
from viewmodels.main_viewmodel import MainViewModel


def _make_loaded_project(tmp_path: Path, conversion: ConversionResult) -> LoadedProject:
    archive = tmp_path / "song.ocarina"
    working_dir = tmp_path / "workspace"
    input_path = working_dir / "original.musicxml"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("<score/>", encoding="utf-8")
    grace_settings = GraceTransformSettings(
        policy="steal",
        fractions=(0.2, 0.1, 0.05),
        max_chain=4,
        anchor_min_fraction=0.6,
        fold_out_of_range=False,
        drop_out_of_range=True,
        slow_tempo_bpm=72.0,
        fast_tempo_bpm=160.0,
        grace_bonus=0.4,
    ).normalized()
    return LoadedProject(
        archive_path=archive,
        working_directory=working_dir,
        input_path=input_path,
        settings=TransformSettings(
            prefer_mode="lydian",
            range_min="C4",
            range_max="C6",
            prefer_flats=False,
            collapse_chords=False,
            favor_lower=True,
            transpose_offset=1,
            instrument_id="alto",
            selected_part_ids=("P2",),
            grace_settings=grace_settings,
        ),
        pdf_options=PdfExportOptions.with_defaults(page_size="A6", orientation="portrait"),
        pitch_list=["C4", "D4"],
        pitch_entries=["C4", "D4"],
        status_message="Project loaded.",
        conversion=conversion,
        preview_settings={
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=88.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=2.0,
                loop_end_beat=4.0,
            )
        },
        grace_settings=grace_settings,
    )


def test_save_project_requires_input(tmp_path: Path) -> None:
    dialogs = FakeDialogs(project_save_path=str(tmp_path / "project.ocarina"))
    project_service = StubProjectService()
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService(), project_service=project_service)

    result = viewmodel.save_project()
    assert isinstance(result, Result)
    assert result.is_err()
    assert "Choose" in result.error
    assert project_service.saved_snapshots == []


def test_save_project_invokes_service(tmp_path: Path, conversion_result: ConversionResult) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    dialogs = FakeDialogs(
        save_path=str(tmp_path / "converted.musicxml"),
        project_save_path=str(tmp_path / "project.ocarina"),
    )
    project_service = StubProjectService()
    service = StubScoreService(conversion=conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=service, project_service=project_service)
    grace_settings = GraceTransformSettings(
        policy="steal",
        fractions=(0.2, 0.1, 0.05),
        max_chain=2,
        anchor_min_fraction=0.4,
        fold_out_of_range=False,
        drop_out_of_range=False,
        slow_tempo_bpm=72.0,
        fast_tempo_bpm=180.0,
        grace_bonus=0.6,
    )
    viewmodel.update_settings(input_path=str(input_path), grace_settings=grace_settings)
    convert_result = viewmodel.convert()
    assert convert_result is not None and convert_result.is_ok()
    viewmodel.update_preview_settings(
        {
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=102.0,
                metronome_enabled=False,
                loop_enabled=True,
                loop_start_beat=1.0,
                loop_end_beat=2.5,
            )
        }
    )

    save_result = viewmodel.save_project()

    assert save_result is not None
    assert save_result.is_ok()
    assert project_service.saved_snapshots
    snapshot = project_service.saved_snapshots[-1]
    assert snapshot.input_path == input_path
    assert snapshot.pitch_list == conversion_result.used_pitches
    assert snapshot.pitch_entries == conversion_result.used_pitches
    assert "arranged" in snapshot.preview_settings
    saved_preview = snapshot.preview_settings["arranged"]
    assert saved_preview.tempo_bpm == pytest.approx(102.0)
    assert saved_preview.loop_enabled is True
    assert saved_preview.loop_start_beat == pytest.approx(1.0)
    assert saved_preview.loop_end_beat == pytest.approx(2.5)
    assert project_service.last_destination == tmp_path / "project.ocarina"
    assert viewmodel.state.status_message == "Project saved."
    assert viewmodel.state.project_path == str(tmp_path / "project.ocarina")
    assert snapshot.settings.grace_settings == grace_settings.normalized()
    assert snapshot.grace_settings == grace_settings.normalized()


def test_load_project_updates_state(tmp_path: Path, conversion_result: ConversionResult) -> None:
    dialogs = FakeDialogs()
    project_service = StubProjectService()
    project_service.load_result = _make_loaded_project(tmp_path, conversion_result)
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService(), project_service=project_service)

    result = viewmodel.load_project_from(str(project_service.load_result.archive_path))

    assert result.is_ok()
    loaded = result.unwrap()
    state = viewmodel.state
    assert state.input_path == str(loaded.input_path)
    assert state.prefer_mode == "lydian"
    assert state.range_min == "C4"
    assert state.range_max == "C6"
    assert state.prefer_flats is False
    assert state.collapse_chords is False
    assert state.favor_lower is True
    assert state.transpose_offset == 1
    assert state.instrument_id == "alto"
    assert state.selected_part_ids == ("P2",)
    assert state.pitch_list == ["C4", "D4"]
    assert viewmodel.pitch_entries() == ["C4", "D4"]
    assert viewmodel.state.status_message == "Project loaded."
    assert state.project_path == str(loaded.archive_path)
    assert "arranged" in state.preview_settings
    restored_preview = state.preview_settings["arranged"]
    assert restored_preview.tempo_bpm == pytest.approx(88.0)
    assert restored_preview.metronome_enabled is True
    assert state.grace_settings == loaded.settings.grace_settings


def test_load_project_failure(tmp_path: Path) -> None:
    dialogs = FakeDialogs()
    project_service = StubProjectService(load_error=RuntimeError("boom"))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService(), project_service=project_service)

    result = viewmodel.load_project_from(str(tmp_path / "missing.ocarina"))

    assert result.is_err()
    assert "boom" in result.error


def test_browse_for_input_clears_project_path(tmp_path: Path) -> None:
    source = tmp_path / "existing.musicxml"
    source.write_text("<score/>", encoding="utf-8")
    dialogs = FakeDialogs(open_path=str(source))
    viewmodel = MainViewModel(dialogs=dialogs, score_service=StubScoreService())
    viewmodel.state.input_path = "previous.musicxml"
    viewmodel.state.project_path = str(tmp_path / "previous.ocarina")

    changed = viewmodel.browse_for_input()

    assert changed is True
    assert viewmodel.state.input_path == str(source)
    assert viewmodel.state.project_path == ""
