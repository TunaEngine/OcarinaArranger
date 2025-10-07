from __future__ import annotations

import tkinter as tk

import pytest

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from app.config import get_auto_scroll_config
from ocarina_gui.piano_roll import PianoRoll
from ocarina_gui.staff import StaffView


def _canvas_left_pixel(canvas: tk.Canvas) -> float:
    region = canvas.cget("scrollregion")
    if not region:
        return 0.0
    parts = [float(value) for value in region.split()]
    if len(parts) != 4:
        return 0.0
    width = parts[2] - parts[0]
    if width <= 0:
        return 0.0
    first = canvas.xview()[0]
    return first * width


@pytest.mark.gui
def test_piano_roll_scrolls_in_pixel_steps() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        roll = PianoRoll(root)
        increment = int(roll.canvas.cget("xscrollincrement"))
        assert increment == 1
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_staff_scrolls_in_pixel_steps() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        increment = int(staff.canvas.cget("xscrollincrement"))
        assert increment == 1
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_autoscroll_snaps_to_integer_pixels() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        roll = PianoRoll(root)
        staff = StaffView(root)
        roll.pack()
        staff.pack()
        roll.sync_x_with(staff.canvas)
        staff.sync_x_with(roll.canvas)

        events = [(i * 240, 180, 60 + (i % 5), 0) for i in range(20)]
        pulses_per_quarter = 480
        roll.render(events, pulses_per_quarter)
        staff.render(events, pulses_per_quarter)

        roll.canvas.config(width=220)
        staff.canvas.config(width=220)
        root.update_idletasks()

        roll.set_cursor(roll._total_ticks)
        root.update_idletasks()

        roll_left = _canvas_left_pixel(roll.canvas)
        staff_left = _canvas_left_pixel(staff.canvas)

        assert pytest.approx(round(roll_left), abs=1e-6) == roll_left
        assert pytest.approx(round(staff_left), abs=1e-6) == staff_left
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_autoscroll_pages_when_cursor_reaches_threshold() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        roll = PianoRoll(root)
        staff = StaffView(root)
        roll.pack()
        staff.pack()
        roll.sync_x_with(staff.canvas)
        staff.sync_x_with(roll.canvas)

        events = [(i * 480, 240, 60 + (i % 6), 0) for i in range(120)]
        pulses_per_quarter = 480
        roll.render(events, pulses_per_quarter)
        staff.render(events, pulses_per_quarter)

        roll.canvas.config(width=320)
        staff.canvas.config(width=320)
        root.update_idletasks()

        viewport = int(roll.canvas.winfo_width())
        assert viewport > 0
        initial_left = _canvas_left_pixel(roll.canvas)
        assert initial_left == pytest.approx(0.0)

        roll.set_auto_scroll_mode("flip")
        flip_config = get_auto_scroll_config().flip
        threshold_x = int(round(viewport * flip_config.threshold_fraction))
        before_tick = int(round((threshold_x - 10 - roll.LEFT_PAD) / max(roll.px_per_tick, 1e-6)))
        roll.set_cursor(before_tick)
        root.update_idletasks()
        assert _canvas_left_pixel(roll.canvas) == pytest.approx(0.0)
        assert _canvas_left_pixel(staff.canvas) == pytest.approx(0.0)

        after_tick = int(round((threshold_x + 10 - roll.LEFT_PAD) / max(roll.px_per_tick, 1e-6)))
        roll.set_cursor(after_tick)
        root.update_idletasks()

        expected_left = initial_left + int(round(viewport * flip_config.page_offset_fraction))
        max_left = max(0, roll._scroll_width - viewport)
        expected_left = max(0, min(expected_left, max_left))

        roll_left = _canvas_left_pixel(roll.canvas)
        staff_left = _canvas_left_pixel(staff.canvas)

        assert roll_left == pytest.approx(expected_left)
        assert staff_left == pytest.approx(expected_left)
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_piano_roll_only_draws_visible_events() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        roll = PianoRoll(root)
        roll.pack()
        events = [(i * 480, 240, 60 + (i % 12), 0) for i in range(60)]
        pulses_per_quarter = 480
        roll.render(events, pulses_per_quarter)
        roll.canvas.config(width=260)
        root.update_idletasks()

        initial = roll.canvas.find_withtag("note_rect")
        assert initial
        assert len(initial) < len(events)
        coords_initial = [roll.canvas.coords(item)[0] for item in initial]
        min_initial = min(coords_initial)
        max_initial = max(coords_initial)
        assert abs(min_initial - roll.LEFT_PAD) <= 2

        roll.canvas.xview_moveto(1.0)
        root.update_idletasks()

        after = roll.canvas.find_withtag("note_rect")
        assert after
        assert len(after) < len(events)
        coords_after = [roll.canvas.coords(item)[0] for item in after]
        min_after = min(coords_after)
        assert max_initial < min_after
    finally:
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_staff_only_draws_visible_events() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        staff = StaffView(root)
        staff.pack()
        events = [(i * 480, 240, 60 + (i % 8), 0) for i in range(60)]
        pulses_per_quarter = 480
        staff.render(events, pulses_per_quarter)
        staff.canvas.config(width=260)
        root.update_idletasks()

        initial = staff.canvas.find_withtag("staff_note")
        assert initial
        assert len(initial) < len(events)
        coords_initial = [staff.canvas.coords(item)[0] for item in initial]
        min_initial = min(coords_initial)
        max_initial = max(coords_initial)
        assert abs(min_initial - staff.LEFT_PAD) <= 2

        staff.canvas.xview_moveto(1.0)
        root.update_idletasks()

        after = staff.canvas.find_withtag("staff_note")
        assert after
        assert len(after) < len(events)
        coords_after = [staff.canvas.coords(item)[0] for item in after]
        min_after = min(coords_after)
        assert max_initial < min_after
    finally:
        if root is not None:
            root.destroy()
@pytest.mark.gui
def test_autoscroll_continuous_tracks_cursor() -> None:
    root: tk.Tk | None = None
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    try:
        roll = PianoRoll(root)
        staff = StaffView(root)
        roll.pack()
        staff.pack()
        roll.sync_x_with(staff.canvas)
        staff.sync_x_with(roll.canvas)

        events = [(i * 480, 240, 60 + (i % 6), 0) for i in range(120)]
        pulses_per_quarter = 480
        roll.render(events, pulses_per_quarter)
        staff.render(events, pulses_per_quarter)

        roll.canvas.config(width=320)
        staff.canvas.config(width=320)
        root.update()

        viewport = int(roll.canvas.winfo_width())
        assert viewport > 0

        roll.set_auto_scroll_mode("continuous")
        threshold_x = int(round(viewport * 0.75))
        before_tick = int(round((threshold_x - 5 - roll.LEFT_PAD) / max(roll.px_per_tick, 1e-6)))
        roll.set_cursor(before_tick)
        root.update()
        assert _canvas_left_pixel(roll.canvas) == pytest.approx(0.0)

        after_tick = int(round((threshold_x + 20 - roll.LEFT_PAD) / max(roll.px_per_tick, 1e-6)))
        roll.set_cursor(after_tick)
        root.update()

        expected_left = roll._tick_to_x(after_tick) - int(round(viewport * 0.75))
        max_left = max(0, roll._scroll_width - viewport)
        expected_left = max(0, min(expected_left, max_left))

        roll_left = _canvas_left_pixel(roll.canvas)
        staff_left = _canvas_left_pixel(staff.canvas)
        assert roll_left == pytest.approx(expected_left)
        assert staff_left == pytest.approx(expected_left)
    finally:
        if root is not None:
            root.destroy()

