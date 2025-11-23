"""Rendering helpers for the fingering diagram pages."""

from __future__ import annotations
import math
from typing import List, Sequence

from ...fingering import InstrumentSpec
from ...fingering.outline_renderer import generate_outline_path
from ..layouts import PdfLayout
from ..header import (
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ..notes import PatternData
from ..writer import PageBuilder


def build_fingering_pages(
    layout: PdfLayout,
    patterns: Sequence[PatternData],
    missing_notes: Sequence[str],
    instrument: InstrumentSpec,
    columns: int,
    *,
    header_lines: Sequence[HeaderLine] | None = None,
    header_on_first_page_only: bool = False,
) -> List[PageBuilder]:
    pages: List[PageBuilder] = []

    header_lines = tuple(header_lines if header_lines is not None else build_header_lines())

    def _header_for_page(page_index: int) -> tuple[HeaderLine, ...]:
        if not header_lines:
            return ()
        if header_on_first_page_only and page_index > 0:
            return ()
        return header_lines

    first_page_header = _header_for_page(0)
    header_height = compute_header_height(layout, first_page_header)
    header_gap = compute_header_gap(layout, first_page_header)

    available_width = layout.width - 2 * layout.margin_left
    content_top = layout.margin_top + header_height + header_gap
    available_height = layout.height - content_top - layout.margin_bottom
    heading_height = layout.font_size + 20
    spacing = 14.0
    label_height = layout.line_height * 1.6
    canvas_width = max(1.0, float(instrument.canvas_size[0] or 160))
    canvas_height = max(1.0, float(instrument.canvas_size[1] or 120))

    pattern_count = len(patterns)
    if pattern_count == 0:
        builder = PageBuilder(layout)
        page_header_lines = _header_for_page(len(pages))
        draw_document_header(builder, layout, page_header_lines)
        heading_top = content_top
        builder.draw_text(
            layout.margin_left,
            heading_top,
            "Used fingerings visuals",
            size=layout.font_size + 2,
        )
        y = heading_top + layout.line_height
        if missing_notes:
            builder.draw_text(
                layout.margin_left,
                y,
                _missing_fingering_text(missing_notes),
                size=layout.font_size - 1,
            )
        else:
            builder.draw_text(layout.margin_left, y, "(No fingering patterns detected)")
        pages.append(builder)
        return pages

    target_columns = _resolve_target_columns(
        requested=max(1, int(columns)),
        available_width=available_width,
        spacing=spacing,
        canvas_width=canvas_width,
    )
    column_width = (
        (available_width - (target_columns - 1) * spacing) / target_columns
        if target_columns > 0
        else available_width
    )
    if column_width <= 0:
        column_width = available_width

    min_scale = 0.4
    scale = column_width / canvas_width if canvas_width > 0 else 1.0
    scale = min(max(scale, min_scale), 1.1)

    desired_rows = 3 if layout.page_size == "A4" and layout.orientation == "landscape" else None
    if desired_rows:
        usable_height = available_height - heading_height + spacing
        if usable_height > spacing:
            max_row_height = max(64.0, (usable_height / desired_rows) - spacing)
            allowed_diagram_height = max_row_height - label_height
            if allowed_diagram_height > 0 and canvas_height > 0:
                scale = min(scale, allowed_diagram_height / canvas_height)
                scale = max(scale, min_scale)

    diagram_width = canvas_width * scale
    diagram_height = canvas_height * scale
    row_height = diagram_height + label_height

    rows_per_page = max(1, int((available_height - heading_height + spacing) // (row_height + spacing)))
    items_per_page = max(1, rows_per_page * target_columns)

    for start in range(0, pattern_count, items_per_page):
        page_patterns = patterns[start : start + items_per_page]
        builder = PageBuilder(layout)
        page_header_lines = _header_for_page(len(pages))
        draw_document_header(builder, layout, page_header_lines)
        heading_top = content_top
        builder.draw_text(
            layout.margin_left,
            heading_top,
            "Used fingerings visuals",
            size=layout.font_size + 2,
        )
        y_base = heading_top + layout.line_height + 4

        for idx, entry in enumerate(page_patterns):
            row = idx // target_columns
            col = idx % target_columns
            column_left = layout.margin_left + col * (column_width + spacing)
            diagram_left = column_left + (column_width - diagram_width) / 2
            block_top = y_base + row * (row_height + spacing)

            _render_fingering_block(
                builder,
                instrument,
                entry,
                diagram_left,
                block_top,
                diagram_width,
                diagram_height,
                scale,
                label_height,
            )

        if start == 0 and missing_notes:
            row_count = max(1, math.ceil(len(page_patterns) / target_columns))
            missing_y = y_base + row_count * (row_height + spacing)
            builder.draw_text(
                layout.margin_left,
                min(missing_y, layout.height - layout.margin_bottom - layout.line_height),
                _missing_fingering_text(missing_notes),
                size=layout.font_size - 1,
            )

        pages.append(builder)

    return pages


def _missing_fingering_text(missing_notes: Sequence[str]) -> str:
    joined = ", ".join(missing_notes)
    return f"Missing fingering patterns for: {joined}" if joined else "Missing fingering patterns"


def _render_fingering_block(
    page: PageBuilder,
    instrument: InstrumentSpec,
    entry: PatternData,
    diagram_left: float,
    block_top: float,
    diagram_width: float,
    diagram_height: float,
    scale: float,
    label_height: float,
) -> None:
    layout = page.layout
    label_lines = [", ".join(entry.note_names) or "(No note names)", f"Pattern: {entry.pattern_text}"]
    text_y = block_top
    for line in label_lines:
        page.draw_text(diagram_left, text_y, line, size=layout.font_size - 1)
        text_y += layout.line_height

    diagram_top = block_top + label_height
    page.draw_rect(
        diagram_left,
        diagram_top,
        diagram_width,
        diagram_height,
        fill_gray=0.98,
        stroke_gray=0.7,
        line_width=0.8,
    )

    outline = instrument.outline
    if outline and outline.points:
        path = generate_outline_path(
            outline.points,
            smooth=instrument.style.outline_smooth,
            closed=outline.closed,
            spline_steps=getattr(instrument.style, "outline_spline_steps", 48),
        )
        scaled_points = [
            (diagram_left + x * scale, diagram_top + y * scale)
            for x, y in path
        ]
        page.draw_polygon(
            scaled_points,
            stroke_gray=0.6,
            fill_gray=None,
            close=outline.closed,
            line_width=0.8,
        )

    holes = instrument.holes
    states = list(entry.pattern)
    if len(states) < len(holes):
        states.extend([0] * (len(holes) - len(states)))

    for hole, state in zip(holes, states):
        cx = diagram_left + hole.x * scale
        cy = diagram_top + hole.y * scale
        radius = max(2.0, hole.radius * scale)
        _draw_hole(page, cx, cy, radius, state)


def _draw_hole(page: PageBuilder, cx: float, cy: float, radius: float, state: int) -> None:
    clamped = max(0, min(2, int(state)))
    page.draw_circle(cx, cy, radius, stroke_gray=0.1, line_width=0.8)
    inner_radius = max(1.0, radius - 1.5)
    if clamped >= 2:
        page.draw_circle(cx, cy, inner_radius, fill_gray=0.15, stroke_gray=None)
    elif clamped == 1:
        page.fill_half_circle(cx, cy, inner_radius, fill_gray=0.15)


def _resolve_target_columns(
    *,
    requested: int,
    available_width: float,
    spacing: float,
    canvas_width: float,
) -> int:
    target = max(1, requested)
    min_scale = 0.45
    while target > 1:
        column_width = (
            (available_width - (target - 1) * spacing) / target if target > 0 else available_width
        )
        if column_width <= 0:
            target -= 1
            continue
        scale = column_width / canvas_width if canvas_width > 0 else 1.0
        if scale < min_scale:
            target -= 1
            continue
        return target
    return max(1, target)


__all__ = ["build_fingering_pages"]
