import logging
import tkinter as tk
from dataclasses import replace

import pytest

from ocarina_gui import themes
from ocarina_gui.fingering import (
    get_current_instrument,
    get_instrument,
    set_active_instrument,
    update_instrument_spec,
)
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
def test_preview_hole_clicks_when_hole_empty(caplog):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    caplog.set_level(logging.DEBUG, logger="ocarina_gui.fingering.view")
    original = get_current_instrument()
    view: FingeringView | None = None
    try:
        if not original.holes:
            pytest.skip("Instrument does not define any holes")
        if not original.note_map:
            pytest.skip("Instrument does not define any note mappings")

        view = FingeringView(root)
        root.update_idletasks()

        note = next(iter(original.note_map.keys()))
        total_elements = len(original.holes) + len(original.windways)
        if total_elements <= 0:
            pytest.skip("Instrument does not define any interactive elements")

        zero_pattern = [0] * total_elements
        updated_map = {
            key: (list(zero_pattern) if key == note else list(values))
            for key, values in original.note_map.items()
        }

        update_instrument_spec(replace(original, note_map=updated_map))
        root.update()

        clicks: list[int] = []
        view.set_hole_click_handler(lambda index: clicks.append(index))

        view.show_fingering(note, None)
        root.update()

        hole_tag = view._hole_tag(0)  # type: ignore[attr-defined]
        bbox = view.bbox(hole_tag)
        assert bbox is not None
        left, top, right, bottom = bbox
        center_x = int(round((left + right) / 2))
        center_y = int(round((top + bottom) / 2))

        view.event_generate("<Button-1>", x=center_x, y=center_y)
        root.update()

        assert clicks == [0]
    finally:
        update_instrument_spec(original)
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()


@pytest.mark.gui
def test_half_hole_instrument_preview_handles_repeated_clicks():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    original_spec = get_current_instrument()
    original_id = original_spec.instrument_id
    six_spec = get_instrument("alto_c_6")
    view: FingeringView | None = None
    try:
        set_active_instrument("alto_c_6")
        instrument = get_current_instrument()
        if not instrument.holes:
            pytest.skip("Instrument does not define any holes")

        note = next((note for note in instrument.note_order if note in instrument.note_map), None)
        if not note:
            pytest.skip("Instrument does not define mapped fingerings")

        view = FingeringView(root)
        root.update_idletasks()

        clicks: list[int] = []
        view.set_hole_click_handler(lambda index: clicks.append(index))

        view.show_fingering(note, None)
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

        total_elements = len(instrument.holes) + len(instrument.windways)
        zero_pattern = [0] * total_elements
        updated_map = {
            key: (list(zero_pattern) if key == note else list(values))
            for key, values in instrument.note_map.items()
        }
        update_instrument_spec(replace(instrument, note_map=updated_map))
        root.update_idletasks()

        view.event_generate("<Button-1>", x=center_x, y=center_y)
        root.update_idletasks()
        assert clicks == [0, 0]
    finally:
        update_instrument_spec(six_spec)
        set_active_instrument(original_id)
        update_instrument_spec(original_spec)
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


@pytest.mark.gui
def test_outline_not_rerendered_on_note_pattern_updates(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    instrument = get_current_instrument()
    view: FingeringView | None = None
    try:
        call_count = 0

        from ocarina_gui.fingering import view as fingering_view_module

        original_render = fingering_view_module.render_outline_photoimage

        def _counting_render(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_render(*args, **kwargs)

        monkeypatch.setattr(
            fingering_view_module,
            "render_outline_photoimage",
            _counting_render,
        )

        view = FingeringView(root)
        root.update_idletasks()

        if not instrument.note_map:
            pytest.skip("Instrument does not define any note mappings")

        baseline_calls = call_count
        note, pattern = next(iter(instrument.note_map.items()))
        total_elements = len(instrument.holes) + len(instrument.windways)
        values = list(pattern)
        if len(values) < total_elements:
            values.extend([0] * (total_elements - len(values)))
        if not values:
            values = [0] * max(1, total_elements)
        values[0] = 2 if values[0] != 2 else 0

        updated_map = {
            key: (list(values) if key == note else list(existing))
            for key, existing in instrument.note_map.items()
        }

        updated_spec = replace(instrument, note_map=updated_map)

        view.show_fingering(note, None)
        update_instrument_spec(updated_spec)

        assert call_count == baseline_calls
    finally:
        update_instrument_spec(instrument)
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()


@pytest.mark.gui
def test_static_not_redrawn_when_note_map_updates(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    instrument = get_current_instrument()
    view: FingeringView | None = None
    draw_calls = 0

    original_draw_static = FingeringView._draw_static

    def _counting_draw(self, *, precomputed_signature=None):  # type: ignore[override]
        nonlocal draw_calls
        draw_calls += 1
        return original_draw_static(self, precomputed_signature=precomputed_signature)

    monkeypatch.setattr(FingeringView, "_draw_static", _counting_draw)

    try:
        view = FingeringView(root)
        root.update_idletasks()

        if not instrument.note_map:
            pytest.skip("Instrument does not define any note mappings")

        baseline_calls = draw_calls
        note, pattern = next(iter(instrument.note_map.items()))
        total_elements = len(instrument.holes) + len(instrument.windways)
        values = list(pattern)
        if len(values) < total_elements:
            values.extend([0] * (total_elements - len(values)))
        if not values:
            values = [0] * max(1, total_elements)
        values[0] = 2 if values[0] != 2 else 0

        updated_map = {
            key: (list(values) if key == note else list(existing))
            for key, existing in instrument.note_map.items()
        }

        updated_spec = replace(instrument, note_map=updated_map)

        view.show_fingering(note, None)
        update_instrument_spec(updated_spec)
        root.update_idletasks()

        assert draw_calls == baseline_calls
    finally:
        update_instrument_spec(instrument)
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()


@pytest.mark.gui
def test_static_content_redrawn_for_instrument_updates():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()
    original = get_current_instrument()
    view: FingeringView | None = None
    try:
        view = FingeringView(root)
        root.update_idletasks()

        if not original.note_map:
            pytest.skip("Instrument does not define any note mappings")

        call_count = 0
        original_draw = view._draw_static

        def _counting_draw() -> None:
            nonlocal call_count
            call_count += 1
            original_draw()

        view._draw_static = _counting_draw  # type: ignore[attr-defined]
        call_count = 0

        note, pattern = next(iter(original.note_map.items()))
        updated_pattern = list(pattern)
        if updated_pattern:
            updated_pattern[0] = 0 if updated_pattern[0] >= 2 else 2
        updated_map = {
            key: (list(updated_pattern) if key == note else list(values))
            for key, values in original.note_map.items()
        }
        updated_spec = replace(original, note_map=updated_map)

        update_instrument_spec(updated_spec)
        root.update_idletasks()

        assert call_count >= 1
    finally:
        update_instrument_spec(original)
        if view is not None:
            view.destroy()
        root.update_idletasks()
        root.destroy()
