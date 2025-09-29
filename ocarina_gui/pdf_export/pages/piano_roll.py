"""Rendering helpers for the piano roll pages."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Sequence

from ocarina_tools import midi_to_name as pitch_midi_to_name

from ..layouts import PdfLayout
from ..types import NoteEvent
from ..writer import PageBuilder


def build_piano_roll_pages(
    layout: PdfLayout,
    events: Sequence[NoteEvent],
    pulses_per_quarter: int,
    prefer_flats: bool,
) -> List[PageBuilder]:
    """Render one or more piano roll pages depending on song length."""

    if not events:
        page = PageBuilder(layout)
        page.draw_text(
            layout.margin_left,
            layout.margin_top,
            "Arranged piano roll",
            size=layout.font_size + 2,
        )
        page.draw_text(
            layout.margin_left,
            layout.margin_top + layout.line_height,
            "(No arranged notes found)",
        )
        return [page]

    left = layout.margin_left
    width = max(1.0, layout.width - 2 * layout.margin_left)
    label_width = max(32.0, layout.font_size * 2.5)
    quarter_ticks = max(1, pulses_per_quarter or 1)
    quarters_per_page = max(4, int(width / 18.0))
    ticks_per_page = max(quarter_ticks * 4, quarters_per_page * quarter_ticks)

    min_midi = min(event[2] for event in events)
    max_midi = max(event[2] for event in events)
    if min_midi == max_midi:
        min_midi = max(0, min_midi - 2)
        max_midi = min(127, max_midi + 2)
    else:
        min_midi = max(0, min_midi - 1)
        max_midi = min(127, max_midi + 1)

    low_name = pitch_midi_to_name(min_midi, flats=prefer_flats)
    high_name = pitch_midi_to_name(max_midi, flats=prefer_flats)

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
            min_midi,
            max_midi,
            low_name,
            high_name,
            pulses_per_quarter,
            prefer_flats,
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
    min_midi: int,
    max_midi: int,
    low_name: str,
    high_name: str,
    pulses_per_quarter: int,
    prefer_flats: bool,
) -> None:
    layout = page.layout
    heading = "Arranged piano roll"
    if total_pages > 1:
        heading = f"{heading} (Page {page_number} of {total_pages})"
    page.draw_text(left, layout.margin_top, heading, size=layout.font_size + 2)

    remaining_ticks = max_tick - page_start
    span = max(
        quarter_ticks,
        min(ticks_per_page, remaining_ticks if remaining_ticks > 0 else ticks_per_page),
    )
    page_span = max(quarter_ticks, ticks_per_page)
    grid_width = max(1.0, width - label_width)
    scale_x = grid_width / max(1.0, float(page_span))

    start_measure = int(page_start // (quarter_ticks * 4)) + 1
    end_measure = int((page_start + span - 1) // (quarter_ticks * 4)) + 1

    summary = (
        f"Range: {low_name} to {high_name} | Pulses/quarter: {pulses_per_quarter or 0}"
        f" | Measures {start_measure}-{end_measure} | Events on page: {len(events)}"
    )
    summary_y = layout.margin_top + layout.line_height
    page.draw_text(left, summary_y, summary, size=layout.font_size - 1)

    grid_top = summary_y + layout.line_height + 6
    grid_bottom = layout.height - layout.margin_bottom
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
        label = pitch_midi_to_name(midi, flats=prefer_flats)
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

    tick = max(0, (page_start // quarter_ticks) * quarter_ticks)
    page_end = page_start + page_span
    while tick <= page_end:
        local = tick - page_start
        if local >= 0:
            x = grid_left + local * scale_x
            page.draw_line(x, grid_top, x, grid_top + actual_height, gray=0.85, line_width=0.5)
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
        name_text = pitch_midi_to_name(midi, flats=prefer_flats)
        label_x = grid_left + local_onset * scale_x + 2.0
        primary_size = max(6.0, min(layout.font_size - 2.0, note_height * 0.55))
        name_baseline = min(note_y + note_height - 1.0, note_y + note_height * 0.6)
        page.draw_text(label_x, name_baseline, name_text, size=primary_size, fill_gray=1.0)


__all__ = ["build_piano_roll_pages"]
