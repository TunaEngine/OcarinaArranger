from __future__ import annotations

import tkinter as tk
from unittest.mock import patch

import pytest

from ocarina_gui import themes
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
    Selection,
    SelectionKind,
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
def test_instrument_layout_canvas_responds_to_theme_changes() -> None:
    root: tk.Tk | None = None
    canvas: InstrumentLayoutCanvas | None = None
    original_theme = themes.get_current_theme_id()
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
        state.selection = Selection(SelectionKind.HOLE, 0)
        canvas.render(state, high_quality=False)

        palette = themes.get_current_theme().palette.layout_editor
        assert canvas.cget("background").lower() == palette.workspace_background.lower()

        items = canvas.find_all()
        background_rect = next(
            item
            for item in items
            if canvas.type(item) == "rectangle"
            and canvas.itemcget(item, "outline") == ""
        )
        assert canvas.itemcget(background_rect, "fill").lower() == palette.instrument_surface.lower()
        line_id = next(item for item in items if canvas.type(item) == "line")
        assert canvas.itemcget(line_id, "fill").lower() == palette.grid_line.lower()

        hole_id = next(item for item in items if canvas.type(item) == "oval")
        assert canvas.itemcget(hole_id, "outline").lower() == palette.hole_outline.lower()
        assert canvas.itemcget(hole_id, "fill").lower() == palette.hole_fill.lower()

        handle_id = next(
            item
            for item, info in canvas._item_lookup.items()  # type: ignore[attr-defined]
            if info[0] is SelectionKind.OUTLINE
        )
        assert canvas.itemcget(handle_id, "fill").lower() == palette.handle_fill.lower()
        assert canvas.itemcget(handle_id, "outline").lower() == palette.handle_outline.lower()

        indicator_id = canvas._selection_indicator  # type: ignore[attr-defined]
        assert indicator_id is not None
        assert canvas.itemcget(indicator_id, "outline").lower() == palette.selection_outline.lower()

        target_theme = "dark" if themes.get_current_theme_id() != "dark" else "light"
        themes.set_active_theme(target_theme)
        root.update_idletasks()

        updated = themes.get_current_theme().palette.layout_editor
        assert canvas.cget("background").lower() == updated.workspace_background.lower()
        new_line_id = next(item for item in canvas.find_all() if canvas.type(item) == "line")
        assert canvas.itemcget(new_line_id, "fill").lower() == updated.grid_line.lower()
        new_rect = next(
            item
            for item in canvas.find_all()
            if canvas.type(item) == "rectangle" and canvas.itemcget(item, "outline") == ""
        )
        assert canvas.itemcget(new_rect, "fill").lower() == updated.instrument_surface.lower()
    finally:
        if canvas is not None:
            canvas.destroy()
        if root is not None:
            root.destroy()
        themes.set_active_theme(original_theme)


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

