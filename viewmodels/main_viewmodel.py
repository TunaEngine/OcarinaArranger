"""View-model for the main window orchestrating score actions."""

from __future__ import annotations

import logging
from dataclasses import replace
import os
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions
from adapters.file_dialog import FileDialogAdapter
from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
    ProjectService,
    ProjectSnapshot,
    PreviewPlaybackSnapshot,
)
from services.score_service import ScoreService
from shared.melody_part import select_melody_candidate
from shared.result import Result

from domain.arrangement.api import ArrangementStrategyResult

from services.arranger_preview import (
    ArrangerComputation,
    compute_arranger_preview as _compute_arranger_preview,
)
from viewmodels.arranger_models import (
    ArrangerBudgetSettings,
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerGPSettings,
    ArrangerInstrumentSummary,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)
from .main_viewmodel_state import (
    ARRANGER_STRATEGIES,
    ARRANGER_STRATEGY_CURRENT,
    ARRANGER_STRATEGY_STARRED_BEST,
    DEFAULT_ARRANGER_STRATEGY,
    MainViewModelState,
)
from .main_viewmodel_arranger_helpers import (
    apply_arranger_results_from_preview,
    preview_with_arranger_events,
)
from .main_viewmodel_arranger_settings import (
    normalize_arranger_budgets,
    normalize_arranger_gp_settings,
)
from .main_viewmodel_part_selection import (
    normalize_available_parts,
    normalize_selected_part_ids,
)


logger = logging.getLogger(__name__)


_UNSET = object()


