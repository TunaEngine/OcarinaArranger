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
