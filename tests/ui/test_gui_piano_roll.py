from __future__ import annotations

from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.usefixtures("ensure_original_preview")



def test_piano_roll_hover_updates_highlight_and_callback(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "_midi_from_y"):
        pytest.skip("Piano roll hover behaviour requires Tk-based widgets")
    midi = roll.max_midi - 4
    events = [(0, 120, midi)]
    roll.render(events, pulses_per_quarter=480)

    received = []
    roll.set_fingering_cb(lambda value: received.append(value))

    y = roll._y(midi) + roll.px_per_note // 2
    roll._hover_emit(int(y))

    assert received and received[-1] == midi
    assert roll._label_highlight is not None
    highlight_state = roll.labels.itemcget(roll._label_highlight, "state")
    assert highlight_state == "normal"
    expected_coords = [
        0.0,
        float(roll._y(midi)),
        float(roll.label_width),
        float(roll._y(midi) + roll.px_per_note),
    ]
    assert roll.labels.coords(roll._label_highlight) == pytest.approx(expected_coords)

    roll.canvas.yview_moveto(0.25)
    roll.labels.yview_moveto(0.25)
    roll.canvas.update_idletasks()

    received.clear()
    top_offset = int(roll.canvas.canvasy(0))
    viewport_y = int(y - top_offset)
    roll._hover_emit(viewport_y, roll.canvas)

    assert received and received[-1] == midi
    assert roll.labels.coords(roll._label_highlight) == pytest.approx(expected_coords)


def test_piano_roll_hover_clears_highlight_outside_rows(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "_midi_from_y"):
        pytest.skip("Piano roll hover behaviour requires Tk-based widgets")
    midi = roll.max_midi - 2
    roll.render([(0, 60, midi)], pulses_per_quarter=480)

    received = []
    roll.set_fingering_cb(lambda value: received.append(value))

    roll._hover_emit(roll._y(midi) + roll.px_per_note // 2)
    assert received and received[-1] == midi

    roll._hover_emit(roll._y(roll.max_midi) - 5)
    assert received[-1] is None
    assert roll._label_highlight is not None
    assert roll.labels.itemcget(roll._label_highlight, "state") == "hidden"


def test_piano_roll_hover_handles_notes_below_range(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "_midi_from_y"):
        pytest.skip("Piano roll hover behaviour requires Tk-based widgets")

    midi = roll.min_midi - 3
    roll.render([(0, 90, midi)], pulses_per_quarter=480)

    received = []
    roll.set_fingering_cb(lambda value: received.append(value))

    y = roll._y(midi) + roll.px_per_note // 2
    roll._hover_emit(int(y))

    assert received and received[-1] == midi
    assert roll._label_highlight is not None
    assert roll.labels.itemcget(roll._label_highlight, "state") == "normal"
    expected_coords = [
        0.0,
        float(roll._y(roll.min_midi)),
        float(roll.label_width),
        float(roll._y(roll.min_midi) + roll.px_per_note),
    ]
    assert roll.labels.coords(roll._label_highlight) == pytest.approx(expected_coords)

    fingering = gui_app.side_fing_orig
    assert fingering is not None
    roll.set_fingering_cb(fingering.set_midi)
    roll._hover_emit(int(y))
    status = getattr(fingering, "status", getattr(fingering, "_status_message", ""))
    assert status == "No fingering available"


def test_piano_roll_cursor_autoscrolls_into_view(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "canvas") or not hasattr(roll.canvas, "winfo_width"):
        pytest.skip("Autoscroll behaviour requires Tk-based widgets")

    events = [(index * 240, 180, roll.min_midi + (index % 5)) for index in range(24)]
    roll.render(events, pulses_per_quarter=480)
    roll.canvas.configure(width=260)
    roll.canvas.update_idletasks()

    start_left = roll.canvas.xview()[0]
    roll.set_cursor(roll._total_ticks)
    gui_app.update_idletasks()
    end_left = roll.canvas.xview()[0]

    roll.set_cursor(0)
    gui_app.update_idletasks()
    reset_left = roll.canvas.xview()[0]

    assert end_left > start_left
    assert reset_left < end_left


def test_piano_roll_cursor_skip_redundant_scroll(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "canvas") or not hasattr(roll.canvas, "winfo_width"):
        pytest.skip("Autoscroll behaviour requires Tk-based widgets")

    events = [(index * 180, 160, roll.min_midi + (index % 4)) for index in range(18)]
    roll.render(events, pulses_per_quarter=480)
    roll.canvas.configure(width=240)
    roll.canvas.update_idletasks()

    roll.set_cursor(roll._total_ticks)
    gui_app.update_idletasks()
    initial_left = roll.canvas.xview()[0]

    roll.set_cursor(roll._total_ticks)
    gui_app.update_idletasks()
    second_left = roll.canvas.xview()[0]

    assert second_left == pytest.approx(initial_left)


def test_piano_roll_shows_note_name_only(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "canvas") or not hasattr(roll, "min_midi"):
        pytest.skip("Piano roll rendering requires Tk-based widgets")

    midi = roll.min_midi + 4
    events = [(0, 480, midi)]
    roll.render(events, pulses_per_quarter=480)
    gui_app.update_idletasks()
    roll.canvas.update_idletasks()

    text_items = roll.canvas.find_withtag("note_value_label")
    texts = {roll.canvas.itemcget(item, "text") for item in text_items}

    note_name = roll._label_for_midi(midi)
    assert note_name in texts
    assert texts == {note_name}
    disallowed = {"Quarter", "Eighth", "Sixteenth", "/"}
    assert all(not any(token in text for token in disallowed) for text in texts)


def test_piano_roll_vertical_layout_updates_on_resize(gui_app):
    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll, "set_time_scroll_orientation") or not hasattr(roll, "_wrap_layout"):
        pytest.skip("Wrapped layout behaviour requires Tk-based widgets")

    events = [(index * 240, 180, roll.min_midi + (index % 6)) for index in range(24)]
    roll.set_time_scroll_orientation("vertical")
    roll.canvas.configure(width=900)
    roll.render(events, pulses_per_quarter=480)
    gui_app.update_idletasks()
    roll.canvas.update_idletasks()

    layout = getattr(roll, "_wrap_layout", None)
    assert layout is not None
    initial_ticks_per_line = layout.ticks_per_line
    assert initial_ticks_per_line > 0

    roll.canvas.configure(width=1200)
    roll._on_canvas_configure(SimpleNamespace(width=1200))
    gui_app.update_idletasks()
    roll.canvas.update_idletasks()

    updated_layout = getattr(roll, "_wrap_layout", None)
    assert updated_layout is not None
    assert updated_layout.ticks_per_line > initial_ticks_per_line
