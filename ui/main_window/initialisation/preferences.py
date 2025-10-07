from __future__ import annotations

import tkinter as tk

import sys

from ocarina_gui.preferences import Preferences

from ._logging import LOGGER


class PreferencesMixin:
    """Initialise and expose application preferences."""

    def _initialise_preferences(self) -> object:
        initialisation_module = sys.modules[__name__.rsplit(".", 1)[0]]

        ensure_logging = getattr(initialisation_module, "ensure_app_logging")
        version_getter = getattr(initialisation_module, "get_app_version")
        preferences_loader = getattr(initialisation_module, "load_preferences")

        self._log_path = ensure_logging()
        LOGGER.info("Starting Ocarina Arranger version %s", version_getter())
        preferences = preferences_loader()
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
