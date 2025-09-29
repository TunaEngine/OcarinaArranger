from __future__ import annotations

import pytest

from helpers import make_linear_score

from tests.ui._preview_helpers import write_score


def test_original_preview_initializes_on_demand(gui_app, tmp_path):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Requires Tk preview widgets")

    notebook = gui_app._notebook
    preview_tabs = gui_app._preview_tab_frames
    if notebook is None or not preview_tabs:
        pytest.skip("Preview tabs not available in this environment")

    assert gui_app.roll_orig is None
    assert gui_app.staff_orig is None

    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    assert gui_app.roll_orig is None
    assert gui_app.staff_orig is None
    orig_playback = gui_app._preview_playback["original"]
    arr_playback = gui_app._preview_playback["arranged"]
    assert not orig_playback.state.is_loaded
    assert arr_playback.state.is_loaded

    notebook.select(preview_tabs[0])
    gui_app.update_idletasks()

    assert gui_app.roll_orig is not None
    assert getattr(gui_app.roll_orig, "_cached", None) is not None
    assert gui_app.staff_orig is not None
    assert getattr(gui_app.staff_orig, "_cached", None) is not None
    assert orig_playback.state.is_loaded
