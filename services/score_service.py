"""Application services orchestrating score loading, previewing, and conversion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ocarina_gui.conversion import ConversionResult, MidiExporter, PdfExporter
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_tools.parts import MusicXmlPartInfo, list_parts
from ocarina_tools.midi_import.models import MidiImportReport
from ocarina_tools.io import ScoreLoadResult


LoadScoreFn = Callable[..., ScoreLoadResult]
BuildPreviewFn = Callable[..., PreviewData]
ConvertScoreFn = Callable[..., ConversionResult]
ExportFn = Callable[[object, str], None]
ExportPdfFn = PdfExporter
ExportMidiFn = MidiExporter


@dataclass(slots=True)
class ScoreService:
    """High-level operations for manipulating scores."""

    load_score: LoadScoreFn
    build_preview_data: BuildPreviewFn
    convert_score: ConvertScoreFn
    export_musicxml: ExportFn
    export_mxl: ExportFn
    export_midi: ExportMidiFn
    export_pdf: ExportPdfFn
    last_midi_report: MidiImportReport | None = None

    def build_preview(
        self, path: str, settings: TransformSettings, *, midi_mode: str = "auto"
    ) -> PreviewData:
        try:
            preview = self.build_preview_data(path, settings, midi_mode=midi_mode)
        except Exception:
            self.last_midi_report = None
            raise
        self.last_midi_report = getattr(preview, "midi_report", None)
        return preview

    def load_part_metadata(
        self, path: str, *, midi_mode: str = "auto"
    ) -> tuple[MusicXmlPartInfo, ...]:
        try:
            result = self.load_score(path, midi_mode=midi_mode)
        except Exception:
            self.last_midi_report = None
            return ()
        self.last_midi_report = getattr(result, "midi_report", None)
        root = result.root
        try:
            return tuple(list_parts(root))
        except Exception:
            return ()

    def convert(
        self,
        path: str,
        output_xml_path: str,
        settings: TransformSettings,
        pdf_options: PdfExportOptions,
        *,
        midi_mode: str = "auto",
    ) -> ConversionResult:
        result = self.convert_score(
            path,
            output_xml_path,
            settings,
            export_musicxml=self.export_musicxml,
            export_mxl=self.export_mxl,
            export_midi=self.export_midi,
            export_pdf=self.export_pdf,
            pdf_options=pdf_options,
            midi_mode=midi_mode,
        )
        self.last_midi_report = getattr(result, "midi_report", None)
        return result


__all__ = ["ScoreService"]
