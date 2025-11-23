from __future__ import annotations

import tkinter as tk

import pytest

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from ocarina_gui.note_values import describe_note_glyph
from ocarina_gui.staff import StaffView


@pytest.mark.gui
def test_staff_draws_ledger_lines_and_octave_labels() -> None:
    root: tk.Tk | None = None
    staff: StaffView | None = None

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        staff.pack()
        root.update_idletasks()

        events = [
            (0, 120, 52, 0),
            (480, 120, 84, 0),
            (960, 120, 62, 0),
            (1920, 120, 64, 0),
        ]
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)

        canvas = staff.canvas
        y_top = getattr(staff, "_last_y_top", 40)

        measure_items = canvas.find_withtag("measure_number")
        assert measure_items, "expected measure numbers to be drawn"
        measure_texts = {canvas.itemcget(item, "text") for item in measure_items}
        assert "2" in measure_texts

        def _ledger_segments() -> list[tuple[float, float, float, float]]:
            segments: list[tuple[float, float, float, float]] = []
            for item in canvas.find_all():
                if canvas.type(item) != "line":
                    continue
                coords = canvas.coords(item)
                if len(coords) < 4:
                    continue
                for index in range(0, len(coords) - 2, 2):
                    x1, y1, x2, y2 = coords[index : index + 4]
                    if abs(y2 - y1) > 1e-3:
                        continue
                    if x2 - x1 <= 60:
                        segments.append((x1, y1, x2, y2))
            return segments

        ledger_segments = _ledger_segments()
        assert ledger_segments, "expected ledger lines to be drawn"

        note_width = 12
        d_onset = 960
        d_pos = staff._staff_pos(62)
        assert d_pos == -1
        x_center_d = staff.LEFT_PAD + int(d_onset * staff.px_per_tick) + note_width / 2
        d_line_y = staff._y_for_pos(y_top, -2)
        assert any(
            abs(segment_y - d_line_y) < 0.6
            and abs((x1 + x2) / 2 - x_center_d) < 1.6
            for x1, segment_y, x2, _ in ledger_segments
        ), "expected D4 to use the lower ledger line"
        d_y = staff._y_for_pos(y_top, d_pos)
        assert not any(
            abs(segment_y - d_y) < 0.6 and abs((x1 + x2) / 2 - x_center_d) < 1.6
            for x1, segment_y, x2, _ in ledger_segments
        ), "D4 ledger line should not cross the note head"
        high_onset = 480
        x_center_high = staff.LEFT_PAD + int(high_onset * staff.px_per_tick) + note_width / 2
        high_pos = staff._staff_pos(84)
        for ledger_pos in range(10, high_pos + 1, 2):
            expected_y = staff._y_for_pos(y_top, ledger_pos)
            assert any(
                abs(segment_y - expected_y) < 0.6 and abs((x1 + x2) / 2 - x_center_high) < 1.6
                for x1, segment_y, x2, _ in ledger_segments
            ), f"missing ledger line at pos {ledger_pos}"

        def _text_positions(value: str) -> list[tuple[float, float]]:
            positions: list[tuple[float, float]] = []
            for item in canvas.find_all():
                if canvas.type(item) != "text":
                    continue
                if canvas.itemcget(item, "text") != value:
                    continue
                x, y = canvas.coords(item)
                positions.append((x, y))
            return positions

        low_pos = staff._staff_pos(52)
        y_low = staff._y_for_pos(y_top, low_pos)
        low_expected_y = y_low + staff.staff_spacing * 1.6
        low_x = staff.LEFT_PAD + note_width / 2
        low_matches = _text_positions("3")
        assert any(
            abs(x - low_x) < 1.6 and abs(y - low_expected_y) < staff.staff_spacing
            for x, y in low_matches
        )

        high_y = staff._y_for_pos(y_top, high_pos)
        high_expected_y = high_y - staff.staff_spacing * 1.6
        high_matches = _text_positions("6")
        assert any(
            abs(x - x_center_high) < 1.6 and abs(y - high_expected_y) < staff.staff_spacing
            for x, y in high_matches
        )

        assert not _text_positions("1/16")

        def _stem_segments() -> list[tuple[float, float, float, float]]:
            stems: list[tuple[float, float, float, float]] = []
            for item in canvas.find_all():
                if canvas.type(item) != "line":
                    continue
                coords = canvas.coords(item)
                if len(coords) < 4:
                    continue
                for index in range(0, len(coords) - 2, 2):
                    x1, y1, x2, y2 = coords[index : index + 4]
                    if abs(x1 - x2) > 0.8:
                        continue
                    length = abs(y2 - y1)
                    if length < staff.staff_spacing * 2.4 or length > staff.staff_spacing * 4.5:
                        continue
                    stems.append((x1, y1, x2, y2))
            return stems

        stems = _stem_segments()
        assert stems, "expected stems for rhythmic glyphs"

        low_glyph = describe_note_glyph(120, 480)
        assert low_glyph is not None and low_glyph.base != "whole"
        low_stem_up = staff._staff_pos(52) < 6
        expected_low_x0 = staff.LEFT_PAD + int(0 * staff.px_per_tick)
        expected_low_stem_x = expected_low_x0 + (note_width if low_stem_up else 0)
        assert any(abs(x1 - expected_low_stem_x) < 2.0 for x1, *_ in stems)

        high_glyph = describe_note_glyph(120, 480)
        assert high_glyph is not None
        high_stem_up = staff._staff_pos(84) < 6
        expected_high_x0 = staff.LEFT_PAD + int(high_onset * staff.px_per_tick)
        expected_high_stem_x = expected_high_x0 + (note_width if high_stem_up else 0)
        assert any(abs(x1 - expected_high_stem_x) < 2.0 for x1, *_ in stems)
    finally:
        if staff is not None:
            try:
                staff.destroy()
            except Exception:
                pass
        if root is not None:
            root.update_idletasks()
            root.destroy()


