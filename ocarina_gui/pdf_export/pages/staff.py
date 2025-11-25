"""Rendering helpers for the staff notation pages."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Sequence

from ..header import (
    HeaderLine,
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ..layouts import PdfLayout
from ..types import NoteEvent
from ..writer import PageBuilder
from ...staff.rendering.note_painter import GRACE_NOTE_SCALE
from ...staff.rendering.spacing import (
    default_note_scale,
    dotted_spacing_offsets,
    dot_gap_for_available_space,
    ornament_spacing_offsets,
)
from ...note_values import NoteGlyphDescription, describe_note_glyph
from ...staff.rendering.geometry import staff_pos, staff_y, tie_control_offsets
from shared.tempo import TempoChange, scaled_tempo_marker_pairs

from ._time_signature import ticks_per_measure

from ._tempo import (
    TEMPO_MARKER_BARLINE_PADDING,
    draw_tempo_marker,
    tempo_marker_total_width,
)


SHARP_SEMITONES = {1, 3, 6, 8, 10}
ACCIDENTAL_BASELINE_OFFSET_RATIO = 0.32
BASE_TARGET_PX_PER_TICK = 0.12
TARGET_PX_PER_TICK = BASE_TARGET_PX_PER_TICK
TIME_ZOOM_INCREASE = 1.1


def _note_scale(event: NoteEvent) -> float:
    return default_note_scale(event)


def _choose_measures_per_system(
    staff_width: float, ticks_per_measure: int, target_px_per_tick: float
) -> int:
    """Choose the number of measures per system to approximate UI spacing."""

    if target_px_per_tick <= 0:
        return 1

    approx_measures = staff_width / (ticks_per_measure * target_px_per_tick)
    lower = max(1, int(approx_measures))
    upper = lower if abs(approx_measures - lower) < 1e-6 else lower + 1

    def px_per_tick(measures: int) -> float:
        return staff_width / (ticks_per_measure * measures)

    target = target_px_per_tick
    lower_diff = abs(px_per_tick(lower) - target)
    upper_diff = abs(px_per_tick(upper) - target)
    return lower if lower_diff <= upper_diff else upper


def _target_px_per_tick(
    is_a6: bool, staff_spacing: float, events: Sequence[NoteEvent]
) -> float:
    base_note_width = staff_spacing * 1.5
    base_target = (
        BASE_TARGET_PX_PER_TICK * (0.5 if is_a6 else 1.0)
        * (TIME_ZOOM_INCREASE if is_a6 else 1.0)
    )
    _ = base_note_width  # reserved for future spacing tweaks
    return base_target


def build_staff_pages(
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
    header_lines = tuple(header_lines if header_lines is not None else build_header_lines())
    heading = (title or "").strip() or "Arranged staff view"

    def _header_for_page(page_index: int) -> tuple[HeaderLine, ...]:
        if not header_lines:
            return ()
        if header_on_first_page_only and page_index > 0:
            return ()
        return header_lines

    first_page_header = _header_for_page(0)
    header_height = compute_header_height(layout, first_page_header)
    header_gap = compute_header_gap(layout, first_page_header)
    heading_padding = layout.line_height * (0.8 if layout.page_size == "A6" else 2.0)
    heading_extra = 8.0 if layout.page_size == "A6" else 20.0
    heading_top = layout.margin_top + header_height + header_gap + heading_padding
    systems_top = heading_top + heading_extra

    if not events:
        page_header_lines = _header_for_page(0)
        page_header_height = compute_header_height(layout, page_header_lines)
        page_header_gap = compute_header_gap(layout, page_header_lines)
        page = PageBuilder(layout)
        draw_document_header(page, layout, page_header_lines)
        content_top = layout.margin_top + page_header_height + page_header_gap + heading_padding
        page.draw_text(layout.margin_left, content_top, heading, size=layout.font_size + 2)
        page.draw_text(
            layout.margin_left,
            content_top + layout.line_height,
            "(No arranged notes found)",
        )
        return [page]

    left = layout.margin_left
    width = max(1.0, layout.width - 2 * layout.margin_left)
    is_a6 = layout.page_size == "A6"
    staff_scale = 0.45 if is_a6 else 0.5
    staff_spacing = 8.0 * staff_scale
    staff_height = staff_spacing * 4
    system_padding = staff_spacing * (2.0 if is_a6 else 4.0)
    system_spacing = staff_spacing * (3.2 if is_a6 else 4.5)
    content_top = systems_top
    available_height = max(80.0, layout.height - layout.margin_bottom - content_top)
    system_total_height = staff_height + 2 * system_padding
    base_systems_per_page = max(
        1, int((available_height + system_spacing) // (system_total_height + system_spacing))
    )
    systems_per_page = max(1, base_systems_per_page - (1 if is_a6 and base_systems_per_page > 1 else 0))
    quarter_ticks = max(1, pulses_per_quarter or 1)
    measure_ticks = ticks_per_measure(quarter_ticks, beats, beat_type)
    staff_width = max(1.0, width - 80.0)
    target_px_per_tick = _target_px_per_tick(is_a6, staff_spacing, events)
    measures_per_system = _choose_measures_per_system(
        staff_width, measure_ticks, target_px_per_tick
    )
    ticks_per_system = max(measure_ticks, measures_per_system * measure_ticks)
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

    tempo_markers: tuple[tuple[int, str], ...] = ()
    if tempo_changes and tempo_base is not None:
        tempo_markers = scaled_tempo_marker_pairs(tempo_changes, tempo_base)

    for page_number, index in enumerate(page_indices, start=1):
        builder = PageBuilder(layout)
        page_header_lines = _header_for_page(page_number - 1)
        _draw_staff_page(
            builder,
            page_events[index],
            page_number,
            index * ticks_per_page,
            total_pages,
            ticks_per_page,
            max_tick,
            pulses_per_quarter,
            quarter_ticks,
            measure_ticks,
            systems_per_page,
            ticks_per_system,
            staff_spacing,
            system_padding,
            system_spacing,
            page_header_lines,
            tempo_markers,
            heading,
            heading_top,
            systems_top,
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
    quarter_ticks: int,
    ticks_per_measure: int,
    systems_per_page: int,
    ticks_per_system: int,
    staff_spacing: float,
    system_padding: float,
    system_spacing: float,
    header_lines: Sequence[HeaderLine],
    tempo_markers: Sequence[tuple[int, str]],
    heading: str,
    heading_top: float,
    systems_top: float,
) -> None:
    layout = page.layout
    header_height = compute_header_height(layout, header_lines)
    header_gap = compute_header_gap(layout, header_lines)
    left = layout.margin_left
    right = layout.width - layout.margin_left
    width = max(1.0, right - left)

    draw_document_header(page, layout, header_lines)
    heading_size = layout.font_size + (1 if layout.page_size == "A6" else 2)
    page.draw_text(left, heading_top, heading, size=heading_size)
    span = max(
        quarter_ticks,
        min(ticks_per_page, max_tick - page_start if max_tick > page_start else ticks_per_page),
    )

    staff_height = staff_spacing * 4
    staff_left = left + (8 if layout.page_size == "A6" else 40)
    staff_right = left + width - (2 if layout.page_size == "A6" else 20)
    system_height = staff_height + 2 * system_padding

    for system_index in range(systems_per_page):
        system_start = page_start + system_index * ticks_per_system
        if system_start >= page_start + span:
            break
        system_remaining = span - (system_start - page_start)
        system_span = max(quarter_ticks, min(ticks_per_system, system_remaining))
        system_box_top = systems_top + system_index * (system_height + system_spacing)
        staff_top = system_box_top + system_padding
        staff_bottom = staff_top + staff_height
        box_padding = staff_spacing * (1.25 if layout.page_size == "A6" else 6.0)
        page.draw_rect(
            staff_left - box_padding,
            system_box_top,
            (staff_right - staff_left) + box_padding * 2,
            system_height,
            fill_gray=0.97,
            stroke_gray=0.75,
            line_width=0.8,
        )

        for index in range(5):
            y = staff_top + index * staff_spacing
            page.draw_line(staff_left, y, staff_right, y, gray=0.2, line_width=1.0)

        staff_width = max(1.0, staff_right - staff_left - (2 if layout.page_size == "A6" else 20))
        scale_x = staff_width / max(1.0, float(system_span))
        system_left_x = staff_left + (4 if layout.page_size == "A6" else 10)
        system_right_x = system_left_x + system_span * scale_x

        system_end = system_start + system_span

        system_events = [
            event
            for event in events
            if event[0] < system_end and (event[0] + max(1, event[1])) > system_start
        ]
        system_events.sort(key=lambda event: event.onset)

        last_onset_in_span = max((event.onset for event in system_events), default=None)
        last_measure_tick = system_start + system_span
        if last_onset_in_span is not None:
            last_measure_tick = max(
                system_start,
                (last_onset_in_span // ticks_per_measure) * ticks_per_measure,
            )

        tick = max(0, (system_start // ticks_per_measure) * ticks_per_measure)
        measure_font = max(6.0, layout.font_size - 3)
        while tick <= last_measure_tick:
            local = tick - system_start
            if local >= 0:
                x = system_left_x + local * scale_x
                line_top = system_box_top
                line_bottom = system_box_top + system_height
                page.draw_line(x, line_top, x, line_bottom, gray=0.75, line_width=0.5)
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

        system_markers = [
            (tick, label)
            for tick, label in tempo_markers
            if system_start <= tick < system_end
        ]
        if system_markers:
            tempo_font = max(6.0, layout.font_size - 2.0)
            marker_y = system_box_top + 10
            for tick, label in system_markers:
                local = tick - system_start
                anchor_x = system_left_x + local * scale_x + TEMPO_MARKER_BARLINE_PADDING
                total_width = tempo_marker_total_width(page, label, tempo_font)
                max_left = max(system_left_x, system_right_x - total_width)
                left = max(system_left_x, min(max_left, anchor_x))
                draw_tempo_marker(page, left, marker_y, label, font_size=tempo_font)

        base_note_width = staff_spacing * 1.5
        ornament_offsets = ornament_spacing_offsets(
            system_events, base_note_width=base_note_width, grace_extra_gap_ratio=0.2
        )
        dotted_offsets = dotted_spacing_offsets(
            system_events,
            base_note_width=base_note_width,
            pulses_per_quarter=pulses_per_quarter,
            px_per_tick=scale_x,
            base_offsets=ornament_offsets,
            scale_for_event=default_note_scale,
        )
        spacing_offsets = tuple(
            (ornament or 0.0) + (dotted or 0.0)
            for ornament, dotted in zip(ornament_offsets, dotted_offsets)
        )

        if not system_events:
            continue

        event_starts: list[float] = []
        for event, offset_px in zip(system_events, spacing_offsets):
            local_start = max(0.0, event.onset - system_start)
            event_starts.append(system_left_x + local_start * scale_x + offset_px)

        base_note_width = staff_spacing * 1.5
        base_note_height = staff_spacing * 1.125
        for event_index, (event, offset_px) in enumerate(
            zip(system_events, spacing_offsets)
        ):
            pos = staff_pos(event.midi)
            y_center = staff_y(staff_top, pos, staff_spacing)
            scale = _note_scale(event)
            note_width = base_note_width * scale
            note_height = base_note_height * scale
            note_half_width = note_width / 2.0
            drawn_segments: list[tuple[int, float, bool, bool]] = []
            segment_offsets = (0, *event.tie_offsets)
            system_end = system_start + system_span

            for segment_index, (segment_duration, offset) in enumerate(
                zip(event.tied_durations, segment_offsets)
            ):
                segment_start = event.onset + offset
                segment_end = segment_start + max(1, segment_duration)
                if segment_end <= system_start or segment_start >= system_end:
                    continue
                local_onset = max(0.0, segment_start - system_start)
                if local_onset >= system_span:
                    continue

                x_center = (
                    staff_left + 10 + local_onset * scale_x + note_half_width + offset_px
                )
                available_space = None
                if event_index < len(event_starts) - 1:
                    available_space = event_starts[event_index + 1] - (
                        x_center + note_half_width
                    )
                has_incoming = False
                if segment_index > 0:
                    prev_start = event.onset + segment_offsets[segment_index - 1]
                    prev_duration = max(1, event.tied_durations[segment_index - 1])
                    prev_end = prev_start + prev_duration
                    has_incoming = prev_end <= system_start

                has_outgoing = False
                if segment_index < len(event.tied_durations) - 1:
                    next_offset = event.tie_offsets[segment_index]
                    next_start = event.onset + next_offset
                    has_outgoing = next_start >= system_end

                drawn_segments.append(
                    (segment_index, x_center, has_incoming, has_outgoing)
                )
                _draw_staff_ledger_lines(
                    page,
                    x_center,
                    note_width,
                    staff_top,
                    pos,
                    staff_spacing,
                )

                glyph = describe_note_glyph(int(segment_duration), pulses_per_quarter)
                if glyph is not None:
                    _shade_note_head(
                        page,
                        x_center,
                        y_center,
                        note_width,
                        note_height,
                        glyph,
                        scale=scale,
                    )
                else:
                    page.draw_oval(
                        x_center,
                        y_center,
                        note_half_width,
                        note_height / 2.0,
                        fill_gray=0.1,
                        stroke_gray=0.05,
                        line_width=0.8,
                    )

                if segment_index == 0 and event.midi % 12 in SHARP_SEMITONES:
                    font_size = layout.font_size - 2
                    page.draw_text(
                        x_center - staff_spacing * 2.0,
                        y_center + font_size * ACCIDENTAL_BASELINE_OFFSET_RATIO,
                        "#",
                        size=font_size,
                    )

                if glyph is not None:
                    _draw_pdf_stem_and_flags(
                        page,
                        x_center,
                        y_center,
                        note_width,
                        glyph,
                        pos,
                        staff_spacing,
                        scale=scale,
                    )
                    _draw_pdf_dots(
                        page,
                        x_center,
                        y_center,
                        note_width,
                        glyph,
                        scale=scale,
                        available_space=available_space,
                    )

            if len(drawn_segments) > 1:
                for (left_index, left_center, _, _), (
                    right_index,
                    right_center,
                    _,
                    _,
                ) in zip(drawn_segments, drawn_segments[1:]):
                    if right_index != left_index + 1:
                        continue
                    start_x = left_center + note_width * 0.45
                    end_x = right_center - note_width * 0.45
                    if end_x <= start_x:
                        continue
                    _draw_pdf_tie(page, start_x, end_x, y_center, staff_spacing, pos)

            for segment_index, center, has_incoming, has_outgoing in drawn_segments:
                if has_incoming:
                    start_x = max(staff_left, system_left_x - note_width * 1.35)
                    end_x = center - note_width * 0.45
                    if end_x > start_x:
                        _draw_pdf_tie(page, start_x, end_x, y_center, staff_spacing, pos)
                if has_outgoing:
                    start_x = center + note_width * 0.45
                    end_x = min(staff_right, system_right_x + note_width * 1.35)
                    if end_x > start_x:
                        _draw_pdf_tie(page, start_x, end_x, y_center, staff_spacing, pos)

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


def _shade_note_head(
    page: PageBuilder,
    x_center: float,
    y_center: float,
    width: float,
    height: float,
    glyph: NoteGlyphDescription,
    *,
    scale: float = 1.0,
) -> None:
    half_width = width / 2.0
    half_height = height / 2.0
    line_width = max(0.5, 0.8 * scale)
    if glyph.base in {"whole", "half"}:
        page.draw_oval(
            x_center,
            y_center,
            half_width,
            half_height,
            fill_gray=1.0,
            stroke_gray=0.05,
            line_width=line_width,
        )
    elif glyph.base != "":
        page.draw_oval(
            x_center,
            y_center,
            half_width,
            half_height,
            fill_gray=0.1,
            stroke_gray=0.05,
            line_width=line_width,
        )


def _draw_pdf_stem_and_flags(
    page: PageBuilder,
    x_center: float,
    y_center: float,
    note_width: float,
    glyph: NoteGlyphDescription,
    pos: int,
    spacing: float,
    *,
    scale: float = 1.0,
) -> None:
    if glyph.base == "whole":
        return

    stem_length = spacing * 3.5 * max(scale, 0.1)
    stem_up = pos < 6
    stem_x = (
        x_center + note_width / 2.0 if stem_up else x_center - note_width / 2.0
    )
    stem_end_y = y_center - stem_length if stem_up else y_center + stem_length
    page.draw_line(
        stem_x,
        y_center,
        stem_x,
        stem_end_y,
        gray=0.0,
        line_width=max(0.6, 1.0 * scale),
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

    flag_length = note_width * 1.2
    flag_height = spacing * 0.9 * max(scale, 0.1)
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
    note_width: float,
    glyph: NoteGlyphDescription,
    *,
    scale: float = 1.0,
    available_space: float | None = None,
) -> None:
    if glyph.dots <= 0:
        return

    dot_radius = max(1.0, note_width * 0.18)
    gap = note_width * 0.45
    if available_space is not None:
        gap = dot_gap_for_available_space(note_width, available_space)
    half_width = note_width / 2.0
    x = x_center + half_width + gap
    line_width = max(0.4, 0.6 * scale)
    for _ in range(glyph.dots):
        page.draw_circle(
            x,
            y_center,
            dot_radius,
            fill_gray=0.0,
            stroke_gray=0.0,
            line_width=line_width,
        )
        x += gap


def _draw_pdf_tie(
    page: PageBuilder,
    start_x: float,
    end_x: float,
    y_center: float,
    spacing: float,
    pos: int,
) -> None:
    if end_x - start_x <= 1.0:
        return

    base_offset, curve_offset = tie_control_offsets(spacing, pos)
    thickness = max(0.5, spacing * 0.18)
    base_y = y_center + base_offset
    control_y = y_center + curve_offset
    direction = 1 if pos < 6 else -1
    outer_base_y = base_y + direction * thickness
    outer_control_y = control_y + direction * thickness
    ts = (0.0, 0.25, 0.5, 0.75, 1.0)

    inner_points = [
        (
            start_x + (end_x - start_x) * t,
            _quadratic_point(base_y, control_y, base_y, t),
        )
        for t in ts
    ]
    outer_points = [
        (
            end_x - (end_x - start_x) * t,
            _quadratic_point(outer_base_y, outer_control_y, outer_base_y, t),
        )
        for t in ts
    ]
    page.draw_polygon(inner_points + outer_points, fill_gray=0.0, stroke_gray=None)


def _draw_staff_ledger_lines(
    page: PageBuilder,
    center: float,
    note_width: float,
    staff_top: float,
    pos: int,
    spacing: float,
) -> None:
    extra = max(4.0, note_width * 0.25)
    half_width = note_width / 2.0
    left = max(0.0, center - half_width - extra)
    right = center + half_width + extra
    if pos < -1:
        start = pos if pos % 2 == 0 else pos + 1
        for ledger_pos in range(start, 0, 2):
            y = staff_y(staff_top, ledger_pos, spacing)
            page.draw_line(left, y, right, y, gray=0.4, line_width=0.6)
    elif pos > 9:
        for ledger_pos in range(10, pos + 1, 2):
            y = staff_y(staff_top, ledger_pos, spacing)
            page.draw_line(left, y, right, y, gray=0.4, line_width=0.6)


def _quadratic_point(start: float, control: float, end: float, t: float) -> float:
    return (1 - t) * (1 - t) * start + 2 * (1 - t) * t * control + t * t * end


__all__ = ["build_staff_pages"]
