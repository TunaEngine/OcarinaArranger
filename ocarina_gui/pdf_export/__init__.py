"""Public interface for arranged PDF export."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import xml.etree.ElementTree as ET

from ocarina_tools.events import (
    detect_tempo_bpm,
    get_note_events,
    get_tempo_changes,
    get_time_signature,
)

from ..fingering import get_current_instrument
from ..events import trim_leading_silence
from .header import build_header_lines
from .layouts import resolve_layout
from .notes import ArrangedNote, PatternData, collect_arranged_notes, group_patterns
from .types import NoteEvent
from .pages.fingering import build_fingering_pages
from .pages.piano_roll import build_piano_roll_pages
from .pages.staff import build_staff_pages
from .pages.text import build_text_page
from .writer import PdfWriter
from shared.tempo import first_tempo

__all__ = ["export_arranged_pdf"]


def export_arranged_pdf(
    root: ET.Element,
    output_path: str,
    page_size: str,
    orientation: str,
    columns: int,
    prefer_flats: bool,
    *,
    events: Sequence[NoteEvent] | None = None,
    pulses_per_quarter: int | None = None,
    beats: int | None = None,
    beat_type: int | None = None,
    include_piano_roll: bool = True,
    include_staff: bool = True,
    include_text: bool = False,
    include_fingerings: bool = True,
) -> None:
    """Export the arranged score's fingering sequence to a PDF document."""

    layout = resolve_layout(page_size, orientation)
    title = _extract_title(root)
    header_lines = build_header_lines()
    header_available = bool(header_lines)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    resolved_events: list[NoteEvent] | None = None
    resolved_ppq: int | None = pulses_per_quarter

    if events is not None:
        resolved_events = list(events)

    if resolved_ppq is None or resolved_events is None:
        fallback_events, fallback_ppq = get_note_events(root)
        if resolved_events is None:
            resolved_events = list(fallback_events)
        if resolved_ppq is None:
            resolved_ppq = fallback_ppq

    beats_from_score, beat_type_from_score = get_time_signature(root)
    beats = max(1, int(beats or beats_from_score or 4))
    beat_type = max(1, int(beat_type or beat_type_from_score or 4))

    resolved_events = trim_leading_silence(
        sorted(resolved_events, key=lambda event: (event[0], event[2], event[1]))
    )
    resolved_ppq = resolved_ppq or 0

    instrument = get_current_instrument()

    tempo_bpm = detect_tempo_bpm(root)
    tempo_changes = get_tempo_changes(root, default_bpm=tempo_bpm)
    tempo_base = first_tempo(tempo_changes, default=tempo_bpm)

    notes: list[ArrangedNote] = []
    grouped_patterns: list[PatternData] = []
    missing_notes: list[str] = []
    if include_text or include_fingerings:
        notes = collect_arranged_notes(resolved_events, instrument)
        if include_fingerings:
            grouped_patterns, missing_notes = group_patterns(notes)

    writer = PdfWriter(layout)

    if include_piano_roll:
        piano_header_lines = header_lines if header_available else ()
        piano_pages = build_piano_roll_pages(
            layout,
            resolved_events,
            resolved_ppq,
            beats=beats,
            beat_type=beat_type,
            tempo_changes=tempo_changes,
            tempo_base=tempo_base,
            header_lines=piano_header_lines,
            header_on_first_page_only=header_available,
            title=title,
        )
        for page in piano_pages:
            writer.add_page(page)
        if piano_pages:
            header_available = False

    if include_text:
        text_header_lines = header_lines if header_available else ()
        text_pages = build_text_page(
            layout,
            instrument,
            page_size.upper(),
            notes,
            header_lines=text_header_lines,
            header_on_first_page_only=header_available,
        )
        for page in text_pages:
            writer.add_page(page)
        if text_pages:
            header_available = False

    if include_staff:
        staff_header_lines = header_lines if header_available else ()
        staff_pages = build_staff_pages(
            layout,
            resolved_events,
            resolved_ppq,
            beats=beats,
            beat_type=beat_type,
            tempo_changes=tempo_changes,
            tempo_base=tempo_base,
            header_lines=staff_header_lines,
            header_on_first_page_only=header_available,
            title=title,
        )
        for page in staff_pages:
            writer.add_page(page)
        if staff_pages:
            header_available = False

    if include_fingerings:
        fingering_header_lines = header_lines if header_available else ()
        fingering_pages = build_fingering_pages(
            layout,
            grouped_patterns,
            missing_notes,
            instrument,
            columns,
            include_text=include_text,
            header_lines=fingering_header_lines,
            header_on_first_page_only=header_available,
        )
        for page in fingering_pages:
            writer.add_page(page)

    writer.write(output_file)


def _extract_title(root: ET.Element) -> str | None:
    def _text_for(tag: str) -> str | None:
        element = root.find(f".//{tag}")
        if element is not None and element.text:
            value = element.text.strip()
            if value:
                return value
        namespaced = root.find(f".//{{*}}{tag}")
        if namespaced is not None and namespaced.text:
            value = namespaced.text.strip()
            if value:
                return value
        return None

    for candidate in ("work-title", "movement-title", "credit-words", "title"):
        value = _text_for(candidate)
        if value:
            return value

    for attr in ("title", "name"):
        value = root.attrib.get(attr, "").strip()
        if value:
            return value

    return None
