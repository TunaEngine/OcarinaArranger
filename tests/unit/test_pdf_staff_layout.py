import pytest

from ocarina_gui.events import trim_leading_silence
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.pages.staff import (
    ACCIDENTAL_BASELINE_OFFSET_RATIO,
    BASE_TARGET_PX_PER_TICK,
    TARGET_PX_PER_TICK,
    _choose_measures_per_system,
    _target_px_per_tick,
    _draw_pdf_dots,
    build_staff_pages,
)
from ocarina_gui.pdf_export.pages._time_signature import ticks_per_measure
from ocarina_gui.pdf_export.writer import PageBuilder
from ocarina_gui.staff.rendering.geometry import staff_y
from ocarina_gui.staff.rendering.spacing import (
    default_note_scale,
    dot_gap_for_available_space,
    dotted_spacing_offsets,
    minimum_px_per_tick,
    ornament_spacing_offsets,
)
from ocarina_gui.note_values import NoteGlyphDescription
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


def test_staff_pdf_ledger_lines_skip_for_middle_d(monkeypatch):
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
    assert not ledger_lines, "D4 should not render ledger lines"


def test_staff_pdf_ledger_lines_do_not_extend_past_needed(monkeypatch):
    layout = resolve_layout("A4", "portrait")
    events = [NoteEvent(0, 240, 59, 0)]

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
    assert ledger_lines, "expected ledger lines to be drawn for B3"

    staff_spacing = abs(staff_lines[2] - staff_lines[0])
    staff_top = min(staff_lines)

    ledger_y_values = {round(value, 6) for value in ledger_lines}
    expected_ledger = round(staff_y(staff_top, -2, staff_spacing), 6)
    disallowed_lower_ledger = round(staff_y(staff_top, -4, staff_spacing), 6)

    assert expected_ledger in ledger_y_values
    assert disallowed_lower_ledger not in ledger_y_values


def test_staff_pdf_sharp_alignment_and_position(monkeypatch):
    layout = resolve_layout("A4", "portrait")
    events = [NoteEvent(0, 240, 69, 0), NoteEvent(240, 240, 70, 0)]

    note_centers: list[float] = []
    text_positions: list[tuple[str, float]] = []

    original_draw_oval = PageBuilder.draw_oval
    original_draw_text = PageBuilder.draw_text

    def _record_oval(self, cx, cy, rx, ry, *, fill_gray=None, stroke_gray=0.0, line_width=1.0):
        note_centers.append(cy)
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

    def _record_text(self, x, y, text, *, size=None, font="F1", angle=0.0, fill_gray=0.0, fill_rgb=None):
        text_positions.append((text, y))
        return original_draw_text(
            self,
            x,
            y,
            text,
            size=size,
            font=font,
            angle=angle,
            fill_gray=fill_gray,
            fill_rgb=fill_rgb,
        )

    monkeypatch.setattr(PageBuilder, "draw_oval", _record_oval)
    monkeypatch.setattr(PageBuilder, "draw_text", _record_text)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert len(note_centers) >= 2, "expected note heads to be recorded"
    a_center, a_sharp_center = note_centers[:2]
    assert abs(a_center - a_sharp_center) < 1e-6, "A# should share A's staff slot"

    sharp_text_y = next((y for text, y in text_positions if text == "#"), None)
    assert sharp_text_y is not None, "expected a sharp symbol to be drawn"
    expected_baseline = a_sharp_center + (layout.font_size - 2) * ACCIDENTAL_BASELINE_OFFSET_RATIO
    assert sharp_text_y == expected_baseline


def test_staff_pdf_skips_trailing_empty_measure_number(monkeypatch):
    layout = resolve_layout("A4", "portrait")
    # Two measures of notes, but spacing would allow a third on the same system.
    events = [NoteEvent(0, 240, 60, 0), NoteEvent(1920, 240, 62, 0)]

    measure_numbers: list[int] = []

    original_draw_text = PageBuilder.draw_text

    def _record_text(self, x, y, text, *, size=None, font="F1", angle=0.0, fill_gray=0.0, fill_rgb=None):
        if abs(fill_gray - 0.55) < 1e-6 and text.isdigit():
            measure_numbers.append(int(text))
        return original_draw_text(
            self,
            x,
            y,
            text,
            size=size,
            font=font,
            angle=angle,
            fill_gray=fill_gray,
            fill_rgb=fill_rgb,
        )

    monkeypatch.setattr(PageBuilder, "draw_text", _record_text)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert measure_numbers, "expected measure numbers to be recorded"
    assert max(measure_numbers) == 2, "should not render measure numbers for empty trailing measures"


def test_target_px_per_tick_expands_when_notes_crowd():
    layout = resolve_layout("A4", "portrait")
    staff_scale = 0.45 if layout.page_size == "A6" else 0.5
    staff_spacing = 8.0 * staff_scale

    crowded_events = [
        NoteEvent(0, 24, 60, 0, is_grace=True, grace_type="acciaccatura"),
        NoteEvent(16, 120, 62, 0),
    ]

    target_px_per_tick = _target_px_per_tick(False, staff_spacing, crowded_events)

    assert target_px_per_tick == TARGET_PX_PER_TICK


