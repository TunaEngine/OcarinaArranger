from __future__ import annotations

import tkinter as tk
from unittest.mock import patch

import pytest

from ocarina_gui.fingering.outline_renderer import OutlineImage
from ocarina_gui.layout_editor.fingering_pattern_canvas import (
    FingeringPatternCanvas,
)
from ocarina_gui.layout_editor.instrument_layout_canvas import (
    InstrumentLayoutCanvas,
)
from viewmodels.instrument_layout_editor.models import (
    EditableHole,
    EditableStyle,
    InstrumentLayoutState,
    OutlinePoint,
)


def _build_state() -> InstrumentLayoutState:
    style = EditableStyle(
        background_color="#ffffff",
        outline_color="#222222",
        outline_width=2.0,
        outline_smooth=True,
        outline_spline_steps=48,
        hole_outline_color="#111111",
        covered_fill_color="#555555",
    )
    return InstrumentLayoutState(
        instrument_id="test",
        name="Test",
        title="Test",
        canvas_width=120,
        canvas_height=80,
        holes=[EditableHole(identifier="h1", x=40, y=40, radius=10)],
        windways=[],
        outline_points=[
            OutlinePoint(x=10, y=10),
            OutlinePoint(x=110, y=10),
            OutlinePoint(x=110, y=70),
        ],
        outline_closed=False,
        style=style,
    )


def _outline_image(master: tk.Misc, width: int, height: int) -> OutlineImage:
    return OutlineImage(
        photo_image=tk.PhotoImage(master=master, width=width, height=height),
        width=width,
        height=height,
    )


@pytest.mark.gui
def test_instrument_layout_canvas_reuses_cached_outline_image() -> None:
    root: tk.Tk | None = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        canvas = InstrumentLayoutCanvas(
            root,
            on_select=lambda *_args: None,
            on_move=lambda *_args: None,
        )
        state = _build_state()
        total_width = state.canvas_width + 2 * canvas._margin  # type: ignore[attr-defined]
        total_height = state.canvas_height + 2 * canvas._margin  # type: ignore[attr-defined]
        cached_image = _outline_image(canvas, total_width, total_height)

        with patch(
            "ocarina_gui.layout_editor.instrument_layout_canvas.render_outline_photoimage",
            return_value=cached_image,
        ) as render_mock:
            canvas.render(state)
            assert render_mock.call_count == 1

            canvas.render(state)
            assert render_mock.call_count == 1
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_fingering_pattern_canvas_reuses_cached_outline_image() -> None:
    root: tk.Tk | None = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        canvas = FingeringPatternCanvas(root, on_toggle=lambda *_args: True)
        state = _build_state()
        total_width = state.canvas_width + 2 * canvas._margin  # type: ignore[attr-defined]
        total_height = state.canvas_height + 2 * canvas._margin  # type: ignore[attr-defined]
        cached_image = _outline_image(canvas, total_width, total_height)

        with patch(
            "ocarina_gui.layout_editor.fingering_pattern_canvas.render_outline_photoimage",
            return_value=cached_image,
        ) as render_mock:
            canvas.render(state, [2])
            assert render_mock.call_count == 1

            canvas.render(state, [2])
            assert render_mock.call_count == 1
    finally:
        if root is not None:
            root.destroy()

