from __future__ import annotations

import tkinter as tk

from ocarina_gui.preferences import Preferences, load_preferences
from shared.logging_config import ensure_app_logging

from app.version import get_app_version

from ._logging import LOGGER


class PreferencesMixin:
    """Initialise and expose application preferences."""

    def _initialise_preferences(self) -> object:
        self._log_path = ensure_app_logging()
        LOGGER.info("Starting Ocarina Arranger version %s", get_app_version())
        preferences = load_preferences()
        self._preferences = preferences
        return preferences

    @property
    def preferences(self) -> Preferences | None:
        stored = getattr(self, "_preferences", None)
        if isinstance(stored, Preferences):
            return stored
        return None

    def _setup_recent_projects(self, preferences: object) -> None:
        self._recent_projects: list[str] = list(
            getattr(preferences, "recent_projects", [])
        )
        self._recent_projects_menu: tk.Menu | None = None


__all__ = ["PreferencesMixin"]
