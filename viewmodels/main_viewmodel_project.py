from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
)
from shared.result import Result

from .main_viewmodel_persistence import build_project_snapshot, apply_loaded_project

if TYPE_CHECKING:
    from services.project_service import ProjectService

    from .main_viewmodel import MainViewModel


class MainViewModelProjectMixin:
    """Mix in project persistence commands for the main view-model."""

    _project_service: "ProjectService"

    def save_project(self: "MainViewModel") -> Optional[Result[str, str]]:
        require_result = self._require_existing_input(
            "Choose a valid input file before saving a project."
        )
        if require_result.is_err():
            return Result.err(require_result.error)
        input_path = require_result.unwrap()
        base = Path(input_path).stem or "ocarina-project"
        destination = self._dialogs.ask_save_project_path(f"{base}.ocarina")
        if not destination:
            logger.info("Project save cancelled", extra={"input_path": input_path})
            return None
        return self.save_project_to(destination)

    def save_project_to(
        self: "MainViewModel", destination: str | Path
    ) -> Result[str, str]:
        snapshot = build_project_snapshot(self)
        try:
            saved = self._project_service.save(snapshot, Path(destination))
        except ProjectPersistenceError as exc:
            self.state.status_message = "Project save failed."
            logger.exception(
                "Project save failed", extra={"destination": str(destination)}
            )
            return Result.err(str(exc))
        with self._state_lock:
            self.state.status_message = "Project saved."
            self.state.project_path = str(saved)
        logger.info("Project saved", extra={"destination": str(saved)})
        return Result.ok(str(saved))

    def open_project(
        self: "MainViewModel", extract_dir: Path | None = None
    ) -> Optional[Result[LoadedProject, str]]:
        path = self._dialogs.ask_open_project_path()
        if not path:
            logger.info("Project load cancelled")
            return None
        return self.load_project_from(path, extract_dir)

    def load_project_from(
        self: "MainViewModel", project_path: str | Path, extract_dir: Path | None = None
    ) -> Result[LoadedProject, str]:
        try:
            loaded = self._project_service.load(Path(project_path), extract_dir)
        except ProjectPersistenceError as exc:
            self.state.status_message = "Project load failed."
            logger.exception(
                "Project load failed", extra={"path": str(project_path)}
            )
            return Result.err(str(exc))
        self._apply_loaded_project(loaded)
        logger.info("Project loaded", extra={"path": str(project_path)})
        return Result.ok(loaded)

    def _apply_loaded_project(
        self: "MainViewModel", loaded: LoadedProject
    ) -> None:
        apply_loaded_project(self, loaded)


__all__ = ["MainViewModelProjectMixin"]
logger = logging.getLogger(__name__)
