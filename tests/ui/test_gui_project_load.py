from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import TransformSettings
from services.project_service import LoadedProject, PreviewPlaybackSnapshot
from shared.result import Result


def _loaded_project(tmp_path: Path) -> LoadedProject:
    archive = tmp_path / "song.ocarina"
    working = tmp_path / "workspace"
    input_path = working / "original" / "score.musicxml"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("<score/>", encoding="utf-8")
    return LoadedProject(
        archive_path=archive,
        working_directory=working,
        input_path=input_path,
        settings=TransformSettings(
            prefer_mode="auto",
            range_min="A4",
            range_max="F6",
            prefer_flats=True,
            collapse_chords=True,
            favor_lower=False,
            transpose_offset=-4,
            instrument_id="",
        ),
        pdf_options=PdfExportOptions.with_defaults(),
        pitch_list=["A4"],
        pitch_entries=["A4"],
        status_message="Loaded",
        conversion=None,
        preview_settings={
            "arranged": PreviewPlaybackSnapshot(
                tempo_bpm=84.0,
                metronome_enabled=True,
                loop_enabled=True,
                loop_start_beat=1.0,
                loop_end_beat=3.5,
            )
        },
    )


@pytest.mark.gui
def test_open_project_restores_manual_transpose(gui_app, tmp_path, monkeypatch) -> None:
    loaded = _loaded_project(tmp_path)
    def fake_open_project() -> Result[LoadedProject, str]:
        gui_app._viewmodel._apply_loaded_project(loaded)
        return Result.ok(loaded)

    monkeypatch.setattr(gui_app._viewmodel, "open_project", fake_open_project)
    monkeypatch.setattr("ocarina_gui.preferences.save_preferences", lambda *_args, **_kwargs: None)

    gui_app._open_project_command()

    assert gui_app.transpose_offset.get() == -4
    assert gui_app._transpose_applied_offset == -4
    assert gui_app._viewmodel.state.transpose_offset == -4
    arranged_snapshot = gui_app._viewmodel.state.preview_settings.get("arranged")
    assert arranged_snapshot is not None
    assert arranged_snapshot.tempo_bpm == pytest.approx(84.0)
    assert gui_app._preview_tempo_vars["arranged"].get() == pytest.approx(84.0)
    assert gui_app._preview_metronome_vars["arranged"].get() is True
    assert gui_app._preview_loop_start_vars["arranged"].get() == pytest.approx(1.0)
    assert gui_app._preview_loop_end_vars["arranged"].get() == pytest.approx(3.5)
    assert getattr(gui_app, "_preview_selected_side", None) == "arranged"


@pytest.mark.gui
def test_open_recent_project_selects_arranged(gui_app, tmp_path, monkeypatch) -> None:
    loaded = _loaded_project(tmp_path)

    def fake_load_project_from(path: str, extract_dir=None):
        assert path
        gui_app._viewmodel._apply_loaded_project(loaded)
        return Result.ok(loaded)

    monkeypatch.setattr(gui_app._viewmodel, "load_project_from", fake_load_project_from)
    monkeypatch.setattr("ocarina_gui.preferences.save_preferences", lambda *_args, **_kwargs: None)
    gui_app._preview_selected_side = "original"

    gui_app._load_project_from_path(str(tmp_path / "recent.ocarina"))

    assert getattr(gui_app, "_preview_selected_side", None) == "arranged"


@pytest.mark.gui
def test_open_recent_project_rerenders_arranged_when_already_selected(
    gui_app, tmp_path, monkeypatch
) -> None:
    loaded = _loaded_project(tmp_path)

    def fake_load_project_from(path: str, extract_dir=None):
        gui_app._viewmodel._apply_loaded_project(loaded)
        return Result.ok(loaded)

    monkeypatch.setattr(gui_app._viewmodel, "load_project_from", fake_load_project_from)
    monkeypatch.setattr("ocarina_gui.preferences.save_preferences", lambda *_args, **_kwargs: None)
    calls: list[object] = []

    def fake_auto_render(tab: object) -> None:
        calls.append(tab)
        assert gui_app._preview_auto_rendered is False
        gui_app._preview_auto_rendered = True

    monkeypatch.setattr(gui_app, "_auto_render_preview", fake_auto_render)
    gui_app._preview_selected_side = "arranged"
    gui_app._preview_auto_rendered = True

    gui_app._load_project_from_path(str(tmp_path / "another.ocarina"))

    expected = gui_app._preview_frame_for_side("arranged")
    assert calls == [expected]
