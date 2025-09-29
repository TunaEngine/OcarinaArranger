"""Utilities for managing UI log verbosity preferences."""

from __future__ import annotations

import logging
from typing import Callable

from ocarina_gui.preferences import Preferences, load_preferences, save_preferences
from shared.logging_config import LogVerbosity, set_file_log_verbosity

logger = logging.getLogger(__name__)


LOG_VERBOSITY_CHOICES: tuple[tuple[str, LogVerbosity], ...] = (
    ("Disabled", LogVerbosity.DISABLED),
    ("Error", LogVerbosity.ERROR),
    ("Warning", LogVerbosity.WARNING),
    ("Info", LogVerbosity.INFO),
    ("Verbose", LogVerbosity.VERBOSE),
)


def apply_log_verbosity(
    verbosity: LogVerbosity,
    *,
    on_failure: Callable[[LogVerbosity, Exception], None] | None = None,
) -> bool:
    """Set the application log verbosity, returning ``True`` on success."""

    try:
        set_file_log_verbosity(verbosity)
    except Exception as exc:  # pragma: no cover - defensive against logging issues
        logger.exception(
            "Failed to update log verbosity", extra={"verbosity": verbosity.value}
        )
        if on_failure is not None:
            on_failure(verbosity, exc)
        return False
    return True


def restore_log_verbosity_preference(preferences: Preferences) -> LogVerbosity | None:
    """Apply the stored log verbosity preference if it is valid."""

    saved = preferences.log_verbosity
    if not saved:
        return None
    try:
        verbosity = LogVerbosity(saved)
    except ValueError:
        logger.warning(
            "Ignoring invalid log verbosity preference", extra={"verbosity": saved}
        )
        return None
    if not apply_log_verbosity(verbosity):
        return None
    return verbosity


def persist_log_verbosity(verbosity: LogVerbosity) -> None:
    """Persist the selected verbosity in the user preferences store."""

    preferences = load_preferences()
    preferences.log_verbosity = verbosity.value
    save_preferences(preferences)


__all__ = [
    "LOG_VERBOSITY_CHOICES",
    "apply_log_verbosity",
    "persist_log_verbosity",
    "restore_log_verbosity_preference",
]
