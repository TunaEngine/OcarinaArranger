"""Helpers for reading Linux automation configuration from the environment."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_path_from_env(name: str) -> Optional[Path]:
    raw = os.environ.get(name)
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception("Unable to create directory for %s: %s", name, path.parent)
        return None
    return path


def resolve_sample_path() -> Optional[Path]:
    sample_env = os.environ.get("OCARINA_E2E_SAMPLE_XML")
    if not sample_env:
        return None
    path = Path(sample_env).expanduser().resolve()
    if not path.exists():
        logger.warning("Sample MusicXML path %s does not exist", path)
        return None
    return path


@dataclass(frozen=True)
class AutomationPaths:
    """Resolved filesystem locations used by the Linux automation entrypoint."""

    sample: Optional[Path]
    status: Optional[Path]
    command: Optional[Path]


def load_automation_paths() -> AutomationPaths:
    """Resolve all known environment paths required for automation."""

    return AutomationPaths(
        sample=resolve_sample_path(),
        status=_resolve_path_from_env("OCARINA_E2E_STATUS_FILE"),
        command=_resolve_path_from_env("OCARINA_E2E_COMMAND_FILE"),
    )


__all__ = ["AutomationPaths", "load_automation_paths", "resolve_sample_path"]

