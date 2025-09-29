from __future__ import annotations

import pytest
import tkinter as tk
from tkinter import messagebox

from helpers import make_linear_score

from tests.ui._preview_helpers import write_score


pytestmark = pytest.mark.usefixtures("ensure_original_preview")


def test_render_previews_updates_status_and_caches(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: errors.append((args, kwargs)))
    gui_app.render_previews()
    gui_app.update_idletasks()
    assert not errors
    assert gui_app.status.get() == "Preview rendered."
    assert gui_app.roll_orig._cached is not None
    assert gui_app.roll_arr._cached is not None
    assert gui_app.staff_orig._cached is not None
    assert gui_app.staff_arr._cached is not None


def test_import_auto_renders_and_selects_arranged_tab(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)

    calls: list[str] = []
    original_render = gui_app.render_previews

    def _tracked_render():
        calls.append(gui_app.input_path.get())
        return original_render()

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.input_path.set(str(path))
    gui_app.update_idletasks()

    assert calls == [str(path)]

    notebook = gui_app._notebook
    preview_tabs = gui_app._preview_tab_frames
    if notebook is None or not preview_tabs:
        pytest.skip("Preview tabs not available in headless mode")

    selected = notebook.nametowidget(notebook.select())
    assert selected is preview_tabs[1]

    notebook.select(preview_tabs[0])
    gui_app.update_idletasks()
    notebook.select(preview_tabs[1])
    gui_app.update_idletasks()

    assert calls == [str(path)]


