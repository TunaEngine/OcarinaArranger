"""Seed preview data for deterministic Linux screenshots."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ocarina_gui.app import App

from .linux_status import write_status

logger = logging.getLogger(__name__)


def prime_preview(app: App, sample_path: Path, status_file: Optional[Path]) -> None:
    logger.info("Priming Linux E2E previews with %s", sample_path)
    try:
        setattr(app, "_suppress_preview_error_dialogs", True)
    except Exception:  # pragma: no cover - defensive best effort
        pass

    viewmodel = getattr(app, "_viewmodel", None)
    if viewmodel is None:
        logger.error("Main window does not expose a viewmodel; cannot seed previews")
        write_status(status_file, preview="error", detail="no-viewmodel")
        return

    try:
        viewmodel.update_settings(input_path=str(sample_path))
        if hasattr(app, "_sync_controls_from_state"):
            app._sync_controls_from_state()
        result = app.render_previews()
    except Exception:  # pragma: no cover - diagnostic aid only
        logger.exception("Failed to render preview data for %s", sample_path)
        write_status(status_file, preview="error", detail="render-exception")
        return

    if result is None:
        logger.error("render_previews returned None; previews not initialised")
        write_status(status_file, preview="error", detail="no-result")
        return

    if hasattr(result, "is_err") and result.is_err():
        try:
            detail = result.error  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - fallback
            detail = "<unknown error>"
        logger.error("Preview rendering failed for %s: %s", sample_path, detail)
        write_status(status_file, preview="error", detail=str(detail))
        return

    logger.info("Preview data seeded successfully for Linux E2E screenshots")
    write_status(status_file, preview="ready")


__all__ = ["prime_preview"]

