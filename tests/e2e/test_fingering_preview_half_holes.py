from __future__ import annotations

import tkinter as tk
from dataclasses import replace

import pytest

from ocarina_gui.fingering import (
    FingeringView,
    get_current_instrument,
    get_current_instrument_id,
    load_fingering_config,
    set_active_instrument,
    update_instrument_spec,
    update_library_from_config,
)


@pytest.mark.gui
def test_custom_half_hole_instrument_preview_round_trip(monkeypatch: pytest.MonkeyPatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    view: FingeringView | None = None
    original_config = load_fingering_config()
    original_id = get_current_instrument_id()
    original_spec = get_current_instrument()

    instrument_data = {
        "id": "test_half_hole_preview",
        "name": "Test Half-Hole",
        "title": "Test Half-Hole",
        "canvas": {"width": 140, "height": 140},
        "style": {
            "background_color": "#ffffff",
            "outline_color": "#111111",
            "outline_width": 3.0,
            "outline_smooth": True,
            "outline_spline_steps": 48,
            "hole_outline_color": "#111111",
            "covered_fill_color": "#111111",
        },
        "holes": [
            {"id": "primary", "x": 70.0, "y": 70.0, "radius": 18.0},
        ],
        "windways": [],
        "note_order": ["C4"],
        "note_map": {"C4": [2]},
        "candidate_notes": ["C4"],
        "candidate_range": {"min": "C4", "max": "C4"},
        "preferred_range": {"min": "C4", "max": "C4"},
        "allow_half_holes": True,
        "outline": {
            "points": [
                [20.0, 20.0],
                [20.0, 120.0],
                [120.0, 120.0],
                [120.0, 20.0],
            ],
            "closed": True,
        },
    }

    monkeypatch.setattr(
        "ocarina_gui.fingering.save_fingering_config", lambda config: None
    )

    try:
        update_library_from_config({"instruments": [instrument_data]}, current_instrument_id=instrument_data["id"])
        set_active_instrument(instrument_data["id"])

        view = FingeringView(root)
        root.update_idletasks()

        clicks: list[int] = []
        view.set_hole_click_handler(lambda index: clicks.append(index))

        view.show_fingering("C4", None)
        root.update_idletasks()

        hole_tag = view._hole_tag(0)  # type: ignore[attr-defined]
        bbox = view.bbox(hole_tag)
        assert bbox is not None
        left, top, right, bottom = bbox
        center_x = int(round((left + right) / 2))
        center_y = int(round((top + bottom) / 2))

        view.event_generate("<Button-1>", x=center_x, y=center_y)
        root.update_idletasks()
        assert clicks == [0]

        instrument = get_current_instrument()
        total_elements = len(instrument.holes) + len(instrument.windways)
        zero_pattern = [0] * total_elements
        updated_map = {
            key: (list(zero_pattern) if key == "C4" else list(values))
            for key, values in instrument.note_map.items()
        }
        update_instrument_spec(replace(instrument, note_map=updated_map))
        root.update_idletasks()

        view.event_generate("<Button-1>", x=center_x, y=center_y)
        root.update_idletasks()
        assert clicks == [0, 0]
    finally:
        update_library_from_config(original_config, current_instrument_id=original_id)
        set_active_instrument(original_id)
        update_instrument_spec(original_spec)
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()
