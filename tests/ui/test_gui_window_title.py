from __future__ import annotations

import pytest

from ocarina_gui.constants import APP_TITLE


@pytest.mark.gui
def test_window_title_reflects_input_path(gui_app, tmp_path) -> None:
    path = tmp_path / "example.musicxml"
    path.write_text("<score/>", encoding="utf-8")

    gui_app.input_path.set(str(path))
    gui_app.update_idletasks()

    expected = f"{APP_TITLE} – {path.name}"
    assert getattr(gui_app, "_current_window_title", "") == expected