def test_auto_render_suppresses_preview_error_dialog(gui_app, tmp_path, monkeypatch):
    path = tmp_path / "invalid.musicxml"
    path.write_text("not xml", encoding="utf-8")

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _record_showerror(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(messagebox, "showerror", _record_showerror)

    gui_app.input_path.set(str(path))
    gui_app.update_idletasks()

    assert not calls
    assert gui_app.status.get() == "Preview failed."

    gui_app.render_previews()
    gui_app.update_idletasks()

    assert calls
    args, _ = calls[-1]
    assert args[0] == "Preview failed"
    assert "syntax error" in str(args[1])


def test_preview_tab_does_not_auto_render_without_file(gui_app, monkeypatch):
    calls = []

    def _tracked_render():
        calls.append(True)

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    notebook = gui_app._notebook
    if notebook is None:
        pytest.skip("Notebook not available in headless mode")
    preview_tabs = gui_app._preview_tab_frames
    if not preview_tabs:
        pytest.skip("Preview tabs not available in headless mode")

    notebook.select(preview_tabs[0])
    gui_app.update_idletasks()
    assert not calls


def test_preview_auto_render_resets_after_input_change(gui_app, tmp_path, monkeypatch):
    tree1, _ = make_linear_score()
    path1 = write_score(tmp_path, tree1, name="first.musicxml")
    tree2, _ = make_linear_score()
    path2 = write_score(tmp_path, tree2, name="second.musicxml")

    calls: list[str] = []
    original_render = gui_app.render_previews

    def _tracked_render() -> None:
        calls.append(gui_app.input_path.get())
        return original_render()

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    gui_app.input_path.set(str(path1))
    gui_app._auto_render_preview(None)
    assert calls and calls[-1] == str(path1)

    gui_app.input_path.set(str(path2))
    gui_app._auto_render_preview(None)

    assert len(calls) == 2
    assert calls[-1] == str(path2)

@pytest.mark.skip(reason="Temporarily? disabled")
def test_reimport_button_enables_after_option_change(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.update_idletasks()

    button = getattr(gui_app, "_reimport_button", None)
    if button is None:
        pytest.skip("Re-import button not available in this environment")

    assert "disabled" not in button.state()

    gui_app.prefer_flats.set(not bool(gui_app.prefer_flats.get()))
    gui_app.update_idletasks()

    calls: list[str] = []
    original_render = gui_app.render_previews

    def _tracked_render():
        calls.append("render")
        return original_render()

    monkeypatch.setattr(gui_app, "render_previews", _tracked_render)

    button.invoke()
    gui_app.update_idletasks()

    notebook = gui_app._notebook
    preview_tabs = gui_app._preview_tab_frames
    if notebook is None or not preview_tabs:
        pytest.skip("Preview tabs not available in this environment")

    selected = notebook.nametowidget(notebook.select())
    assert selected is preview_tabs[1]

    assert calls == ["render"]
    assert "disabled" in button.state()


def test_reimport_button_stays_enabled_when_file_changes(gui_app, tmp_path):
    tree1, _ = make_linear_score()
    path1 = write_score(tmp_path, tree1, name="first.musicxml")
    tree2, _ = make_linear_score()
    path2 = write_score(tmp_path, tree2, name="second.musicxml")

    gui_app.input_path.set(str(path1))
    gui_app.update_idletasks()

    button = getattr(gui_app, "_reimport_button", None)
    if button is None:
        pytest.skip("Re-import button not available in this environment")

    gui_app.prefer_flats.set(not bool(gui_app.prefer_flats.get()))
    gui_app.update_idletasks()

    assert "disabled" not in button.state()

    gui_app.input_path.set(str(path2))
    gui_app.update_idletasks()

    assert "disabled" not in button.state()


def test_reimport_button_available_without_option_changes(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    button = getattr(gui_app, "_reimport_button", None)
    if button is None:
        pytest.skip("Re-import button not available in this environment")

    assert "disabled" not in button.state()

    button.invoke()
    gui_app.update_idletasks()

    assert "disabled" not in button.state()


def test_reimport_button_enables_without_preview_tab_initialized(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)

    # Simulate the desktop UI where preview tabs are created lazily.
    gui_app._preview_tab_initialized.clear()
    gui_app.roll_orig = None
    gui_app.roll_arr = None
    gui_app.staff_orig = None
    gui_app.staff_arr = None

    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    button = getattr(gui_app, "_reimport_button", None)
    if button is None:
        pytest.skip("Re-import button not available in this environment")

    assert not gui_app._preview_initial_loading
    assert "disabled" not in button.state()


def test_auto_scroll_mode_menu_updates_rolls(gui_app, ensure_original_preview):
    gui_app._ensure_preview_tab_initialized("arranged")
    gui_app.update_idletasks()

    roll = gui_app.roll_arr
    assert roll is not None

    gui_app._apply_auto_scroll_mode("continuous")
    gui_app.update_idletasks()
    mode_attr = getattr(roll, "_auto_scroll_mode", None)
    if mode_attr is not None and hasattr(mode_attr, "value"):
        current = mode_attr.value
    else:
        current = getattr(roll, "auto_scroll_mode", None)
    assert current == "continuous"
    assert gui_app._preferences.auto_scroll_mode == "continuous"
    assert gui_app._auto_scroll_mode.get() == "continuous"

    gui_app._apply_auto_scroll_mode("flip")
    gui_app.update_idletasks()
    mode_attr = getattr(roll, "_auto_scroll_mode", None)
    if mode_attr is not None and hasattr(mode_attr, "value"):
        current = mode_attr.value
    else:
        current = getattr(roll, "auto_scroll_mode", None)
    assert current == "flip"
    assert gui_app._preferences.auto_scroll_mode == "flip"
    assert gui_app._auto_scroll_mode.get() == "flip"


def test_reimport_button_tracks_manual_transpose(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.update_idletasks()

    button = getattr(gui_app, "_reimport_button", None)
    if button is None:
        pytest.skip("Re-import button not available in this environment")

    assert "disabled" not in button.state()

    base_value = int(gui_app.transpose_offset.get())
    if base_value < 12:
        new_value = base_value + 1
    else:
        new_value = base_value - 1

    gui_app.transpose_offset.set(new_value)
    gui_app.update_idletasks()

    assert "disabled" not in button.state()

    gui_app.transpose_offset.set(base_value)
    gui_app.update_idletasks()

    assert "disabled" not in button.state()


def test_render_previews_shows_initial_loading_indicator(gui_app, tmp_path, monkeypatch):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    original_render = gui_app._viewmodel.render_previews
    call_order: list[str] = []

    original_update = gui_app.update_idletasks

    def _tracked_update() -> None:
        call_order.append("update_idletasks")
        original_update()

    monkeypatch.setattr(gui_app, "update_idletasks", _tracked_update)

    def _tracked_render():
        call_order.append("render")
        assert call_order[0] == "update_idletasks"
        assert gui_app._preview_initial_loading == {"original", "arranged"}
        label = gui_app._preview_render_progress_labels["original"]
        assert label.get() == "Loading preview… 0%"
        return original_render()

    monkeypatch.setattr(gui_app._viewmodel, "render_previews", _tracked_render)

    gui_app.render_previews()
    gui_app.update_idletasks()

    assert not gui_app._preview_initial_loading


def test_preview_apply_shows_progress_indicator(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    tempo_var = gui_app._preview_tempo_vars["original"]
    apply_button = gui_app._preview_apply_buttons["original"]
    progress_frame = gui_app._preview_progress_frames["original"]
    renderer = gui_app._test_audio_renderers["original"]
    renderer.auto_complete_render = False

    tempo_var.set(160.0)
    gui_app.update_idletasks()
    apply_button.invoke()
    gui_app.update()

    assert progress_frame.winfo_manager()

    # Emit small progress first to ensure fractional percentages are surfaced.
    renderer.emit_progress(0.005)
    gui_app.update()

    label = gui_app._preview_render_progress_labels["original"]
    assert label.get() == "0.5%"

    # Subsequent larger updates should continue to refresh the label.
    renderer.emit_progress(0.5)
    gui_app.update()

    assert label.get() == "50%"

    renderer.finish_render()
    gui_app.update()
    gui_app.update()

    assert not progress_frame.winfo_manager()


def test_initial_preview_render_shows_progress_indicator(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))

    original_renderer = gui_app._test_audio_renderers["original"]
    arranged_renderer = gui_app._test_audio_renderers["arranged"]
    original_renderer.auto_complete_render = False
    arranged_renderer.auto_complete_render = False

    gui_app.render_previews()
    gui_app.update()

    progress_frame = gui_app._preview_progress_frames["original"]
    assert progress_frame.winfo_manager()

    original_renderer.finish_render()
    arranged_renderer.finish_render()
    gui_app.update()
    gui_app.update()

    assert not progress_frame.winfo_manager()


def test_time_zoom_keeps_roll_and_staff_synced(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    roll = gui_app.roll_orig
    staff = gui_app.staff_orig
    if roll is None or staff is None:
        pytest.skip("Preview widgets not available in headless mode")
    if not hasattr(roll, "px_per_tick") or not hasattr(staff, "px_per_tick"):
        pytest.skip("Preview widgets not available in headless mode")

    for _ in range(4):
        gui_app._hzoom_all(0.5)
    assert roll.px_per_tick == pytest.approx(staff.px_per_tick)

    for _ in range(3):
        gui_app._hzoom_all(1.5)
    assert roll.px_per_tick == pytest.approx(staff.px_per_tick)


def test_preview_scrollbars_have_matching_width(gui_app, tmp_path):
    tree, _ = make_linear_score()
    path = write_score(tmp_path, tree)
    gui_app.input_path.set(str(path))
    gui_app.render_previews()
    gui_app.update_idletasks()

    roll = gui_app.roll_orig
    staff = gui_app.staff_orig
    if roll is None or staff is None:
        pytest.skip("Preview widgets not available in headless mode")
    if not hasattr(roll, "hbar") or not hasattr(staff, "hbar"):
        pytest.skip("Preview widgets not available in headless mode")

    roll_width = roll.hbar.winfo_width()
    staff_width = staff.hbar.winfo_width()

    assert roll_width == staff_width

@pytest.mark.skip(reason="Temporarily? disabled")
def test_staff_only_layout_wraps_and_scrolls_vertically(gui_app):
    staff = getattr(gui_app, "staff_arr", None)
    if staff is None:
        pytest.skip("Staff view not available in this environment")
    if not hasattr(staff, "vbar") or not hasattr(staff, "hbar"):
        pytest.skip("Staff view requires Tk canvas widgets")

    gui_app.preview_layout_mode.set("staff")
    gui_app.update_idletasks()
    if hasattr(staff, "update_idletasks"):
        staff.update_idletasks()

    assert getattr(staff, "_layout_mode", None) == "wrapped"
    assert staff.vbar.winfo_ismapped()
    assert not staff.hbar.winfo_ismapped()


def test_preview_layout_mode_syncs_tabs(gui_app):
    staff_arr = getattr(gui_app, "staff_arr", None)
    if staff_arr is None or not hasattr(staff_arr, "set_layout_mode"):
        pytest.skip("Staff view requires Tk canvas widgets")

    gui_app.preview_layout_mode.set("staff")
    gui_app.update_idletasks()
    assert getattr(staff_arr, "_layout_mode", None) == "wrapped"

    ensure_tab = getattr(gui_app, "_ensure_preview_tab_initialized", None)
    if callable(ensure_tab):
        ensure_tab("original")
    gui_app.update_idletasks()

    staff_orig = getattr(gui_app, "staff_orig", None)
    if staff_orig is None or not hasattr(staff_orig, "_layout_mode"):
        pytest.skip("Staff view requires Tk canvas widgets")
    assert getattr(staff_orig, "_layout_mode", None) == "wrapped"

    gui_app.preview_layout_mode.set("piano_vertical")
    gui_app.update_idletasks()

    roll_arr = getattr(gui_app, "roll_arr", None)
    roll_orig = getattr(gui_app, "roll_orig", None)
    if (
        roll_arr is None
        or roll_orig is None
        or not hasattr(roll_arr, "_time_scroll_orientation")
        or not hasattr(roll_orig, "_time_scroll_orientation")
    ):
        pytest.skip("Piano roll requires Tk canvas widgets")

    assert roll_arr._time_scroll_orientation == "vertical"
    assert roll_orig._time_scroll_orientation == "vertical"


def test_destroy_clears_tk_variable_interpreters(gui_app):
    orphan = tk.StringVar(master=gui_app, value="orphaned")
    variables = gui_app._tk_variables()
    assert variables, "expected main window to expose Tk variables"
    assert orphan not in variables

    gui_app.destroy()

    for var in (*variables, orphan):
        assert getattr(var, "_tk", None) is None
