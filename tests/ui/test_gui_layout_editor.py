from __future__ import annotations

from types import MethodType

import pytest
import tkinter as tk


# The GUI fixture withdraws the root window to keep the real UI hidden during the
# tests. ``open_instrument_layout_editor`` now temporarily deiconifies the root on
# Windows so the footer hierarchy can map correctly before we assert on geometry.


def _wait_for_widget_mapping(host: tk.Misc, widget: tk.Misc, *, attempts: int = 20) -> None:
    """Ensure ``widget`` is mapped before continuing assertions."""

    for _ in range(attempts):
        try:
            host.update()
            host.update_idletasks()
        except tk.TclError:
            break
        if widget.winfo_ismapped():
            return
    pytest.fail(f"Widget {widget} never became mapped")


def test_layout_editor_window_opens(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()

    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None
    assert editor.winfo_exists()
    assert "Instrument Layout Editor" in str(editor.title())

    canvas = getattr(editor, "canvas", None)
    assert canvas is not None
    assert int(canvas.winfo_width()) > 0

    preview_frame = getattr(editor, "_preview_frame", None)
    assert preview_frame is not None
    assert not bool(preview_frame.winfo_ismapped())

    editor.destroy()


def test_layout_editor_close_callback_invoked_once(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    calls = 0

    def _callback() -> None:
        nonlocal calls
        calls += 1

    editor._on_close = _callback  # type: ignore[attr-defined]
    editor.destroy()
    gui_app.update_idletasks()

    assert calls == 1


def test_layout_editor_done_button_visible_when_narrow(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    editor.update()
    editor.geometry("360x600")
    editor.update()
    editor.update_idletasks()

    button_row = getattr(editor, "_footer_button_row", None)
    export_row = getattr(editor, "_footer_export_row", None)
    actions_row = getattr(editor, "_footer_actions_row", None)
    done_button = getattr(editor, "_done_button", None)
    assert done_button is not None
    cancel_button = getattr(editor, "_cancel_button", None)
    toggle_button = getattr(editor, "_preview_toggle", None)
    assert button_row is not None
    assert export_row is not None
    assert actions_row is not None
    assert cancel_button is not None
    assert toggle_button is not None

    _wait_for_widget_mapping(editor, button_row)

    # Mimic the constrained Windows layout where the footer needs to stack the
    # export and action rows vertically to stay visible.
    monkeypatch.setattr(button_row, "winfo_width", lambda: 240)
    monkeypatch.setattr(button_row, "winfo_reqwidth", lambda: 240)
    monkeypatch.setattr(export_row, "winfo_reqwidth", lambda: 180)
    monkeypatch.setattr(actions_row, "winfo_reqwidth", lambda: 220)

    for widget, width in (
        (toggle_button, 140),
        (cancel_button, 110),
        (done_button, 110),
    ):
        monkeypatch.setattr(widget, "winfo_reqwidth", lambda w=width: w)

    editor._refresh_footer_layout()
    editor.update()
    editor.update_idletasks()

    _wait_for_widget_mapping(editor, done_button)

    assert bool(done_button.winfo_ismapped())

    window_left = editor.winfo_rootx()
    window_right = window_left + editor.winfo_width()
    button_left = done_button.winfo_rootx()
    button_right = button_left + done_button.winfo_width()

    assert window_left <= button_left <= button_right <= window_right

    assert bool(cancel_button.winfo_ismapped())
    assert bool(toggle_button.winfo_ismapped())

    editor.destroy()


def test_layout_editor_footer_stacks_buttons_when_space_is_constrained(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    editor.update()
    editor.geometry("360x600")
    editor.update()
    editor.update_idletasks()

    button_row = getattr(editor, "_footer_button_row", None)
    assert button_row is not None

    toggle_button = getattr(editor, "_preview_toggle", None)
    cancel_button = getattr(editor, "_cancel_button", None)
    done_button = getattr(editor, "_done_button", None)
    export_row = getattr(editor, "_footer_export_row", None)
    actions_row = getattr(editor, "_footer_actions_row", None)
    status_label = getattr(editor, "_footer_status_label", None)
    assert toggle_button is not None
    assert cancel_button is not None
    assert done_button is not None
    assert export_row is not None
    assert actions_row is not None
    assert status_label is not None

    _wait_for_widget_mapping(editor, button_row)

    # Simulate the tighter layout reported on Windows by constraining the row's
    # width so the footer has to stack the actions beneath the export controls
    # and the action buttons themselves request more space than is available.
    monkeypatch.setattr(button_row, "winfo_width", lambda: 220)
    monkeypatch.setattr(button_row, "winfo_reqwidth", lambda: 220)
    monkeypatch.setattr(export_row, "winfo_reqwidth", lambda: 180)
    monkeypatch.setattr(actions_row, "winfo_reqwidth", lambda: 360)

    for widget, width in (
        (toggle_button, 150),
        (cancel_button, 110),
        (done_button, 110),
    ):
        monkeypatch.setattr(widget, "winfo_reqwidth", lambda w=width: w)

    editor._refresh_footer_layout()
    editor.update()
    editor.update_idletasks()

    _wait_for_widget_mapping(editor, done_button)

    assert bool(done_button.winfo_ismapped())
    assert bool(cancel_button.winfo_ismapped())
    assert bool(toggle_button.winfo_ismapped())

    assert int(export_row.grid_info()["row"]) == 0
    assert int(actions_row.grid_info()["row"]) == 1
    assert int(status_label.grid_info()["row"]) == 2

    assert int(toggle_button.grid_info()["row"]) == 0
    assert int(cancel_button.grid_info()["row"]) == 1
    assert int(done_button.grid_info()["row"]) == 2

    editor.destroy()


def test_layout_editor_footer_recovers_when_buttons_unmapped(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    editor.update()
    editor.geometry("360x600")
    editor.update()
    editor.update_idletasks()

    button_row = getattr(editor, "_footer_button_row", None)
    export_row = getattr(editor, "_footer_export_row", None)
    actions_row = getattr(editor, "_footer_actions_row", None)
    status_label = getattr(editor, "_footer_status_label", None)
    toggle_button = getattr(editor, "_preview_toggle", None)
    cancel_button = getattr(editor, "_cancel_button", None)
    done_button = getattr(editor, "_done_button", None)
    assert button_row is not None
    assert export_row is not None
    assert actions_row is not None
    assert status_label is not None
    assert toggle_button is not None
    assert cancel_button is not None
    assert done_button is not None

    # Measurements underestimate the space requirements so the footer believes a
    # horizontal layout is viable even though the platform later unmaps widgets.
    monkeypatch.setattr(button_row, "winfo_width", lambda: 320)
    monkeypatch.setattr(button_row, "winfo_reqwidth", lambda: 320)
    monkeypatch.setattr(export_row, "winfo_reqwidth", lambda: 120)
    monkeypatch.setattr(actions_row, "winfo_reqwidth", lambda: 150)

    mapped_state = {"value": True}
    forced_state = {"called": False}

    original_force = editor._force_footer_stack_layout

    def _wrapped_force(self, button_row, export_row, actions_row, status_label, *, force=False):
        if force:
            forced_state["called"] = True
        mapped_state["value"] = True
        original_force(button_row, export_row, actions_row, status_label, force=force)

    monkeypatch.setattr(
        editor,
        "_force_footer_stack_layout",
        MethodType(_wrapped_force, editor),
    )

    for widget, width in (
        (toggle_button, 60),
        (cancel_button, 60),
        (done_button, 60),
    ):
        monkeypatch.setattr(widget, "winfo_reqwidth", lambda w=width: w)

    monkeypatch.setattr(done_button, "winfo_ismapped", lambda: int(mapped_state["value"]))

    editor._refresh_footer_layout()
    editor.update()
    editor.update_idletasks()

    # Emulate Tk unmapping the Done button because the available width was
    # tighter than our measurements reported.
    mapped_state["value"] = False
    done_button.grid_remove()
    editor.update()
    editor.update_idletasks()

    editor._refresh_footer_layout()
    editor.update()
    editor.update_idletasks()

    assert bool(done_button.winfo_ismapped())
    assert bool(cancel_button.winfo_ismapped())
    assert bool(toggle_button.winfo_ismapped())
    assert forced_state["called"] is True


def test_layout_editor_footer_returns_to_horizontal_when_space_recovers(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    editor.update()
    editor.geometry("360x600")
    editor.update()
    editor.update_idletasks()

    button_row = getattr(editor, "_footer_button_row", None)
    export_row = getattr(editor, "_footer_export_row", None)
    actions_row = getattr(editor, "_footer_actions_row", None)
    toggle_button = getattr(editor, "_preview_toggle", None)
    cancel_button = getattr(editor, "_cancel_button", None)
    done_button = getattr(editor, "_done_button", None)
    assert button_row is not None
    assert export_row is not None
    assert actions_row is not None
    assert toggle_button is not None
    assert cancel_button is not None
    assert done_button is not None

    width_state = {"value": 220}

    monkeypatch.setattr(button_row, "winfo_width", lambda: width_state["value"])
    monkeypatch.setattr(button_row, "winfo_reqwidth", lambda: width_state["value"])
    monkeypatch.setattr(export_row, "winfo_reqwidth", lambda: 180)
    monkeypatch.setattr(actions_row, "winfo_reqwidth", lambda: 360)

    for widget, width in (
        (toggle_button, 150),
        (cancel_button, 110),
        (done_button, 110),
    ):
        monkeypatch.setattr(widget, "winfo_reqwidth", lambda w=width: w)

    editor._refresh_footer_layout()
    editor.update()
    editor.update_idletasks()

    assert int(actions_row.grid_info()["row"]) == 1
    assert editor._footer_layout_stacked is True

    width_state["value"] = 620
    monkeypatch.setattr(actions_row, "winfo_reqwidth", lambda: 260)

    editor._refresh_footer_layout()
    editor.update_idletasks()
    editor.update()

    assert int(actions_row.grid_info()["row"]) == 0
    assert editor._footer_layout_stacked is False
    assert editor._footer_actions_vertical is False

    editor.destroy()
