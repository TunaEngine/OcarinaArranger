import pytest

from ocarina_gui.pdf_export.header import (
    build_header_lines,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.pages import staff as staff_pages
from ocarina_gui.pdf_export.pages.staff import build_staff_pages
from ocarina_gui.pdf_export.writer import PageBuilder
from ocarina_tools import NoteEvent


def test_a6_staff_padding_has_spacing(monkeypatch):
    layout = resolve_layout("A6", "portrait")
    events = [NoteEvent(0, 240, 60, 0)]

    system_rects: list[tuple[float, float, float, float]] = []
    staff_lines: list[tuple[float, float, float, float]] = []

    original_draw_rect = PageBuilder.draw_rect
    original_draw_line = PageBuilder.draw_line

    def _record_rect(
        self, x, y, width, height, *, fill_gray=0.0, stroke_gray=None, line_width=1.0
    ):
        system_rects.append((x, y, width, height))
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

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(gray - 0.2) < 1e-6 and abs(line_width - 1.0) < 1e-6:
            staff_lines.append((x1, y1, x2, y2))
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    monkeypatch.setattr(PageBuilder, "draw_rect", _record_rect)
    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert system_rects, "expected staff systems to be drawn"
    assert staff_lines, "expected staff lines to be drawn"

    rect_left, rect_top, rect_width, rect_height = system_rects[0]
    rect_right = rect_left + rect_width
    rect_bottom = rect_top + rect_height

    first_staff_line = staff_lines[0]
    staff_left = min(first_staff_line[0], first_staff_line[2])
    staff_right = max(first_staff_line[0], first_staff_line[2])

    left_padding = staff_left - rect_left
    right_padding = rect_right - staff_right

    staff_y_values = [line[1] for line in staff_lines]
    assert len(staff_y_values) >= 5, "expected five staff lines"
    staff_y_values.sort()
    staff_spacing = abs(staff_y_values[1] - staff_y_values[0])
    staff_top = staff_y_values[0]
    staff_bottom = staff_y_values[-1]

    top_padding = staff_top - rect_top
    bottom_padding = rect_bottom - staff_bottom

    assert left_padding == pytest.approx(staff_spacing * 1.25, rel=1e-3)
    assert right_padding == pytest.approx(staff_spacing * 1.25, rel=1e-3)
    assert top_padding == pytest.approx(staff_spacing * 2.0, rel=1e-3)
    assert bottom_padding == pytest.approx(staff_spacing * 2.0, rel=1e-3)


def test_staff_pdf_barline_aligns_with_system_box(monkeypatch):
    layout = resolve_layout("A6", "portrait")
    events = [NoteEvent(0, 240, 60, 0), NoteEvent(240, 240, 62, 0)]

    system_box: tuple[float, float] | None = None
    bar_lines: list[tuple[float, float]] = []

    original_draw_rect = PageBuilder.draw_rect
    original_draw_line = PageBuilder.draw_line

    def _record_rect(
        self, x, y, width, height, *, fill_gray=0.0, stroke_gray=None, line_width=1.0
    ):
        nonlocal system_box
        system_box = (y, height)
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

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(x1 - x2) < 1e-6 and abs(gray - 0.75) < 1e-6 and abs(line_width - 0.5) < 1e-6:
            bar_lines.append((y1, y2))
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    monkeypatch.setattr(PageBuilder, "draw_rect", _record_rect)
    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert system_box is not None, "expected system rectangle to be recorded"
    assert bar_lines, "expected bar lines to be recorded"

    box_top, box_height = system_box
    box_bottom = box_top + box_height

    for y1, y2 in bar_lines:
        top = min(y1, y2)
        bottom = max(y1, y2)
        assert top == pytest.approx(box_top, abs=1e-6)
        assert bottom == pytest.approx(box_bottom, abs=1e-6)


def test_a6_staff_pages_pack_one_fewer_system(monkeypatch):
    layout = resolve_layout("A6", "portrait")
    events = [NoteEvent(0, 240, 60, 0), NoteEvent(1920, 240, 62, 0)]

    systems_per_page: list[int] = []

    original_draw_page = staff_pages._draw_staff_page

    def _record_systems(
        page,
        events,
        page_number,
        page_start,
        total_pages,
        ticks_per_page,
        max_tick,
        pulses_per_quarter,
        quarter_ticks,
        ticks_per_measure,
        systems_per_page_arg,
        ticks_per_system,
        staff_spacing,
        system_padding,
        system_spacing,
        header_lines,
        tempo_markers,
        heading,
        heading_top,
        systems_top,
    ):
        systems_per_page.append(systems_per_page_arg)
        return original_draw_page(
            page,
            events,
            page_number,
            page_start,
            total_pages,
            ticks_per_page,
            max_tick,
            pulses_per_quarter,
            quarter_ticks,
            ticks_per_measure,
            systems_per_page_arg,
            ticks_per_system,
            staff_spacing,
            system_padding,
            system_spacing,
            header_lines,
            tempo_markers,
            heading,
            heading_top,
            systems_top,
        )

    monkeypatch.setattr(staff_pages, "_draw_staff_page", _record_systems)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    header_lines = tuple(build_header_lines())
    header_height = compute_header_height(layout, header_lines)
    header_gap = compute_header_gap(layout, header_lines)
    heading_padding = layout.line_height * 0.8
    heading_extra = 8.0
    heading_top = layout.margin_top + header_height + header_gap + heading_padding
    systems_top = heading_top + heading_extra

    staff_scale = 0.45
    staff_spacing = 8.0 * staff_scale
    staff_height = staff_spacing * 4
    system_padding = staff_spacing * 2.0
    system_spacing = staff_spacing * 3.2
    content_top = systems_top
    available_height = max(80.0, layout.height - layout.margin_bottom - content_top)
    system_total_height = staff_height + 2 * system_padding
    base_systems_per_page = max(
        1, int((available_height + system_spacing) // (system_total_height + system_spacing))
    )
    expected_systems_per_page = max(1, base_systems_per_page - 1)

    assert systems_per_page, "expected at least one staff page to be drawn"
    assert all(count == expected_systems_per_page for count in systems_per_page), "A6 pages should leave one fewer system slot"


def test_a6_measure_spacing_uses_wide_staff(monkeypatch):
    layout = resolve_layout("A6", "portrait")
    events = [NoteEvent(0, 240, 60, 0), NoteEvent(960, 240, 62, 0)]

    note_centers: list[float] = []
    staff_lines: list[tuple[float, float, float, float]] = []

    original_draw_line = PageBuilder.draw_line
    original_draw_oval = PageBuilder.draw_oval

    def _record_line(self, x1, y1, x2, y2, *, gray=0.0, line_width=1.0):
        if abs(gray - 0.2) < 1e-6 and abs(line_width - 1.0) < 1e-6 and abs(y1 - y2) < 1e-6:
            staff_lines.append((x1, y1, x2, y2))
        return original_draw_line(self, x1, y1, x2, y2, gray=gray, line_width=line_width)

    def _record_oval(
        self,
        x,
        y,
        half_width,
        half_height,
        *,
        fill_gray=0.0,
        stroke_gray=0.0,
        line_width=1.0,
    ):
        note_centers.append(x)
        return original_draw_oval(
            self,
            x,
            y,
            half_width,
            half_height,
            fill_gray=fill_gray,
            stroke_gray=stroke_gray,
            line_width=line_width,
        )

    monkeypatch.setattr(PageBuilder, "draw_line", _record_line)
    monkeypatch.setattr(PageBuilder, "draw_oval", _record_oval)

    build_staff_pages(layout, events, pulses_per_quarter=480)

    assert len(note_centers) >= 2, "expected note heads to be recorded"
    assert staff_lines, "expected staff lines to be drawn"

    note_span = max(note_centers) - min(note_centers)
    staff_width = max(staff_lines[0][0], staff_lines[0][2]) - min(
        staff_lines[0][0], staff_lines[0][2]
    )

    assert note_span >= staff_width * 0.7, "notes should spread across most of the widened staff"
    assert note_span <= staff_width, "note spacing should stay within the staff bounds"
