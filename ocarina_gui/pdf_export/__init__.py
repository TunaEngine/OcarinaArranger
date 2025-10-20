"""Public interface for arranged PDF export."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from ocarina_tools.events import detect_tempo_bpm, get_note_events, get_tempo_changes

from ..fingering import get_current_instrument
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
    include_piano_roll: bool = True,
    include_staff: bool = True,
    include_text: bool = True,
    include_fingerings: bool = True,
) -> None:
    """Export the arranged score's fingering sequence to a PDF document."""

    layout = resolve_layout(page_size, orientation)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    events: list[NoteEvent]
    pulses_per_quarter: int
    events, pulses_per_quarter = get_note_events(root)
    events = sorted(events, key=lambda event: (event[0], event[2], event[1]))

    instrument = get_current_instrument()

    tempo_bpm = detect_tempo_bpm(root)
    tempo_changes = get_tempo_changes(root, default_bpm=tempo_bpm)
    tempo_base = first_tempo(tempo_changes, default=tempo_bpm)

    notes: list[ArrangedNote] = []
    grouped_patterns: list[PatternData] = []
    missing_notes: list[str] = []
    if include_text or include_fingerings:
        notes = collect_arranged_notes(events, instrument)
        if include_fingerings:
            grouped_patterns, missing_notes = group_patterns(notes)

    writer = PdfWriter(layout)

    if include_piano_roll:
        piano_pages = build_piano_roll_pages(
            layout,
            events,
            pulses_per_quarter,
            tempo_changes=tempo_changes,
            tempo_base=tempo_base,
        )
        for page in piano_pages:
            writer.add_page(page)

    if include_text:
        text_pages = build_text_page(
            layout,
            instrument,
            page_size.upper(),
            notes,
        )
        for page in text_pages:
            writer.add_page(page)

    if include_staff:
        staff_pages = build_staff_pages(
            layout,
            events,
            pulses_per_quarter,
            tempo_changes=tempo_changes,
            tempo_base=tempo_base,
        )
        for page in staff_pages:
            writer.add_page(page)

    if include_fingerings:
        fingering_pages = build_fingering_pages(
            layout, grouped_patterns, missing_notes, instrument, columns
        )
        for page in fingering_pages:
            writer.add_page(page)

    writer.write(output_file)
