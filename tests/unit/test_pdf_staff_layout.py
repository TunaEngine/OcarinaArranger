from ocarina_gui.events import trim_leading_silence
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.pages.staff import (
    TARGET_PX_PER_TICK,
    _choose_measures_per_system,
    build_staff_pages,
)
from ocarina_gui.pdf_export.pages._time_signature import ticks_per_measure
from ocarina_gui.pdf_export.writer import PageBuilder
from ocarina_gui.staff.rendering.geometry import staff_y
from ocarina_tools import NoteEvent


def test_choose_measures_per_system_prefers_spacing_close_to_target():
    measures = _choose_measures_per_system(
        staff_width=665.0, ticks_per_measure=1920, target_px_per_tick=TARGET_PX_PER_TICK
    )
    assert measures == 3


def test_choose_measures_per_system_handles_non_positive_target():
    measures = _choose_measures_per_system(staff_width=500.0, ticks_per_measure=1920, target_px_per_tick=0)
    assert measures == 1


def test_ticks_per_measure_respects_time_signature():
    ticks = ticks_per_measure(pulses_per_quarter=480, beats=3, beat_type=8)
    assert ticks == 720


def test_trim_leading_silence_shifts_events():
    events = [
        NoteEvent(120, 240, 60, 0),
        NoteEvent(360, 120, 62, 0),
    ]

    trimmed = trim_leading_silence(events)

    assert [event.onset for event in trimmed] == [0, 240]
    assert [event.duration for event in trimmed] == [240, 120]


def test_staff_notes_start_to_right_of_barline(monkeypatch):
    layout = resolve_layout("A4", "portrait")
    events = [NoteEvent(0, 240, 60, 0), NoteEvent(240, 240, 62, 0)]

    measure_lines: list[float] = []
    note_heads: list[tuple[float, float]] = []

    original_draw_line = PageBuilder.draw_line
    original_draw_oval = PageBuilder.draw_oval

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(x1 - x2) < 1e-6 and abs(gray - 0.75) < 1e-6 and abs(line_width - 0.5) < 1e-6:
            measure_lines.append(x1)
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    def _record_oval(self, cx, cy, rx, ry, *, fill_gray=None, stroke_gray=0.0, line_width=1.0):
        note_heads.append((cx, rx))
        return original_draw_oval(
            self,
            cx,
            cy,
            rx,
            ry,
            fill_gray=fill_gray,
            stroke_gray=stroke_gray,
            line_width=line_width,
        )

    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)
    monkeypatch.setattr(PageBuilder, "draw_oval", _record_oval)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert measure_lines, "expected measure lines to be drawn"
    assert note_heads, "expected note heads to be drawn"

    first_barline = min(measure_lines)
    first_note_center, first_note_radius = note_heads[0]

    assert first_note_center - first_note_radius >= first_barline


def test_staff_pdf_ledger_lines_align_below_middle_d(monkeypatch):
    layout = resolve_layout("A4", "portrait")
    events = [NoteEvent(0, 240, 62, 0)]

    staff_lines: list[float] = []
    ledger_lines: list[float] = []

    original_draw_line = PageBuilder.draw_line

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(gray - 0.2) < 1e-6 and abs(line_width - 1.0) < 1e-6:
            staff_lines.extend([y1, y2])
        if abs(gray - 0.4) < 1e-6 and abs(line_width - 0.6) < 1e-6:
            ledger_lines.extend([y1, y2])
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert staff_lines, "expected staff lines to be drawn"
    assert ledger_lines, "expected ledger lines to be drawn for middle D"

    staff_spacing = abs(staff_lines[2] - staff_lines[0])
    staff_top = min(staff_lines)

    ledger_y_values = {round(value, 6) for value in ledger_lines}
    expected_bottom_ledger = round(staff_y(staff_top, -2, staff_spacing), 6)
    disallowed_crossing_ledger = round(staff_y(staff_top, -1, staff_spacing), 6)

    assert expected_bottom_ledger in ledger_y_values
    assert disallowed_crossing_ledger not in ledger_y_values
