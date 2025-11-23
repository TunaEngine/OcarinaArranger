"""View-model for the main window orchestrating score actions."""

from __future__ import annotations

import logging
import os
from threading import RLock
from collections.abc import Callable
from typing import Optional

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_gui.pdf_export.types import PdfExportOptions
from adapters.file_dialog import FileDialogAdapter
from services.project_service import (
    ProjectService,
    PreviewPlaybackSnapshot,
)
from services.score_service import ScoreService
from shared.result import Result

from domain.arrangement.api import ArrangementStrategyResult

from services.arranger_preview import (
    ArrangerComputation,
    compute_arranger_preview as _compute_arranger_preview,
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
from .main_viewmodel_settings_mixin import MainViewModelSettingsMixin
from .main_viewmodel_arranger_state import MainViewModelArrangerStateMixin
from .main_viewmodel_gp_presets import GPSettingsPresetMixin
from .main_viewmodel_project import MainViewModelProjectMixin
from .main_viewmodel_preview_state import (
    PreviewStateSnapshot,
    capture_preview_state,
    restore_preview_state,
)

logger = logging.getLogger(__name__)

class MainViewModel(
    MainViewModelSettingsMixin,
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
        self._last_preview: PreviewData | None = None
        self._pitch_entries: list[str] = []
        self._pending_input_confirmation = False
        self._last_successful_input_snapshot: PreviewStateSnapshot | None = None
        self._state_lock = RLock()
        logger.info("MainViewModel initialised")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
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
            self._last_preview = updated_preview
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
        arranged_events = None
        arranged_ppq = None
        with self._state_lock:
            if self._last_preview is not None:
                arranged_events = tuple(self._last_preview.arranged_events)
                arranged_ppq = self._last_preview.pulses_per_quarter
        try:
            result = self._score_service.convert(
                path,
                save_path,
                self.settings(),
                options,
                midi_mode=midi_mode,
                arranged_events=arranged_events,
                arranged_pulses_per_quarter=arranged_ppq,
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
    "ARRANGER_STRATEGIES",
    "ARRANGER_STRATEGY_CURRENT",
    "ARRANGER_STRATEGY_STARRED_BEST",
    "DEFAULT_ARRANGER_STRATEGY",
    "compute_arranger_preview",
]

# Backwards compatibility for legacy tests expecting module-level access.
compute_arranger_preview = _compute_arranger_preview
