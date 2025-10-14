from __future__ import annotations

import pytest


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


def test_layout_editor_done_button_visible_when_narrow(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("requires Tk display")

    gui_app.open_instrument_layout_editor()
    editor = getattr(gui_app, "_layout_editor_window", None)
    assert editor is not None

    editor.geometry("360x600")
    editor.update_idletasks()

    done_button = getattr(editor, "_done_button", None)
    assert done_button is not None
    assert bool(done_button.winfo_ismapped())

    window_left = editor.winfo_rootx()
    window_right = window_left + editor.winfo_width()
    button_left = done_button.winfo_rootx()
    button_right = button_left + done_button.winfo_width()

    assert window_left <= button_left <= button_right <= window_right

    actions_frame = done_button.master
    assert actions_frame is not None
    top_row = actions_frame.master
    assert top_row is not None
    export_row = next(child for child in top_row.winfo_children() if child is not actions_frame)
    export_buttons = export_row.winfo_children()
    assert export_buttons, "expected export buttons in the layout editor footer"
    first_export_button = export_buttons[0]

    assert abs(first_export_button.winfo_rooty() - done_button.winfo_rooty()) <= 2

    cancel_button = getattr(editor, "_cancel_button", None)
    assert cancel_button is not None
    toggle_button = getattr(editor, "_preview_toggle", None)
    assert toggle_button is not None

    assert done_button.winfo_rootx() > cancel_button.winfo_rootx() > toggle_button.winfo_rootx()

    editor.destroy()
