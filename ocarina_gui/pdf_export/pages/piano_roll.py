"""Rendering helpers for the piano roll pages."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Sequence

from ocarina_tools import midi_to_name as pitch_midi_to_name
from shared.tempo import TempoChange, scaled_tempo_marker_pairs

from ._time_signature import ticks_per_measure

from ._tempo import (
    TEMPO_MARKER_BARLINE_PADDING,
    draw_tempo_marker,
    tempo_marker_total_width,
)

from ..layouts import PdfLayout
from ..header import (
    HeaderLine,
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ..types import NoteEvent
from ..writer import PageBuilder


def build_piano_roll_pages(
    layout: PdfLayout,
    events: Sequence[NoteEvent],
    pulses_per_quarter: int,
    *,
    beats: int = 4,
    beat_type: int = 4,
    tempo_changes: Sequence[TempoChange] | None = None,
    tempo_base: float | None = None,
    header_lines: Sequence[HeaderLine] | None = None,
    header_on_first_page_only: bool = False,
    title: str | None = None,
) -> List[PageBuilder]:
    """Render one or more piano roll pages depending on song length."""

    header_lines = tuple(header_lines if header_lines is not None else build_header_lines())
    heading = (title or "").strip() or "Arranged piano roll"

    def _header_for_page(page_index: int) -> tuple[HeaderLine, ...]:
        if not header_lines:
            return ()
        if header_on_first_page_only and page_index > 0:
            return ()
        return header_lines

    if not events:
        page_header_lines = _header_for_page(0)
        header_height = compute_header_height(layout, page_header_lines)
        header_gap = compute_header_gap(layout, page_header_lines)
        page = PageBuilder(layout)
        draw_document_header(page, layout, page_header_lines)
        content_top = layout.margin_top + header_height + header_gap
        page.draw_text(layout.margin_left, content_top, heading, size=layout.font_size + 2)
        page.draw_text(
            layout.margin_left,
            content_top + layout.line_height,
            "(No arranged notes found)",
        )
        return [page]

    left = layout.margin_left
    width = max(1.0, layout.width - 2 * layout.margin_left)
    label_width = max(32.0, layout.font_size * 2.5)
    quarter_ticks = max(1, pulses_per_quarter or 1)
    measure_ticks = ticks_per_measure(quarter_ticks, beats, beat_type)
    target_px_per_quarter = 18.0 * (0.5 if layout.page_size == "A6" else 1.0)
    quarters_per_page = max(4, int(width / target_px_per_quarter))
    ticks_per_page = max(measure_ticks, quarters_per_page * quarter_ticks)

    min_midi = min(event[2] for event in events)
    max_midi = max(event[2] for event in events)
    if min_midi == max_midi:
        min_midi = max(0, min_midi - 2)
        max_midi = min(127, max_midi + 2)
    else:
        min_midi = max(0, min_midi - 1)
        max_midi = min(127, max_midi + 1)

    low_name = pitch_midi_to_name(min_midi, flats=False)
    high_name = pitch_midi_to_name(max_midi, flats=False)

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

    tempo_markers: tuple[tuple[int, str], ...] = ()
    if tempo_changes and tempo_base is not None:
        tempo_markers = scaled_tempo_marker_pairs(tempo_changes, tempo_base)

    for page_number, index in enumerate(page_indices, start=1):
        builder = PageBuilder(layout)
        page_header_lines = _header_for_page(page_number - 1)
        header_height = compute_header_height(layout, page_header_lines)
        header_gap = compute_header_gap(layout, page_header_lines)
        _draw_piano_roll_page(
            builder,
            page_events[index],
            page_number,
            index * ticks_per_page,
            total_pages,
            ticks_per_page,
            max_tick,
            left,
            width,
            label_width,
            quarter_ticks,
            measure_ticks,
            min_midi,
            max_midi,
            low_name,
            high_name,
            pulses_per_quarter,
            page_header_lines,
            header_height,
            header_gap,
            tempo_markers,
            heading,
        )
        pages.append(builder)

    return pages


def _draw_piano_roll_page(
    page: PageBuilder,
    events: Sequence[NoteEvent],
    page_number: int,
    page_start: int,
    total_pages: int,
    ticks_per_page: int,
    max_tick: int,
    left: float,
    width: float,
    label_width: float,
    quarter_ticks: int,
    ticks_per_measure: int,
    min_midi: int,
    max_midi: int,
    low_name: str,
    high_name: str,
    pulses_per_quarter: int,
    header_lines: Sequence[HeaderLine],
    header_height: float,
    header_gap: float,
    tempo_markers: Sequence[tuple[int, str]],
    heading: str,
) -> None:
    layout = page.layout
    draw_document_header(page, layout, header_lines)
    heading_top = layout.margin_top + header_height + header_gap
    page.draw_text(left, heading_top, heading, size=layout.font_size + 2)

    remaining_ticks = max_tick - page_start
    span = max(
        quarter_ticks,
        min(ticks_per_page, remaining_ticks if remaining_ticks > 0 else ticks_per_page),
    )
    page_span = max(quarter_ticks, ticks_per_page)
    grid_width = max(1.0, width - label_width)
    scale_x = grid_width / max(1.0, float(page_span))

    markers_on_page = [
        (tick, label)
        for tick, label in tempo_markers
        if page_start <= tick < page_start + page_span
    ]
    marker_height = layout.line_height if markers_on_page else 0.0
    marker_y = heading_top + layout.line_height + 4
    grid_top = heading_top + layout.line_height + 6 + marker_height
    footer_padding = layout.line_height * (1.5 if total_pages > 1 else 0.5)
    grid_bottom = layout.height - layout.margin_bottom - footer_padding
    grid_bottom = max(grid_top + 24.0, grid_bottom)
    available_height = max(40.0, grid_bottom - grid_top)

    note_count = max(1, max_midi - min_midi + 1)
    row_height = max(6.0, available_height / note_count)
    actual_height = row_height * note_count

    row_midis = list(range(max_midi, min_midi - 1, -1))
    grid_left = left + label_width
    for idx, midi in enumerate(row_midis):
        row_y = grid_top + idx * row_height
        fill = 0.93 if midi % 12 in (1, 3, 6, 8, 10) else 0.97
        page.draw_rect(grid_left, row_y, grid_width, row_height, fill_gray=fill, stroke_gray=None)
        label = pitch_midi_to_name(midi, flats=False)
        page.draw_rect(
            left,
            row_y,
            label_width,
            row_height,
            fill_gray=0.99,
            stroke_gray=0.85,
            line_width=0.3,
        )
        page.draw_text(left + 4, row_y + row_height - 4, label, size=layout.font_size - 2)

    page.draw_rect(grid_left, grid_top, grid_width, actual_height, stroke_gray=0.6, fill_gray=None, line_width=0.8)
    page.draw_line(grid_left, grid_top, grid_left, grid_top + actual_height, gray=0.6, line_width=0.8)

    if markers_on_page:
        tempo_font = max(6.0, layout.font_size - 2.0)
        for tick, label in markers_on_page:
            local = tick - page_start
            anchor_x = grid_left + local * scale_x + TEMPO_MARKER_BARLINE_PADDING
            total_width = tempo_marker_total_width(page, label, tempo_font)
            max_left = max(grid_left, grid_left + grid_width - total_width)
            left = max(grid_left, min(max_left, anchor_x))
            draw_tempo_marker(page, left, marker_y, label, font_size=tempo_font)

    tick = max(0, (page_start // quarter_ticks) * quarter_ticks)
    page_end = page_start + page_span
    measure_ticks = quarter_ticks * 4
    measure_font = max(6.0, layout.font_size - 3.0)
    label_offset = min(row_height * 0.6, 14.0)
    while tick <= page_end:
        local = tick - page_start
        if local >= 0:
            x = grid_left + local * scale_x
            is_measure = measure_ticks > 0 and tick % measure_ticks == 0
            line_gray = 0.55 if is_measure else 0.85
            line_width = 0.8 if is_measure else 0.5
            page.draw_line(x, grid_top, x, grid_top + actual_height, gray=line_gray, line_width=line_width)
            if is_measure and measure_ticks > 0:
                measure_number = tick // max(1, measure_ticks) + 1
                if measure_number > 1:
                    page.draw_text(
                        x + 2.0,
                        grid_top + label_offset,
                        str(measure_number),
                        size=measure_font,
                        fill_gray=0.35,
                    )
        tick += quarter_ticks

    for onset, duration, midi, _program in events:
        local_onset = max(0, onset - page_start)
        if local_onset >= page_span:
            continue
        local_end = min(page_span, local_onset + max(1, duration))
        width_note = max(2.0, (local_end - local_onset) * scale_x)
        row_index = max(0, min(len(row_midis) - 1, max_midi - midi))
        row_y = grid_top + row_index * row_height
        note_y = row_y + 1.0
        note_height = max(2.0, row_height - 2.0)
        fill_gray = 0.35 if midi % 12 in (1, 3, 6, 8, 10) else 0.2
        page.draw_rect(
            grid_left + local_onset * scale_x,
            note_y,
            width_note,
            note_height,
            fill_gray=fill_gray,
            stroke_gray=0.1,
            line_width=0.8,
        )
        name_text = pitch_midi_to_name(midi, flats=False)
        label_x = grid_left + local_onset * scale_x + 2.0
        primary_size = max(6.0, min(layout.font_size - 2.0, note_height * 0.55))
        name_baseline = min(note_y + note_height - 1.0, note_y + note_height * 0.6)
        page.draw_text(label_x, name_baseline, name_text, size=primary_size, fill_gray=1.0)

    if total_pages > 1:
        footer_text = f"Page {page_number} of {total_pages}"
        footer_size = max(6.0, layout.font_size - 3)
        footer_width = page.estimate_text_width(footer_text, size=footer_size)
        footer_y = layout.height - layout.margin_bottom + layout.line_height * 0.25
        footer_x = max(layout.margin_left, layout.width - layout.margin_left - footer_width)
        page.draw_text(
            footer_x,
            footer_y,
            footer_text,
            size=footer_size,
            fill_gray=0.5,
        )


__all__ = ["build_piano_roll_pages"]