class MainViewModel:
    """Expose UI-ready state and commands for the main window."""

    def __init__(
        self,
        dialogs: FileDialogAdapter,
        score_service: ScoreService,
        project_service: ProjectService | None = None,
    ) -> None:
        self._dialogs = dialogs
        self._score_service = score_service
        self._project_service = project_service or ProjectService()
        self.state = MainViewModelState()
        self._last_conversion: ConversionResult | None = None
        self._last_pdf_options: PdfExportOptions | None = None
        self._pitch_entries: list[str] = []
        logger.info("MainViewModel initialised")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def update_settings(
        self,
        *,
        input_path: Optional[str] = None,
        prefer_mode: Optional[str] = None,
        prefer_flats: Optional[bool] = None,
        collapse_chords: Optional[bool] = None,
        favor_lower: Optional[bool] = None,
        range_min: Optional[str] = None,
        range_max: Optional[str] = None,
        transpose_offset: Optional[int] = None,
        instrument_id: Optional[str] = None,
        available_parts: Optional[Iterable[MusicXmlPartInfo | Mapping[str, Any]]] = None,
        selected_part_ids: Optional[tuple[str, ...] | list[str]] = None,
        arranger_mode: Optional[str] = None,
        arranger_strategy: Optional[str] = None,
        starred_instrument_ids: Optional[tuple[str, ...] | list[str]] = None,
        arranger_dp_slack_enabled: Optional[bool] = None,
        arranger_budgets: Optional[
            ArrangerBudgetSettings | dict[str, int] | tuple[int, int, int, int]
        ] = None,
        arranger_gp_settings: Optional[
            ArrangerGPSettings
            | dict[str, object]
            | tuple[int, int, object]
        ] = None,
    ) -> None:
        if input_path is not None:
            normalized_path = input_path
            if normalized_path != self.state.input_path:
                self.state.preview_settings = {}
                self.state.available_parts = ()
                self.state.selected_part_ids = ()
                self.state.arranger_strategy_summary = ()
                self.state.arranger_result_summary = None
                self.state.arranger_explanations = ()
                self.state.arranger_telemetry = ()
                self.state.pitch_list = []
                self._pitch_entries = []
            self.state.input_path = normalized_path
        if prefer_mode is not None:
            self.state.prefer_mode = prefer_mode
        if prefer_flats is not None:
            self.state.prefer_flats = prefer_flats
        if collapse_chords is not None:
            self.state.collapse_chords = collapse_chords
        if favor_lower is not None:
            self.state.favor_lower = favor_lower
        if range_min is not None:
            self.state.range_min = range_min
        if range_max is not None:
            self.state.range_max = range_max
        if transpose_offset is not None:
            self.state.transpose_offset = transpose_offset
        if instrument_id is not None:
            self.state.instrument_id = instrument_id
        if available_parts is not None:
            normalized_parts = normalize_available_parts(available_parts)
            self.state.available_parts = normalized_parts
            if self.state.selected_part_ids:
                filtered = normalize_selected_part_ids(
                    self.state.selected_part_ids,
                    (part.part_id for part in normalized_parts),
                )
                if filtered != self.state.selected_part_ids:
                    self.state.selected_part_ids = filtered
        if selected_part_ids is not None:
            allowed_part_ids = (
                (part.part_id for part in self.state.available_parts)
                if self.state.available_parts
                else None
            )
            self.state.selected_part_ids = normalize_selected_part_ids(
                selected_part_ids,
                allowed_part_ids,
            )
        if arranger_mode is not None:
            self.state.arranger_mode = arranger_mode
        if arranger_strategy is not None:
            normalized_strategy = (
                arranger_strategy if arranger_strategy in ARRANGER_STRATEGIES else DEFAULT_ARRANGER_STRATEGY
            )
            self.state.arranger_strategy = normalized_strategy
        if starred_instrument_ids is not None:
            ordered: list[str] = []
            seen = set()
            for identifier in starred_instrument_ids:
                if not isinstance(identifier, str):
                    continue
                if identifier in seen:
                    continue
                seen.add(identifier)
                ordered.append(identifier)
            self.state.starred_instrument_ids = tuple(ordered)
        if arranger_dp_slack_enabled is not None:
            self.state.arranger_dp_slack_enabled = bool(arranger_dp_slack_enabled)
        if arranger_budgets is not None:
            self.state.arranger_budgets = normalize_arranger_budgets(arranger_budgets)
        if arranger_gp_settings is not None:
            self.state.arranger_gp_settings = normalize_arranger_gp_settings(
                arranger_gp_settings,
                self.state.arranger_gp_settings,
            )

    def update_arranger_summary(
        self,
        *,
        summaries: Optional[list[ArrangerInstrumentSummary] | tuple[ArrangerInstrumentSummary, ...]] = None,
        strategy: Optional[str] = None,
    ) -> None:
        """Refresh arranger v2 summary data exposed to the UI."""

        if strategy is not None and strategy in ARRANGER_STRATEGIES:
            self.state.arranger_strategy = strategy
        if summaries is not None:
            self.state.arranger_strategy_summary = tuple(summaries)

    def update_arranger_results(
        self,
        *,
        summary: ArrangerResultSummary | None | object = _UNSET,
        explanations: Optional[Iterable[ArrangerExplanationRow]] = None,
        telemetry: Optional[Iterable[ArrangerTelemetryHint]] = None,
    ) -> None:
        """Refresh arranger v2 outcome details used by the results panel."""

        if summary is not _UNSET:
            self.state.arranger_result_summary = summary  # type: ignore[assignment]
        if explanations is not None:
            self.state.arranger_explanations = tuple(explanations)
        if telemetry is not None:
            self.state.arranger_telemetry = tuple(telemetry)

    def reset_arranger_budgets(self) -> None:
        """Restore arranger salvage budgets to default values."""

        self.state.arranger_budgets = ArrangerBudgetSettings()

    def settings(self) -> TransformSettings:
        return TransformSettings(
            prefer_mode=self.state.prefer_mode,
            range_min=self.state.range_min,
            range_max=self.state.range_max,
            prefer_flats=self.state.prefer_flats,
            collapse_chords=self.state.collapse_chords,
            favor_lower=self.state.favor_lower,
            transpose_offset=self.state.transpose_offset,
            instrument_id=self.state.instrument_id,
            selected_part_ids=self.state.selected_part_ids,
        )

    # ------------------------------------------------------------------
    # Commands used by the UI
    # ------------------------------------------------------------------
    def load_part_metadata(self) -> tuple[MusicXmlPartInfo, ...]:
        path = self.state.input_path.strip()
        if not path:
            logger.debug("Skipping part metadata load: no input path set")
            self.update_settings(available_parts=())
            return ()
        parts: tuple[MusicXmlPartInfo, ...] = ()
        try:
            loaded = self._score_service.load_part_metadata(path)
        except Exception:
            logger.exception("Failed to load part metadata", extra={"path": path})
        else:
            parts = tuple(loaded)
        self.update_settings(available_parts=parts)
        if self.state.available_parts and not self.state.selected_part_ids:
            melody_part_id = select_melody_candidate(self.state.available_parts)
            default_id = melody_part_id or self.state.available_parts[0].part_id
            self.update_settings(selected_part_ids=(default_id,))
        return self.state.available_parts

    def apply_part_selection(self, part_ids: Sequence[str]) -> tuple[str, ...]:
        allowed = (part.part_id for part in self.state.available_parts)
        normalized = normalize_selected_part_ids(part_ids, allowed)
        self.update_settings(selected_part_ids=normalized)
        return self.state.selected_part_ids

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> tuple[str, ...] | None:
        chooser = getattr(self._dialogs, "ask_select_parts", None)
        if chooser is None:
            logger.debug("No part selection dialog available; using defaults")
            return tuple(preselected)
        try:
            result = chooser(parts, preselected)
        except Exception:
            logger.exception("Part selection dialog failed", extra={"path": self.state.input_path})
            return tuple(preselected)
        if result is None:
            return None
        return tuple(result)

    def browse_for_input(self) -> bool:
        logger.info("Prompting for input file")
        previous_path = self.state.input_path
        path = self._dialogs.ask_open_path()
        if not path:
            logger.info("Input file selection cancelled")
            return False
        if previous_path and path == previous_path:
            logger.info("Input file unchanged; skipping preview reload")
            return False
        self.update_settings(input_path=path)
        self.state.pitch_list = []
        self._pitch_entries = []
        logger.info("Input file selected", extra={"path": path})
        self.state.status_message = "Ready."
        return True

    def render_previews(self) -> Result[PreviewData, str]:
        require_result = self._require_existing_input("Choose a file first.")
        if require_result.is_err():
            logger.warning(
                "Preview render blocked: input required",
                extra={"detail": require_result.error},
            )
            return Result.err(require_result.error)
        path = require_result.unwrap()
        logger.info("Building preview data", extra={"path": path})
        try:
            preview = self._score_service.build_preview(path, self.settings())
        except Exception as exc:
            self.state.status_message = "Preview failed."
            logger.exception("Failed to build preview", extra={"path": path})
            return Result.err(str(exc))
        self.state.status_message = "Preview rendered."
        computation: ArrangerComputation | None = None
        try:
            computation = apply_arranger_results_from_preview(self, preview)
        except Exception:
            logger.exception("Failed to apply arranger results from preview")
            self.update_arranger_summary(summaries=(), strategy=self.state.arranger_strategy)
            self.update_arranger_results(summary=None, explanations=(), telemetry=())
        updated_preview = preview_with_arranger_events(preview, computation)
        logger.info("Preview build completed", extra={"path": path})
        return Result.ok(updated_preview)

    def convert(
        self, pdf_options: Optional[PdfExportOptions] = None
    ) -> Optional[Result[ConversionResult, str]]:
        require_result = self._require_existing_input(
            "Please choose a valid input file (.musicxml/.xml, .mxl, or .mid)."
        )
        if require_result.is_err():
            logger.warning(
                "Conversion blocked: input required",
                extra={"detail": require_result.error},
            )
            return Result.err(require_result.error)
        path = require_result.unwrap()
        base = os.path.splitext(os.path.basename(path))[0] + "-ocarina-C"
        logger.info("Prompting for conversion destination", extra={"path": path})
        save_path = self._dialogs.ask_save_path(f"{base}.musicxml")
        if not save_path:
            logger.info("Conversion cancelled while choosing destination", extra={"path": path})
            return None
        options = pdf_options or PdfExportOptions.with_defaults()
        try:
            result = self._score_service.convert(path, save_path, self.settings(), options)
        except Exception as exc:
            self.state.status_message = "Conversion failed."
            logger.exception("Conversion failed", extra={"input_path": path, "output_path": save_path})
            return Result.err(str(exc))
        self.state.pitch_list = list(result.used_pitches)
        self._pitch_entries = list(result.used_pitches)
        self._last_conversion = result
        self._last_pdf_options = options
        self.state.status_message = "Converted OK."
        logger.info(
            "Conversion succeeded",
            extra={"input_path": path, "output_xml": str(result.output_xml_path)},
        )
        return Result.ok(result)

    def save_project(self) -> Optional[Result[str, str]]:
        require_result = self._require_existing_input("Choose a valid input file before saving a project.")
        if require_result.is_err():
            return Result.err(require_result.error)
        input_path = require_result.unwrap()
        base = os.path.splitext(os.path.basename(input_path))[0] or "ocarina-project"
        destination = self._dialogs.ask_save_project_path(f"{base}.ocarina")
        if not destination:
            logger.info("Project save cancelled", extra={"input_path": input_path})
            return None
        return self.save_project_to(destination)

    def save_project_to(self, destination: str | Path) -> Result[str, str]:
        snapshot = ProjectSnapshot(
            input_path=Path(self.state.input_path),
            settings=self.settings(),
            pdf_options=self._last_pdf_options,
            pitch_list=list(self.state.pitch_list),
            pitch_entries=self.pitch_entries(),
            status_message=self.state.status_message,
            conversion=self._last_conversion,
            preview_settings=self.preview_settings(),
        )
        try:
            saved = self._project_service.save(snapshot, Path(destination))
        except ProjectPersistenceError as exc:
            self.state.status_message = "Project save failed."
            logger.exception("Project save failed", extra={"destination": str(destination)})
            return Result.err(str(exc))
        self.state.status_message = "Project saved."
        logger.info("Project saved", extra={"destination": str(saved)})
        return Result.ok(str(saved))

    def open_project(self, extract_dir: Path | None = None) -> Optional[Result[LoadedProject, str]]:
        path = self._dialogs.ask_open_project_path()
        if not path:
            logger.info("Project load cancelled")
            return None
        return self.load_project_from(path, extract_dir)

    def load_project_from(
        self, project_path: str | Path, extract_dir: Path | None = None
    ) -> Result[LoadedProject, str]:
        try:
            loaded = self._project_service.load(Path(project_path), extract_dir)
        except ProjectPersistenceError as exc:
            self.state.status_message = "Project load failed."
            logger.exception("Project load failed", extra={"path": str(project_path)})
            return Result.err(str(exc))
        self._apply_loaded_project(loaded)
        logger.info("Project loaded", extra={"path": str(project_path)})
        return Result.ok(loaded)

    def pitch_entries(self) -> list[str]:
        if self._pitch_entries:
            return list(self._pitch_entries)
        if self.state.pitch_list:
            return list(self.state.pitch_list)
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_existing_input(self, message: str) -> Result[str, str]:
        path = self.state.input_path.strip()
        if not path or not os.path.exists(path):
            logger.warning("Required input missing", extra={"path": path, "detail": message})
            return Result.err(message)
        return Result.ok(path)

    def _apply_loaded_project(self, loaded: LoadedProject) -> None:
        settings = loaded.settings
        self.update_settings(
            input_path=str(loaded.input_path),
            prefer_mode=settings.prefer_mode,
            prefer_flats=settings.prefer_flats,
            collapse_chords=settings.collapse_chords,
            favor_lower=settings.favor_lower,
            range_min=settings.range_min,
            range_max=settings.range_max,
            transpose_offset=settings.transpose_offset,
            instrument_id=settings.instrument_id,
            selected_part_ids=settings.selected_part_ids,
        )
        self.state.pitch_list = list(loaded.pitch_list)
        self._pitch_entries = list(loaded.pitch_entries)
        self._last_pdf_options = loaded.pdf_options
        self._last_conversion = loaded.conversion
        if loaded.conversion is not None:
            self.state.pitch_list = list(loaded.conversion.used_pitches)
        self.state.status_message = loaded.status_message or "Project loaded."
        self.state.preview_settings = dict(loaded.preview_settings)

    def update_preview_settings(
        self, preview_settings: dict[str, PreviewPlaybackSnapshot]
    ) -> None:
        self.state.preview_settings = dict(preview_settings)

    def preview_settings(self) -> dict[str, PreviewPlaybackSnapshot]:
        return dict(self.state.preview_settings)

    # ------------------------------------------------------------------
    # Arranger helpers
    # ------------------------------------------------------------------
__all__ = [
    "MainViewModel",
    "MainViewModelState",
    "compute_arranger_preview",
]

# Backwards compatibility for legacy tests expecting module-level access.
compute_arranger_preview = _compute_arranger_preview