def test_a6_time_zoom_increases_spacing():
    layout = resolve_layout("A6", "portrait")
    staff_scale = 0.45 if layout.page_size == "A6" else 0.5
    staff_spacing = 8.0 * staff_scale

    base_spacing = BASE_TARGET_PX_PER_TICK * 0.5
    target_px_per_tick = _target_px_per_tick(True, staff_spacing, [])

    assert target_px_per_tick == pytest.approx(base_spacing * 1.1)


def test_a6_staff_pages_minimize_margins_and_padding(monkeypatch):
    layout = resolve_layout("A6", "portrait")
    events = [NoteEvent(0, 240, 60, 0)]

    staff_spans: list[float] = []
    system_heights: list[float] = []

    original_draw_line = PageBuilder.draw_line
    original_draw_rect = PageBuilder.draw_rect

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(gray - 0.2) < 1e-6 and abs(line_width - 1.0) < 1e-6 and abs(y1 - y2) < 1e-6:
            staff_spans.append(x2 - x1)
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    def _record_rect(self, x, y, width, height, *, fill_gray=None, stroke_gray=0.0, line_width=1.0):
        if fill_gray is not None and abs(fill_gray - 0.97) < 1e-6:
            system_heights.append(height)
        return original_draw_rect(
            self,
            x,
            y,
            width,
            height,
            fill_gray=fill_gray,
            stroke_gray=stroke_gray,
            line_width=line_width,
        )

    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)
    monkeypatch.setattr(PageBuilder, "draw_rect", _record_rect)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert staff_spans, "expected staff lines to be recorded"
    widest_staff = max(staff_spans)
    assert widest_staff >= layout.width * 0.77

    assert system_heights, "expected system backgrounds to be recorded"
    assert min(system_heights) < 31.0


def test_minimum_spacing_adds_gap_for_close_grace_notes():
    events = [
        NoteEvent(0, 24, 60, 0, is_grace=True, grace_type="acciaccatura"),
        NoteEvent(8, 24, 62, 0, is_grace=True, grace_type="acciaccatura"),
    ]

    base_note_width = 6.0

    without_gap = minimum_px_per_tick(
        events,
        base_note_width,
        scale_for_event=default_note_scale,
        grace_extra_gap_ratio=0.0,
    )
    with_gap = minimum_px_per_tick(
        events,
        base_note_width,
        scale_for_event=default_note_scale,
        grace_extra_gap_ratio=0.2,
    )

    assert with_gap > without_gap


def test_ornament_spacing_offsets_shift_following_noteheads():
    events = [
        NoteEvent(0, 24, 60, 0, is_grace=True, grace_type="acciaccatura"),
        NoteEvent(8, 24, 62, 0),
        NoteEvent(24, 24, 64, 0),
    ]

    offsets = ornament_spacing_offsets(events, base_note_width=10.0, grace_extra_gap_ratio=0.2)

    assert offsets[1] > offsets[0]
    assert offsets[2] == offsets[1]


def test_dotted_spacing_offsets_nudges_following_notes():
    events = [
        NoteEvent(0, 360, 60, 0, tied_durations=(360,)),
        NoteEvent(90, 120, 62, 0, tied_durations=(120,)),
        NoteEvent(240, 120, 64, 0, tied_durations=(120,)),
    ]

    offsets = dotted_spacing_offsets(
        events,
        base_note_width=6.0,
        pulses_per_quarter=480,
        px_per_tick=0.05,
        base_offsets=(0.0, 0.0, 0.0),
    )

    assert offsets[1] > offsets[0]
    assert offsets[2] == offsets[1]


def test_dot_gap_shrinks_when_space_is_cramped():
    note_width = 6.0
    default_gap = note_width * 0.45
    tight_gap = dot_gap_for_available_space(note_width, available_space=note_width * 0.4)
    relaxed_gap = dot_gap_for_available_space(note_width, available_space=note_width * 2)

    assert tight_gap < default_gap
    assert relaxed_gap == default_gap


def test_pdf_dots_stay_within_available_space():
    class _RecordingPage:
        def __init__(self):
            self.circles: list[tuple[float, float, float]] = []

        def draw_circle(
            self,
            x: float,
            y: float,
            radius: float,
            *,
            fill_gray: float | None = None,
            stroke_gray: float | None = None,
            line_width: float = 1.0,
        ) -> None:
            self.circles.append((x, y, radius))

    page = _RecordingPage()
    glyph = NoteGlyphDescription(base="quarter", dots=1)
    note_width = 10.0
    available_space = 5.0
    x_center = 50.0
    y_center = 20.0

    _draw_pdf_dots(
        page,
        x_center,
        y_center,
        note_width,
        glyph,
        scale=1.0,
        available_space=available_space,
    )

    assert page.circles
    dot_x, _, dot_radius = page.circles[0]
    note_right = x_center + note_width / 2.0
    padding = note_width * 0.05

    assert dot_x >= note_right
    assert dot_x + dot_radius <= note_right + available_space - padding + 1e-6
