"""Application services orchestrating score loading, previewing, and conversion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ocarina_gui.conversion import ConversionResult, MidiExporter, PdfExporter
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions


LoadScoreFn = Callable[[str], tuple[object, object]]
BuildPreviewFn = Callable[[str, TransformSettings], PreviewData]
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

    def build_preview(self, path: str, settings: TransformSettings) -> PreviewData:
        return self.build_preview_data(path, settings)

    def convert(
        self,
        path: str,
        output_xml_path: str,
        settings: TransformSettings,
        pdf_options: PdfExportOptions,
    ) -> ConversionResult:
        return self.convert_score(
            path,
            output_xml_path,
            settings,
            export_musicxml=self.export_musicxml,
            export_mxl=self.export_mxl,
            export_midi=self.export_midi,
            export_pdf=self.export_pdf,
            pdf_options=pdf_options,
        )


__all__ = ["ScoreService"]
