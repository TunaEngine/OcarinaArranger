import tkinter as tk

import pytest

from ocarina_gui import themes
from ocarina_gui.fingering.view import FingeringView


@pytest.mark.gui
def test_preview_hole_hitbox_covers_entire_circle():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    view: FingeringView | None = None
    try:
        view = FingeringView(root)
        root.update_idletasks()

        hole_tag = view._hole_tag(0)  # type: ignore[attr-defined]
        bbox = view.bbox(hole_tag)
        assert bbox is not None
        left, top, right, bottom = bbox
        center_x = (left + right) / 2

        def _has_hole_tag(items: tuple[int, ...]) -> bool:
            return any(hole_tag in view.gettags(item) for item in items)

        top_point = (center_x, top + 1)
        bottom_point = (center_x, bottom - 1)

        assert _has_hole_tag(
            view.find_overlapping(top_point[0], top_point[1], top_point[0], top_point[1])
        )
        assert _has_hole_tag(
            view.find_overlapping(
                bottom_point[0], bottom_point[1], bottom_point[0], bottom_point[1]
            )
        )
    finally:
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()


@pytest.mark.gui
def test_fingering_view_swaps_colors_in_dark_theme():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    original_theme = themes.get_current_theme_id()
    root.withdraw()
    default_view: FingeringView | None = None
    dark_view: FingeringView | None = None
    try:
        themes.set_active_theme("light")
        default_view = FingeringView(root)
        root.update_idletasks()
        style = default_view._instrument.style  # type: ignore[attr-defined]
        assert default_view.cget("background").lower() == style.background_color.lower()

        default_view.destroy()
        default_view = None

        themes.set_active_theme("dark")
        dark_view = FingeringView(root)
        root.update_idletasks()
        colors = dark_view._resolve_canvas_colors()  # type: ignore[attr-defined]
        assert dark_view.cget("background").lower() == colors.background.lower()
        assert colors.background.lower() == style.hole_outline_color.lower()
        assert colors.hole_outline.lower() == style.background_color.lower()
    finally:
        themes.set_active_theme(original_theme)
        if default_view is not None:
            default_view.destroy()
        if dark_view is not None:
            dark_view.destroy()
        root.update_idletasks()
        root.destroy()
