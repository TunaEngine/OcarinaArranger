"""View-model for the main window orchestrating score actions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from ocarina_gui.pdf_export.types import PdfExportOptions

from adapters.file_dialog import FileDialogAdapter
from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
    ProjectService,
    ProjectSnapshot,
    PreviewPlaybackSnapshot,
)
from services.score_service import ScoreService
from shared.result import Result


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MainViewModelState:
    input_path: str = ""
    prefer_mode: str = "auto"
    prefer_flats: bool = True
    collapse_chords: bool = True
    favor_lower: bool = False
    range_min: str = DEFAULT_MIN
    range_max: str = DEFAULT_MAX
    status_message: str = "Ready."
    pitch_list: list[str] = field(default_factory=list)
    transpose_offset: int = 0
    instrument_id: str = ""
    preview_settings: dict[str, PreviewPlaybackSnapshot] = field(default_factory=dict)


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
    ) -> None:
        if input_path is not None:
            normalized_path = input_path
            if normalized_path != self.state.input_path:
                self.state.preview_settings = {}
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
        )

    # ------------------------------------------------------------------
    # Commands used by the UI
    # ------------------------------------------------------------------
    def browse_for_input(self) -> None:
        logger.info("Prompting for input file")
        path = self._dialogs.ask_open_path()
        if not path:
            logger.info("Input file selection cancelled")
            return
        self.update_settings(input_path=path)
        self.state.pitch_list = []
        self._pitch_entries = []
        logger.info("Input file selected", extra={"path": path})
        self.state.status_message = "Ready."

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
        logger.info("Preview build completed", extra={"path": path})
        return Result.ok(preview)

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


__all__ = [
    "MainViewModel",
    "MainViewModelState",
]
