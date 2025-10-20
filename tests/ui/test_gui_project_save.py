from __future__ import annotations

import pytest

from shared.result import Result
from ocarina_gui.constants import APP_TITLE


@pytest.mark.gui
def test_save_project_command_syncs_manual_transpose(gui_app, tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "score.musicxml"
    input_path.write_text("<score/>", encoding="utf-8")
    gui_app.input_path.set(str(input_path))
    gui_app._viewmodel.state.input_path = str(input_path)
    gui_app._viewmodel.state.transpose_offset = 0
    gui_app._transpose_applied_offset = 6
    gui_app.transpose_offset.set(6)
    gui_app._preview_applied_settings["arranged"] = {
        "tempo": 92.0,
        "metronome": True,
        "loop_enabled": True,
        "loop_start": 1.0,
        "loop_end": 4.0,
    }

    captured: dict[str, object] = {}

    def fake_save_project() -> Result[str, str]:
        captured["transpose_offset"] = gui_app._viewmodel.state.transpose_offset
        preview_settings = gui_app._viewmodel.state.preview_settings
        captured["preview_settings"] = preview_settings
        destination = tmp_path / "project.ocarina"
        gui_app._viewmodel.state.project_path = str(destination)
        return Result.ok(str(destination))

    monkeypatch.setattr(gui_app._viewmodel, "save_project", fake_save_project)
    monkeypatch.setattr("ocarina_gui.preferences.save_preferences", lambda *_args, **_kwargs: None)

    gui_app._save_project_command()

    assert captured["transpose_offset"] == 6
    preview_settings = captured["preview_settings"]
    assert "arranged" in preview_settings
    arranged_snapshot = preview_settings["arranged"]
    assert arranged_snapshot.loop_enabled is True
    assert arranged_snapshot.loop_end_beat == pytest.approx(4.0)
    assert gui_app._viewmodel.state.project_path.endswith("project.ocarina")
    assert getattr(gui_app, "_current_window_title", "") == f"{APP_TITLE} – project.ocarina"
