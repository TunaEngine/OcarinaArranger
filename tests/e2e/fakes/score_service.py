from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Iterable, Optional, Union

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from services.score_service import ScoreService


@dataclass(slots=True)
class PreviewCall:
    path: str
    settings: TransformSettings
    selected_part_ids: tuple[str, ...]


@dataclass(slots=True)
class ConversionCall:
    input_path: str
    output_path: str
    settings: TransformSettings
    pdf_options: PdfExportOptions
    selected_part_ids: tuple[str, ...]


@dataclass(slots=True)
class FakeConversionPlan:
    """Describe how the fake service should build a conversion result."""

    output_folder: Path
    used_pitches: tuple[str, ...] = ("C4", "D4", "E4")
    summary: dict = field(
        default_factory=lambda: {"range_names": {"min": "C4", "max": "E5"}}
    )
    shifted_notes: int = 0

    def build(self, requested_output_path: str, pdf_options: PdfExportOptions) -> ConversionResult:
        folder = self.output_folder
        folder.mkdir(parents=True, exist_ok=True)
        requested_name = Path(requested_output_path).name
        xml_path = folder / requested_name
        stem = Path(requested_name).stem
        mxl_path = folder / f"{stem}.mxl"
        midi_path = folder / f"{stem}.mid"
        pdf_path = folder / f"{stem}-{pdf_options.filename_suffix()}.pdf"
        return ConversionResult(
            summary=self.summary,
            shifted_notes=self.shifted_notes,
            used_pitches=list(self.used_pitches),
            output_xml_path=str(xml_path),
            output_mxl_path=str(mxl_path),
            output_midi_path=str(midi_path),
            output_pdf_paths={pdf_options.label(): str(pdf_path)},
            output_folder=str(folder),
        )


class FakeScoreService:
    """Score service double that records requests and returns canned data."""

    def __init__(
        self,
        *,
        preview_results: Optional[Deque[Union[PreviewData, Exception]]] = None,
        conversion_plan: Optional[FakeConversionPlan] = None,
    ) -> None:
        self.preview_calls: list[PreviewCall] = []
        self.convert_calls: list[ConversionCall] = []
        self._preview_results: Deque[Union[PreviewData, Exception]] = preview_results or deque()
        self._conversion_plan = conversion_plan
        self._conversion_outcomes: Deque[Union[ConversionResult, Exception]] = deque()

    def queue_preview_result(self, result: PreviewData) -> None:
        self._preview_results.append(result)

    def queue_preview_error(self, error: Exception) -> None:
        self._preview_results.append(error)

    def set_conversion_plan(self, plan: FakeConversionPlan) -> None:
        self._conversion_plan = plan

    def queue_conversion_result(self, result: ConversionResult) -> None:
        self._conversion_outcomes.append(result)

    def queue_conversion_error(self, error: Exception) -> None:
        self._conversion_outcomes.append(error)

    def set_preview_outcomes(
        self, outcomes: Iterable[Union[PreviewData, Exception]]
    ) -> None:
        self._preview_results.clear()
        self._preview_results.extend(outcomes)

    def pending_preview_outcomes(self) -> int:
        return len(self._preview_results)

    # --- Hooks wired into ScoreService ---------------------------------
    def _build_preview_data(self, path: str, settings: TransformSettings) -> PreviewData:
        if not self._preview_results:
            raise AssertionError("No queued preview results for FakeScoreService")
        self.preview_calls.append(
            PreviewCall(
                path=path,
                settings=settings,
                selected_part_ids=settings.selected_part_ids,
            )
        )
        outcome = self._preview_results.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _convert_score(
        self,
        path: str,
        output_xml_path: str,
        settings: TransformSettings,
        *,
        export_musicxml,  # noqa: ANN001 - protocol hook
        export_mxl,  # noqa: ANN001 - protocol hook
        export_midi,  # noqa: ANN001 - protocol hook
        export_pdf,  # noqa: ANN001 - protocol hook
        pdf_options: PdfExportOptions,
    ) -> ConversionResult:
        if self._conversion_outcomes:
            outcome = self._conversion_outcomes.popleft()
            if isinstance(outcome, Exception):
                raise outcome
            result = outcome
        else:
            if self._conversion_plan is None:
                raise AssertionError("FakeConversionPlan must be configured before converting")
            result = self._conversion_plan.build(output_xml_path, pdf_options)
        self.convert_calls.append(
            ConversionCall(
                input_path=path,
                output_path=output_xml_path,
                settings=settings,
                pdf_options=pdf_options,
                selected_part_ids=settings.selected_part_ids,
            )
        )
        return result

    def _export_passthrough(self, *args, **kwargs) -> None:  # noqa: D401 - noop exporter
        return None

    def as_service(self) -> ScoreService:
        return ScoreService(
            load_score=lambda path: (object(), object()),
            build_preview_data=self._build_preview_data,
            convert_score=self._convert_score,
            export_musicxml=self._export_passthrough,
            export_mxl=self._export_passthrough,
            export_midi=self._export_passthrough,
            export_pdf=self._export_passthrough,
        )
