"""Textual presentation page for the arranged PDF."""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from ..layouts import PdfLayout
from ..header import (
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ..notes import ArrangedNote
from ..writer import PageBuilder
from ...fingering import InstrumentSpec


TEXT_FONT = "F2"
_CHAR_WIDTH_SCALE = 0.6


def build_text_page(
    layout: PdfLayout,
    instrument: InstrumentSpec,
    page_size: str,
    notes: Sequence[ArrangedNote],
) -> List[PageBuilder]:
    entry_lines, hole_labels, column_offset = _build_document_lines(
        instrument, page_size, notes
    )

    header_lines = build_header_lines()
    header_height = compute_header_height(layout, header_lines)
    header_gap = compute_header_gap(layout, header_lines)

    char_step = layout.font_size * _CHAR_WIDTH_SCALE
    available_width = layout.width - 2 * layout.margin_left
    column_gap = layout.line_height * 1.5
    min_column_width = 150.0
    max_columns_by_width = max(
        1, int((available_width + column_gap) // (min_column_width + column_gap))
    )

    if not entry_lines:
        page = PageBuilder(layout)
        draw_document_header(page, layout, header_lines)
        label_top = layout.margin_top + header_height + header_gap
        label_height = _draw_fingering_labels(
            page,
            hole_labels,
            label_top,
            char_step,
            column_offset,
            [layout.margin_left],
        )
        y = label_top + label_height + layout.line_height
        page.draw_text(
            layout.margin_left,
            y,
            "(No arranged notes found)",
            font=TEXT_FONT,
        )
        return [page]

    pages: List[PageBuilder] = []
    total_entries = len(entry_lines)
    index = 0
    while index < total_entries:
        page = PageBuilder(layout)

        draw_document_header(page, layout, header_lines)

        label_top = layout.margin_top + header_height + header_gap
        remaining = total_entries - index
        estimated_label_height = _estimate_label_height(hole_labels, char_step)
        estimated_y_start = (
            label_top + estimated_label_height + layout.line_height * 0.5
        )
        available_height = layout.height - layout.margin_bottom - estimated_y_start
        lines_per_column = max(1, int(available_height // layout.line_height))
        columns_for_page = min(
            max_columns_by_width, max(1, math.ceil(remaining / lines_per_column))
        )
        required_per_column = math.ceil(remaining / columns_for_page)
        lines_per_column = min(lines_per_column, required_per_column)

        column_width = (
            (available_width - (columns_for_page - 1) * column_gap) / columns_for_page
            if columns_for_page > 0
            else available_width
        )

        column_origins = [
            layout.margin_left + column * (column_width + column_gap)
            for column in range(columns_for_page)
        ]

        label_height = _draw_fingering_labels(
            page,
            hole_labels,
            label_top,
            char_step,
            column_offset,
            column_origins,
        )
        y_start = label_top + label_height + layout.line_height * 0.5
        available_height = layout.height - layout.margin_bottom - y_start
        lines_per_column = max(1, int(available_height // layout.line_height))
        lines_per_column = min(lines_per_column, required_per_column)

        chunk_end = min(total_entries, index + columns_for_page * lines_per_column)
        chunk = entry_lines[index:chunk_end]

        for column, origin in enumerate(column_origins):
            column_lines = chunk[
                column * lines_per_column : (column + 1) * lines_per_column
            ]
            if not column_lines:
                break
            y = y_start
            for line in column_lines:
                page.draw_text(origin, y, line, font=TEXT_FONT)
                y += layout.line_height

        index += len(chunk)
        pages.append(page)

    return pages


def _build_document_lines(
    instrument: InstrumentSpec,
    page_size: str,
    notes: Sequence[ArrangedNote],
) -> Tuple[List[str], List[str], int]:
    del page_size  # unused but kept for signature compatibility

    entry_lines: List[str] = []
    hole_labels = list(_iter_hole_labels(instrument))

    for note in notes:
        entry_lines.append(f"{note.index:03d}   {note.note_name:<4}  {note.pattern_text}")

    column_offset = _fingering_column_offset(entry_lines, notes)
    return entry_lines, hole_labels, column_offset


def _iter_hole_labels(instrument: InstrumentSpec) -> Iterable[str]:
    for index, hole in enumerate(instrument.holes, start=1):
        identifier = (hole.identifier or "").strip()
        if not identifier:
            identifier = f"Hole {index}"
        yield identifier


def _draw_fingering_labels(
    page: PageBuilder,
    hole_labels: Sequence[str],
    top: float,
    char_step: float,
    column_offset: int,
    column_origins: Sequence[float],
) -> float:
    if not hole_labels:
        return 0.0

    max_height = 0.0
    for origin in column_origins:
        for index, label in enumerate(hole_labels):
            x = origin + (column_offset + index) * char_step
            page.draw_text(x, top, label, font=TEXT_FONT, angle=-90)
            max_height = max(max_height, len(label) * char_step)
    return max_height


def _estimate_label_height(hole_labels: Sequence[str], char_step: float) -> float:
    if not hole_labels:
        return 0.0
    max_chars = max(len(label) for label in hole_labels)
    return max_chars * char_step


def _fingering_column_offset(
    entry_lines: Sequence[str], notes: Sequence[ArrangedNote]
) -> int:
    if entry_lines and notes:
        sample_line = entry_lines[0]
        pattern = notes[0].pattern_text
        index = sample_line.find(pattern)
        if index >= 0:
            return index
    return len(f"{0:03d}   {'':<4}  ")


__all__ = ["build_text_page"]
