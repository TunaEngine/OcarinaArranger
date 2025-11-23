"""Conversion helpers for exporting arranged scores."""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import count
from typing import Callable, Dict, List, Protocol, Sequence

from ocarina_tools import (
    collect_used_pitches,
    favor_lower_register,
    filter_parts,
    get_note_events,
    get_time_signature,
    load_score,
    NoteEvent,
    transform_to_ocarina,
)
from ocarina_tools.midi_import.models import MidiImportReport

from .settings import TransformSettings
from .pdf_export.types import PdfExportOptions
from .events import trim_leading_silence

Exporter = Callable[[object, str], None]


class MidiExporter(Protocol):
    def __call__(
        self,
        root: object,
        output_path: str,
        tempo_bpm: int | None = None,
        *,
        use_original_instruments: bool = False,
    ) -> None:
        """Export a MIDI rendition of the arranged score."""


class PdfExporter(Protocol):
    def __call__(
        self,
        root: object,
        output_path: str,
        page_size: str,
        orientation: str,
        columns: int,
        prefer_flats: bool,
        *,
        events: object | None = None,
        pulses_per_quarter: int | None = None,
        beats: int | None = None,
        beat_type: int | None = None,
        include_piano_roll: bool = True,
        include_staff: bool = True,
        include_text: bool = True,
        include_fingerings: bool = True,
    ) -> None:
        """Export a PDF document for the arranged score."""


@dataclass(frozen=True)
class ConversionResult:
    summary: dict
    shifted_notes: int
    used_pitches: List[str]
    output_xml_path: str
    output_mxl_path: str
    output_midi_path: str
    output_pdf_paths: Dict[str, str]
    output_folder: str
    midi_report: MidiImportReport | None = None


def derive_export_folder(output_xml_path: str) -> str:
    """Return a unique folder path for exports derived from ``output_xml_path``."""

    base_dir = os.path.dirname(output_xml_path) or os.getcwd()
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0] or "ocarina-export"
    candidate = os.path.join(base_dir, base_name)
    if not os.path.exists(candidate):
        return candidate
    for index in count(2):
        indexed = os.path.join(base_dir, f"{base_name} ({index})")
        if not os.path.exists(indexed):
            return indexed
    raise RuntimeError("Failed to derive unique export folder")


def convert_score(
    input_path: str,
    output_xml_path: str,
    settings: TransformSettings,
    export_musicxml: Exporter,
    export_mxl: Exporter,
    export_midi: MidiExporter,
    export_pdf: PdfExporter,
    pdf_options: PdfExportOptions,
    *,
    midi_mode: str = "auto",
    arranged_events: Sequence[NoteEvent] | None = None,
    arranged_pulses_per_quarter: int | None = None,
) -> ConversionResult:
    load_result = load_score(input_path, midi_mode=midi_mode)
    tree, root = load_result

    if settings.selected_part_ids:
        filter_parts(root, settings.selected_part_ids)

    summary = transform_to_ocarina(
        tree,
        root,
        prefer_mode=settings.prefer_mode,
        range_min=settings.range_min,
        range_max=settings.range_max,
        prefer_flats=settings.prefer_flats,
        collapse_chords=settings.collapse_chords,
        transpose_offset=settings.transpose_offset,
        selected_part_ids=settings.selected_part_ids,
    )

    shifted = 0
    if settings.favor_lower:
        shifted = favor_lower_register(root, range_min=settings.range_min)

    importer_grace = settings.grace_settings.to_importer()
    pulses_per_quarter = arranged_pulses_per_quarter
    events: Sequence[NoteEvent] | None = arranged_events
    if events is None or pulses_per_quarter is None:
        events_from_score, pulses_from_score = get_note_events(
            root, grace_settings=importer_grace
        )
        if events is None:
            events = events_from_score
        if pulses_per_quarter is None:
            pulses_per_quarter = pulses_from_score

    pulses_per_quarter = pulses_per_quarter or 0
    beats, beat_type = get_time_signature(root)

    trimmed_events = trim_leading_silence(events)

    export_folder = derive_export_folder(output_xml_path)
    os.makedirs(export_folder, exist_ok=True)

    xml_filename = os.path.basename(output_xml_path)
    export_xml_path = os.path.join(export_folder, xml_filename)
    export_musicxml(tree, export_xml_path)

    base_stem, _ = os.path.splitext(xml_filename)
    output_mxl_path = os.path.join(export_folder, f"{base_stem}.mxl")
    export_mxl(tree, output_mxl_path)

    output_midi_path = os.path.join(export_folder, f"{base_stem}.mid")
    export_midi(root, output_midi_path, tempo_bpm=None)

    pdf_paths: Dict[str, str] = {}
    base_path = os.path.join(export_folder, base_stem)
    size = pdf_options.normalized_size()
    orientation = pdf_options.normalized_orientation()
    pdf_path = f"{base_path}-{pdf_options.filename_suffix()}.pdf"
    export_pdf(
        root,
        pdf_path,
        size,
        orientation,
        pdf_options.columns,
        False,
        events=trimmed_events,
        pulses_per_quarter=pulses_per_quarter,
        beats=beats,
        beat_type=beat_type,
        include_piano_roll=pdf_options.include_piano_roll,
        include_staff=pdf_options.include_staff,
        include_text=pdf_options.include_text,
        include_fingerings=pdf_options.include_fingerings,
    )
    pdf_paths[pdf_options.label()] = pdf_path

    used_pitches = []
    try:
        used_pitches = collect_used_pitches(root, flats=settings.prefer_flats)
    except Exception:
        used_pitches = []

    return ConversionResult(
        summary=summary,
        shifted_notes=shifted,
        used_pitches=used_pitches,
        output_xml_path=export_xml_path,
        output_mxl_path=output_mxl_path,
        output_midi_path=output_midi_path,
        output_pdf_paths=pdf_paths,
        output_folder=export_folder,
        midi_report=getattr(load_result, "midi_report", None),
    )
