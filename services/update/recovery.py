"""Helpers for reporting update failures to the relaunched application."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from services.update.constants import INSTALL_ROOT_ENV, UPDATE_FAILURE_MARKER_SUFFIX

_LOGGER = logging.getLogger(__name__)


def find_install_root() -> Path | None:
    """Return the installation root for the current process when available."""

    override = os.environ.get(INSTALL_ROOT_ENV)
    if override:
        path = Path(override).expanduser()
        if path.exists() and path.is_dir():
            return path
        _LOGGER.debug("Configured installation directory missing or invalid: %s", path)
        return None

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return None


def get_failure_marker_path(install_root: Path) -> Path:
    """Return the sentinel file path used to record update failures."""

    return install_root.parent / f"{install_root.name}{UPDATE_FAILURE_MARKER_SUFFIX}"


def consume_update_failure_notice() -> tuple[str, str] | None:
    """Return the recorded failure reason and advice, removing the marker."""

    install_root = find_install_root()
    if install_root is None:
        return None

    marker_path = get_failure_marker_path(install_root)
    if not marker_path.exists():
        return None

    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        _LOGGER.debug("Unable to parse update failure marker at %s", marker_path, exc_info=True)
        _safe_remove(marker_path)
        return None

    reason = _coerce_text(payload.get("reason"), default="Unknown error.")
    advice = _coerce_text(payload.get("advice"), default="Please try again later.")

    _safe_remove(marker_path)
    return reason, advice


def _coerce_text(value: Any, *, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _safe_remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        _LOGGER.debug("Unable to remove update failure marker at %s", path, exc_info=True)


__all__ = [
    "consume_update_failure_notice",
    "find_install_root",
    "get_failure_marker_path",
]
