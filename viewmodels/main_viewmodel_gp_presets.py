from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from services.project_service_gp import (
    GPSettingsPresetError,
    export_gp_preset,
    import_gp_preset,
)
from shared.result import Result

from viewmodels.arranger_models import ArrangerGPSettings


logger = logging.getLogger(__name__)


class GPSettingsPresetMixin:
    """Helpers for exporting and importing GP arranger presets."""

    def export_gp_settings(
        self, settings: ArrangerGPSettings | None = None
    ) -> Optional[Result[str, str]]:
        current = settings
        if current is None:
            with self._state_lock:
                current = self.state.arranger_gp_settings
            if current is None:
                current = ArrangerGPSettings()
        normalized = current.normalized()
        suggested = "gp-settings.gp.json"
        destination = self._dialogs.ask_save_gp_preset_path(suggested)
        if not destination:
            logger.info("GP preset export cancelled")
            return None
        try:
            saved_path = export_gp_preset(normalized, Path(destination))
        except Exception as exc:  # pragma: no cover - filesystem dependent
            self.state.status_message = "Failed to export GP preset."
            logger.exception("GP preset export failed", extra={"destination": destination})
            return Result.err(str(exc))
        self.state.status_message = "GP preset exported."
        logger.info("GP preset exported", extra={"destination": str(saved_path)})
        return Result.ok(str(saved_path))

    def import_gp_settings(self) -> Optional[Result[ArrangerGPSettings, str]]:
        source = self._dialogs.ask_open_gp_preset_path()
        if not source:
            logger.info("GP preset import cancelled")
            return None
        with self._state_lock:
            defaults = self.state.arranger_gp_settings or ArrangerGPSettings()
        try:
            imported = import_gp_preset(Path(source), defaults)
        except GPSettingsPresetError as exc:
            self.state.status_message = "Failed to import GP preset."
            logger.warning(
                "GP preset import failed", extra={"source": source, "reason": str(exc)}
            )
            return Result.err(str(exc))
        except Exception as exc:  # pragma: no cover - filesystem dependent
            self.state.status_message = "Failed to import GP preset."
            logger.exception("GP preset import failed", extra={"source": source})
            return Result.err(str(exc))
        self.update_settings(arranger_gp_settings=imported)
        self.state.status_message = "GP preset imported."
        logger.info("GP preset imported", extra={"source": source})
        return Result.ok(imported)


__all__ = ["GPSettingsPresetMixin"]
