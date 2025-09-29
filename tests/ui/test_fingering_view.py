import tkinter as tk

import pytest

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