@pytest.mark.gui
@pytest.mark.skip(reason="Temporarily? disabled")
def test_staff_click_sets_cursor_and_emits_callback() -> None:
    root: tk.Tk | None = None
    staff: StaffView | None = None

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        staff.pack()
        root.update_idletasks()

        events = [(index * 240, 120, 60 + (index % 4), 0) for index in range(16)]
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)
        root.update_idletasks()

        received: list[int] = []
        staff.set_cursor_callback(received.append)

        target_tick = events[6][0]
        x = staff.LEFT_PAD + int(round(target_tick * staff.px_per_tick))
        y = getattr(staff, "_last_y_top", 40) + staff.staff_spacing * 2
        staff.canvas.event_generate("<Button-1>", x=x, y=int(y))
        root.update_idletasks()

        assert received and received[-1] == target_tick
        assert staff._cursor_tick == target_tick

        staff.set_layout_mode("wrapped")
        staff.canvas.configure(width=900)
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)
        root.update_idletasks()

        received.clear()
        wrapped_tick = events[-1][0]
        x_wrapped, y_top, _y_bottom = staff._wrap_tick_to_coords(wrapped_tick)
        staff.canvas.event_generate("<Button-1>", x=int(x_wrapped), y=int(y_top + staff.staff_spacing))
        root.update_idletasks()

        assert received and received[-1] == wrapped_tick
        assert staff._cursor_tick == wrapped_tick
    finally:
        if staff is not None:
            try:
                staff.destroy()
            except Exception:
                pass
        if root is not None:
            root.update_idletasks()
            root.destroy()


@pytest.mark.gui
def test_staff_cursor_autoscrolls_into_view() -> None:
    root: tk.Tk | None = None
    staff: StaffView | None = None

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        staff.pack()
        root.update_idletasks()

        events = [(index * 240, 160, 60 + (index % 5), 0) for index in range(32)]
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)
        staff.canvas.configure(width=260)
        root.update_idletasks()

        start_fraction = staff.canvas.xview()[0]
        staff.set_cursor(events[-1][0])
        root.update_idletasks()
        after_fraction = staff.canvas.xview()[0]

        staff.set_cursor(0)
        root.update_idletasks()
        reset_fraction = staff.canvas.xview()[0]

        assert after_fraction > start_fraction
        assert reset_fraction < after_fraction

        staff.set_layout_mode("wrapped")
        staff.canvas.configure(width=900)
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)
        root.update_idletasks()

        start_y = staff.canvas.yview()[0]
        staff.set_cursor(events[-1][0])
        root.update_idletasks()
        after_y = staff.canvas.yview()[0]

        assert after_y > start_y
    finally:
        if staff is not None:
            try:
                staff.destroy()
            except Exception:
                pass
        if root is not None:
            root.update_idletasks()
            root.destroy()


@pytest.mark.gui
def test_staff_updates_playback_cursors() -> None:
    root: tk.Tk | None = None
    staff: StaffView | None = None

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        staff.pack()
        root.update_idletasks()

        events = [
            (0, 120, 60, 0),
            (240, 120, 64, 0),
        ]
        staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)

        staff.set_cursor(240)
        staff.set_secondary_cursor(120)

        canvas = staff.canvas
        primary = canvas.find_withtag("time_cursor_primary")
        assert primary, "expected primary cursor line"
        secondary = canvas.find_withtag("time_cursor_secondary")
        assert secondary, "expected secondary cursor line"

        expected_primary_x = staff.LEFT_PAD + int(round(240 * staff.px_per_tick))
        primary_coords = canvas.coords(primary[0])
        assert pytest.approx(primary_coords[0], abs=0.6) == expected_primary_x
        assert pytest.approx(primary_coords[2], abs=0.6) == expected_primary_x
        assert canvas.itemcget(primary[0], "state") == "normal"

        expected_secondary_x = staff.LEFT_PAD + int(round(120 * staff.px_per_tick))
        secondary_coords = canvas.coords(secondary[0])
        assert pytest.approx(secondary_coords[0], abs=0.6) == expected_secondary_x
        assert pytest.approx(secondary_coords[2], abs=0.6) == expected_secondary_x
        assert canvas.itemcget(secondary[0], "state") == "normal"

        staff.set_time_zoom(2.0)
        root.update_idletasks()

        expected_primary_zoomed = staff.LEFT_PAD + int(round(240 * staff.px_per_tick))
        expected_secondary_zoomed = staff.LEFT_PAD + int(round(120 * staff.px_per_tick))
        zoomed_primary = canvas.find_withtag("time_cursor_primary")
        zoomed_secondary = canvas.find_withtag("time_cursor_secondary")
        assert zoomed_primary
        assert zoomed_secondary
        zoomed_primary_coords = canvas.coords(zoomed_primary[0])
        zoomed_secondary_coords = canvas.coords(zoomed_secondary[0])
        assert pytest.approx(zoomed_primary_coords[0], abs=0.6) == expected_primary_zoomed
        assert pytest.approx(zoomed_secondary_coords[0], abs=0.6) == expected_secondary_zoomed

        staff.set_secondary_cursor(None)
        refreshed_secondary = canvas.find_withtag("time_cursor_secondary")
        assert refreshed_secondary
        assert canvas.itemcget(refreshed_secondary[0], "state") == "hidden"
    finally:
        if staff is not None:
            try:
                staff.destroy()
            except Exception:
                pass
        if root is not None:
            root.update_idletasks()
            root.destroy()
