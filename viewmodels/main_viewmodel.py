"""View-model for the main window orchestrating score actions."""

from __future__ import annotations

import logging
import os
from threading import RLock
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Optional

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions
from adapters.file_dialog import FileDialogAdapter
from ocarina_tools.parts import MusicXmlPartInfo
from ocarina_tools.midi_import.models import MidiImportReport
from services.project_service import (
    ProjectService,
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
    ArrangerGPSettings,
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
from .main_viewmodel_arranger_state import MainViewModelArrangerStateMixin
from .main_viewmodel_arranger_settings import (
    normalize_arranger_budgets,
    normalize_arranger_gp_settings,
    normalize_grace_settings,
)
from .main_viewmodel_part_selection import (
    normalize_available_parts,
    normalize_selected_part_ids,
)
from .main_viewmodel_gp_presets import GPSettingsPresetMixin
from .main_viewmodel_project import MainViewModelProjectMixin
from .main_viewmodel_preview_state import (
    PreviewStateSnapshot,
    capture_preview_state,
    restore_preview_state,
)

logger = logging.getLogger(__name__)

class MainViewModel(
    GPSettingsPresetMixin,
    MainViewModelArrangerStateMixin,
    MainViewModelProjectMixin,
):
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
        self._pending_input_confirmation = False
        self._last_successful_input_snapshot: PreviewStateSnapshot | None = None
        self._state_lock = RLock()
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
        grace_settings: Optional[GraceTransformSettings | Mapping[str, Any]] = None,
        lenient_midi_import: Optional[bool] = None,
    ) -> None:
        with self._state_lock:
            if input_path is not None:
                normalized_path = input_path
                if normalized_path != self.state.input_path:
                    if (
                        self._last_successful_input_snapshot is not None
                        and self._last_successful_input_snapshot.input_path
                        == self.state.input_path
                    ):
                        self._last_successful_input_snapshot = capture_preview_state(
                            self.state, self._pitch_entries
                        )
                    self.state.preview_settings = {}
                    self.state.available_parts = ()
                    self.state.selected_part_ids = ()
                    self.state.arranger_strategy_summary = ()
                    self.state.arranger_result_summary = None
                    self.state.arranger_explanations = ()
                    self.state.arranger_telemetry = ()
                    self.state.pitch_list = []
                    self._pitch_entries = []
                    self._pending_input_confirmation = bool(normalized_path)
                    self.state.midi_import_report = None
                    self.state.midi_import_error = None
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
            if grace_settings is not None:
                base_grace = getattr(self.state, "grace_settings", None)
                self.state.grace_settings = normalize_grace_settings(
                    grace_settings,
                    base_grace,
                )
            if lenient_midi_import is not None:
                self.state.lenient_midi_import = bool(lenient_midi_import)

    def settings(self) -> TransformSettings:
        with self._state_lock:
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
                grace_settings=self.state.grace_settings,
                lenient_midi_import=self.state.lenient_midi_import,
            )

    def _midi_import_mode(self) -> str:
        with self._state_lock:
            enabled = bool(getattr(self.state, "lenient_midi_import", True))
        return "auto" if enabled else "strict"

    def update_midi_import_report(self, report: MidiImportReport | None) -> None:
        with self._state_lock:
            self.state.midi_import_report = report

    def update_midi_import_error(self, message: str | None) -> None:
        with self._state_lock:
            self.state.midi_import_error = message

    # ------------------------------------------------------------------
    # Commands used by the UI
    # ------------------------------------------------------------------
    def load_part_metadata(self) -> tuple[MusicXmlPartInfo, ...]:
        with self._state_lock:
            path = self.state.input_path.strip()
        if not path:
            logger.debug("Skipping part metadata load: no input path set")
            self.update_settings(available_parts=())
            self.update_midi_import_report(None)
            return ()
        parts: tuple[MusicXmlPartInfo, ...] = ()
        midi_mode = self._midi_import_mode()
        try:
            loaded = self._score_service.load_part_metadata(path, midi_mode=midi_mode)
        except Exception as exc:
            logger.exception("Failed to load part metadata", extra={"path": path})
            self.update_midi_import_report(getattr(self._score_service, "last_midi_report", None))
            self.update_midi_import_error(str(exc) or exc.__class__.__name__)
        else:
            parts = tuple(loaded)
            self.update_midi_import_report(getattr(self._score_service, "last_midi_report", None))
            self.update_midi_import_error(None)
        self.update_settings(available_parts=parts)
        with self._state_lock:
            if self.state.available_parts and not self.state.selected_part_ids:
                melody_part_id = select_melody_candidate(self.state.available_parts)
                default_id = melody_part_id or self.state.available_parts[0].part_id
                self.update_settings(selected_part_ids=(default_id,))
            return self.state.available_parts

    def apply_part_selection(self, part_ids: Sequence[str]) -> tuple[str, ...]:
        with self._state_lock:
            allowed = (part.part_id for part in self.state.available_parts)
        normalized = normalize_selected_part_ids(part_ids, allowed)
        self.update_settings(selected_part_ids=normalized)
        confirmed_selection = bool(normalized) or bool(part_ids)
        with self._state_lock:
            if (
                confirmed_selection
                and self.state.midi_import_error is None
            ):
                self._pending_input_confirmation = False
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
        with self._state_lock:
            previous_path = self.state.input_path
            awaiting_confirmation = self._pending_input_confirmation
        path = self._dialogs.ask_open_path()
        if not path:
            logger.info("Input file selection cancelled")
            return False
        if (
            previous_path
            and path == previous_path
            and not awaiting_confirmation
        ):
            logger.info(
                "Input file unchanged and selection confirmed; skipping preview reload"
            )
            return False
        self.update_settings(input_path=path)
        with self._state_lock:
            self.state.project_path = ""
            self.state.pitch_list = []
            self._pitch_entries = []
            self.state.status_message = "Ready."
        logger.info("Input file selected", extra={"path": path})
        return True

    def render_previews(
        self,
        progress_callback: Callable[[float, str | None], None] | None = None,
    ) -> Result[PreviewData, str]:
        with self._state_lock:
            require_result = self._require_existing_input("Choose a file first.")
            if require_result.is_err():
                logger.warning(
                    "Preview render blocked: input required",
                    extra={"detail": require_result.error},
                )
                return Result.err(require_result.error)
            path = require_result.unwrap()
            settings_snapshot = self.settings()
        logger.info("Building preview data", extra={"path": path})
        midi_mode = self._midi_import_mode()
        try:
            preview = self._score_service.build_preview(
                path,
                settings_snapshot,
                midi_mode=midi_mode,
            )
            self.update_midi_import_report(getattr(self._score_service, "last_midi_report", None))
            self.update_midi_import_error(None)
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            with self._state_lock:
                self.state.status_message = f"Preview failed: {error_message}"
                self._restore_last_successful_preview_locked()
                self._pending_input_confirmation = bool(self.state.input_path)
            self.update_midi_import_report(None)
            self.update_midi_import_error(error_message)
            logger.exception("Failed to build preview", extra={"path": path})
            return Result.err(error_message)
        with self._state_lock:
            self.state.status_message = "Preview rendered."
        computation: ArrangerComputation | None = None
        try:
            computation = apply_arranger_results_from_preview(
                self,
                preview,
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("Failed to apply arranger results from preview")
            self.update_arranger_summary(summaries=(), strategy=self.state.arranger_strategy)
            self.update_arranger_results(summary=None, explanations=(), telemetry=())
        updated_preview = preview_with_arranger_events(preview, computation)
        with self._state_lock:
            self.state.status_message = "Preview rendered."
            self._pending_input_confirmation = False
            self._last_successful_input_snapshot = capture_preview_state(
                self.state, self._pitch_entries
            )
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
        midi_mode = self._midi_import_mode()
        try:
            result = self._score_service.convert(
                path,
                save_path,
                self.settings(),
                options,
                midi_mode=midi_mode,
            )
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            with self._state_lock:
                self.state.status_message = "Conversion failed."
            self.update_midi_import_error(error_message)
            logger.exception(
                "Conversion failed",
                extra={"input_path": path, "output_path": save_path},
            )
            return Result.err(error_message)
        self.update_midi_import_report(getattr(result, "midi_report", None))
        self.update_midi_import_error(None)
        self.state.pitch_list = list(result.used_pitches)
        self._pitch_entries = list(result.used_pitches)
        self._last_conversion = result
        self._last_pdf_options = options
        with self._state_lock:
            self.state.status_message = "Converted OK."
        logger.info(
            "Conversion succeeded",
            extra={"input_path": path, "output_xml": str(result.output_xml_path)},
        )
        return Result.ok(result)

    def pitch_entries(self) -> list[str]:
        with self._state_lock:
            if self._pitch_entries:
                return list(self._pitch_entries)
            if self.state.pitch_list:
                return list(self.state.pitch_list)
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_existing_input(self, message: str) -> Result[str, str]:
        with self._state_lock:
            path = self.state.input_path.strip()
        if not path or not os.path.exists(path):
            logger.warning("Required input missing", extra={"path": path, "detail": message})
            return Result.err(message)
        return Result.ok(path)

    def update_preview_settings(
        self, preview_settings: dict[str, PreviewPlaybackSnapshot]
    ) -> None:
        self.state.preview_settings = dict(preview_settings)

    def preview_settings(self) -> dict[str, PreviewPlaybackSnapshot]:
        return dict(self.state.preview_settings)

    def _restore_last_successful_preview_locked(self) -> None:
        snapshot = self._last_successful_input_snapshot
        if snapshot is None:
            return
        self._pitch_entries = restore_preview_state(self.state, snapshot)
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
