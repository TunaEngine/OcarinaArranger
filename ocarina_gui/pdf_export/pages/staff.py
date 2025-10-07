"""Rendering helpers for the staff notation pages."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Sequence

from ..layouts import PdfLayout
from ..header import (
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ..types import NoteEvent
from ..writer import PageBuilder
from ...note_values import NoteGlyphDescription, describe_note_glyph


SHARP_SEMITONES = {1, 3, 6, 8, 10}


def build_staff_pages(
    layout: PdfLayout,
    events: Sequence[NoteEvent],
    pulses_per_quarter: int,
) -> List[PageBuilder]:
    header_lines = build_header_lines()
    header_height = compute_header_height(layout, header_lines)
    header_gap = compute_header_gap(layout, header_lines)

    if not events:
        page = PageBuilder(layout)
        draw_document_header(page, layout, header_lines)
        content_top = layout.margin_top + header_height + header_gap
        page.draw_text(
            layout.margin_left,
            content_top,
            "Arranged staff view",
            size=layout.font_size + 2,
        )
        page.draw_text(
            layout.margin_left,
            content_top + layout.line_height,
            "(No arranged notes found)",
        )
        return [page]

    left = layout.margin_left
    width = max(1.0, layout.width - 2 * layout.margin_left)
    staff_spacing = 14.0
    staff_height = staff_spacing * 4
    system_padding = 32.0
    system_spacing = 36.0
    content_top = layout.margin_top + header_height + header_gap + layout.line_height * 2 + 20
    available_height = max(80.0, layout.height - layout.margin_bottom - content_top)
    system_total_height = staff_height + 2 * system_padding
    systems_per_page = max(
        1, int((available_height + system_spacing) // (system_total_height + system_spacing))
    )
    quarter_ticks = max(1, pulses_per_quarter or 1)
    ticks_per_measure = quarter_ticks * 4
    measures_per_system = max(1, int(width / 140.0))
    ticks_per_system = max(ticks_per_measure, measures_per_system * ticks_per_measure)
    ticks_per_page = max(quarter_ticks, ticks_per_system * systems_per_page)

    page_events: DefaultDict[int, list[NoteEvent]] = defaultdict(list)
    max_tick = 0
    for event in events:
        onset, duration, *_ = event
        index = int(onset // ticks_per_page)
        page_events[index].append(event)
        max_tick = max(max_tick, onset + duration)

    page_indices = sorted(page_events)
    total_pages = len(page_indices)
    pages: List[PageBuilder] = []

    for page_number, index in enumerate(page_indices, start=1):
        builder = PageBuilder(layout)
        _draw_staff_page(
            builder,
            page_events[index],
            page_number,
            index * ticks_per_page,
            total_pages,
            ticks_per_page,
            max_tick,
            pulses_per_quarter,
            systems_per_page,
            ticks_per_system,
            staff_spacing,
            system_padding,
            system_spacing,
            header_lines,
            header_height,
            header_gap,
        )
        pages.append(builder)

    return pages


def _draw_staff_page(
    page: PageBuilder,
    events: Sequence[NoteEvent],
    page_number: int,
    page_start: int,
    total_pages: int,
    ticks_per_page: int,
    max_tick: int,
    pulses_per_quarter: int,
    systems_per_page: int,
    ticks_per_system: int,
    staff_spacing: float,
    system_padding: float,
    system_spacing: float,
    header_lines: Sequence[str],
    header_height: float,
    header_gap: float,
) -> None:
    layout = page.layout
    left = layout.margin_left
    right = layout.width - layout.margin_left
    width = max(1.0, right - left)
    quarter_ticks = max(1, pulses_per_quarter or 1)

    heading = "Arranged staff view"
    if total_pages > 1:
        heading = f"{heading} (Page {page_number} of {total_pages})"
    draw_document_header(page, layout, header_lines)
    heading_top = layout.margin_top + header_height + header_gap
    page.draw_text(left, heading_top, heading, size=layout.font_size + 2)

    summary_y = heading_top + layout.line_height
    start_measure = int(page_start // (quarter_ticks * 4)) + 1
    remaining = max_tick - page_start
    span = max(quarter_ticks, min(ticks_per_page, remaining if remaining > 0 else ticks_per_page))
    end_measure = int((page_start + span - 1) // (quarter_ticks * 4)) + 1
    summary = (
        f"Staff visuals | Pulses/quarter: {pulses_per_quarter or 0}"
        f" | Measures {start_measure}-{end_measure} | Events on page: {len(events)}"
    )
    page.draw_text(left, summary_y, summary, size=layout.font_size - 1)

    staff_height = staff_spacing * 4
    staff_left = left + 40
    staff_right = left + width - 20
    system_height = staff_height + 2 * system_padding
    ticks_per_measure = quarter_ticks * 4

    for system_index in range(systems_per_page):
        system_start = page_start + system_index * ticks_per_system
        if system_start >= page_start + span:
            break
        system_remaining = span - (system_start - page_start)
        system_span = max(quarter_ticks, min(ticks_per_system, system_remaining))
        system_box_top = summary_y + layout.line_height + 16 + system_index * (
            system_height + system_spacing
        )
        staff_top = system_box_top + system_padding
        staff_bottom = staff_top + staff_height
        page.draw_rect(
            staff_left - 24,
            system_box_top,
            (staff_right - staff_left) + 48,
            system_height,
            fill_gray=0.97,
            stroke_gray=0.75,
            line_width=0.8,
        )

        for index in range(5):
            y = staff_top + index * staff_spacing
            page.draw_line(staff_left, y, staff_right, y, gray=0.2, line_width=1.0)

        staff_width = max(1.0, staff_right - staff_left - 20)
        scale_x = staff_width / max(1.0, float(system_span))

        tick = max(0, (system_start // ticks_per_measure) * ticks_per_measure)
        measure_font = max(6.0, layout.font_size - 3)
        while tick <= system_start + system_span:
            local = tick - system_start
            if local >= 0:
                x = staff_left + 10 + local * scale_x
                line_top = system_box_top + 6
                page.draw_line(x, line_top, x, staff_bottom + 18, gray=0.75, line_width=0.5)
                measure_number = tick // max(1, ticks_per_measure) + 1
                if measure_number > 1:
                    page.draw_text(
                        x + 2,
                        line_top - 4,
                        str(measure_number),
                        size=measure_font,
                        fill_gray=0.55,
                    )
            tick += ticks_per_measure

        system_end = system_start + system_span
        system_events = [
            event
            for event in events
            if event[0] < system_end and (event[0] + max(1, event[1])) > system_start
        ]

        if not system_events:
            continue

        for onset, duration, midi, _program in system_events:
            local_onset = max(0, onset - system_start)
            if local_onset >= system_span:
                continue

            pos = _staff_pos(midi)
            y_center = _staff_y(staff_top, pos, staff_spacing)
            x_center = staff_left + 10 + local_onset * scale_x
            note_radius = max(3.0, staff_spacing * 0.45)
            _draw_staff_ledger_lines(
                page,
                x_center,
                note_radius,
                staff_top,
                pos,
                staff_spacing,
            )

            glyph = describe_note_glyph(int(duration), pulses_per_quarter)
            if glyph is not None:
                _shade_note_head(page, x_center, y_center, note_radius, glyph)
            else:
                page.draw_circle(
                    x_center,
                    y_center,
                    note_radius,
                    fill_gray=0.1,
                    stroke_gray=0.05,
                    line_width=0.8,
                )

            if midi % 12 in SHARP_SEMITONES:
                page.draw_text(
                    x_center - note_radius - 6,
                    y_center + staff_spacing * 0.25,
                    "#",
                    size=layout.font_size - 2,
                )

            if glyph is not None:
                _draw_pdf_stem_and_flags(
                    page,
                    x_center,
                    y_center,
                    note_radius,
                    glyph,
                    pos,
                    staff_spacing,
                )
                _draw_pdf_dots(page, x_center, y_center, note_radius, glyph)

            octave = midi // 12 - 1
            if pos >= 8:
                octave_y = y_center - staff_spacing * 1.6
            else:
                octave_y = y_center + staff_spacing * 1.6
            page.draw_text(
                x_center,
                octave_y,
                str(octave),
                size=layout.font_size - 2,
            )


def _shade_note_head(
    page: PageBuilder,
    x_center: float,
    y_center: float,
    radius: float,
    glyph: NoteGlyphDescription,
) -> None:
    if glyph.base in {"whole", "half"}:
        page.draw_circle(
            x_center,
            y_center,
            radius,
            fill_gray=1.0,
            stroke_gray=0.05,
            line_width=0.8,
        )
    elif glyph.base != "":
        page.draw_circle(
            x_center,
            y_center,
            radius,
            fill_gray=0.1,
            stroke_gray=0.05,
            line_width=0.8,
        )


def _draw_pdf_stem_and_flags(
    page: PageBuilder,
    x_center: float,
    y_center: float,
    radius: float,
    glyph: NoteGlyphDescription,
    pos: int,
    spacing: float,
) -> None:
    if glyph.base == "whole":
        return

    stem_length = spacing * 3.5
    stem_up = pos < 6
    stem_x = x_center + radius if stem_up else x_center - radius
    stem_end_y = y_center - stem_length if stem_up else y_center + stem_length
    page.draw_line(
        stem_x,
        y_center,
        stem_x,
        stem_end_y,
        gray=0.0,
        line_width=1.0,
    )

    flag_map = {
        "eighth": 1,
        "sixteenth": 2,
        "thirty-second": 3,
        "sixty-fourth": 4,
    }
    flag_count = flag_map.get(glyph.base, 0)
    if flag_count == 0:
        return

    flag_length = radius * 2.2
    flag_height = spacing * 0.9
    for index in range(flag_count):
        if stem_up:
            start_y = stem_end_y + index * (flag_height * 0.65)
            page.draw_polygon(
                [
                    (stem_x, start_y),
                    (stem_x + flag_length, start_y + flag_height * 0.35),
                    (stem_x + flag_length * 0.85, start_y + flag_height),
                ],
                fill_gray=0.0,
                stroke_gray=None,
            )
        else:
            start_y = stem_end_y - index * (flag_height * 0.65)
            page.draw_polygon(
                [
                    (stem_x, start_y),
                    (stem_x - flag_length, start_y - flag_height * 0.35),
                    (stem_x - flag_length * 0.85, start_y - flag_height),
                ],
                fill_gray=0.0,
                stroke_gray=None,
            )


def _draw_pdf_dots(
    page: PageBuilder,
    x_center: float,
    y_center: float,
    radius: float,
    glyph: NoteGlyphDescription,
) -> None:
    if glyph.dots <= 0:
        return

    dot_radius = max(1.0, radius * 0.28)
    gap = radius * 0.9
    x = x_center + radius + gap
    for _ in range(glyph.dots):
        page.draw_circle(
            x,
            y_center,
            dot_radius,
            fill_gray=0.0,
            stroke_gray=0.0,
            line_width=0.6,
        )
        x += gap


def _staff_pos(midi: int) -> int:
    return int(round((midi - 64) * 7 / 12))


def _staff_y(staff_top: float, pos: int, spacing: float) -> float:
    return staff_top + (8 - pos) * (spacing / 2.0)


def _draw_staff_ledger_lines(
    page: PageBuilder,
    center: float,
    radius: float,
    staff_top: float,
    pos: int,
    spacing: float,
) -> None:
    extra = max(4.0, radius * 0.8)
    left = max(0.0, center - radius - extra)
    right = center + radius + extra
    if pos < 0:
        for ledger_pos in range(pos, 0, 2):
            y = _staff_y(staff_top, ledger_pos, spacing)
            page.draw_line(left, y, right, y, gray=0.4, line_width=0.6)
    elif pos > 8:
        for ledger_pos in range(10, pos + 1, 2):
            y = _staff_y(staff_top, ledger_pos, spacing)
            page.draw_line(left, y, right, y, gray=0.4, line_width=0.6)


__all__ = ["build_staff_pages"]
