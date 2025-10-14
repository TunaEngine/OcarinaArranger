"""Helpers for persisting Linux automation status information."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def write_status(status_file: Optional[Path], **updates: object) -> None:
    """Merge ``updates`` into the existing JSON ``status_file`` if provided."""

    if status_file is None:
        return
    try:
        existing: dict[str, object] = {}
        if status_file.exists():
            try:
                payload = status_file.read_text(encoding="utf-8")
                existing = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                logger.debug("Status file %s contained invalid JSON", status_file)
        cleaned = {key: value for key, value in updates.items() if value is not None}
        removals = [key for key, value in updates.items() if value is None]
        existing.update(cleaned)
        for key in removals:
            existing.pop(key, None)
        status_file.write_text(json.dumps(existing), encoding="utf-8")
    except Exception:  # pragma: no cover - diagnostic aid only
        logger.exception("Failed to write Linux E2E status file to %s", status_file)


__all__ = ["write_status"]

