"""Project-related menu helpers for :class:`MenuActionsMixin`."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

from ocarina_gui.preferences import Preferences, save_preferences

from ._logger import logger


class ProjectMenuMixin:
    _viewmodel: object
    status: object
    _recent_projects_menu: tk.Menu
    _recent_projects: list[str]
    _preferences: Preferences | None

    def _open_project_command(self) -> None:
        result = self._viewmodel.open_project()
        if result is None:
            return
        if result.is_err():
            messagebox.showerror("Open Project", result.error)
            self.status.set(self._viewmodel.state.status_message)
            return
        self._sync_controls_from_state()
        self._mark_preview_stale()
        self._select_preview_tab("arranged")
        self._auto_render_preview(self._preview_frame_for_side("arranged"))
        self.status.set(self._viewmodel.state.status_message)
        loaded = result.unwrap()
        self._record_recent_project(str(loaded.archive_path))
        if hasattr(self, "_refresh_window_title"):
            self._refresh_window_title()

    def _save_project_command(self) -> None:
        self._sync_viewmodel_settings()
        result = self._viewmodel.save_project()
        if result is None:
            return
        if result.is_err():
            messagebox.showerror("Save Project", result.error)
            self.status.set(self._viewmodel.state.status_message)
            return
        saved_path = result.unwrap()
        self.status.set(self._viewmodel.state.status_message)
        self._record_recent_project(saved_path)
        if hasattr(self, "_refresh_window_title"):
            self._refresh_window_title()

    def _load_project_from_path(self, path: str) -> None:
        result = self._viewmodel.load_project_from(path)
        if result.is_err():
            messagebox.showerror("Open Project", result.error)
            self.status.set(self._viewmodel.state.status_message)
            return
        self._sync_controls_from_state()
        self._mark_preview_stale()
        self._select_preview_tab("arranged")
        self._auto_render_preview(self._preview_frame_for_side("arranged"))
        self.status.set(self._viewmodel.state.status_message)
        self._record_recent_project(path)
        if hasattr(self, "_refresh_window_title"):
            self._refresh_window_title()

    def _refresh_recent_projects_menu(self) -> None:
        menu = getattr(self, "_recent_projects_menu", None)
        if menu is None:
            return
        menu.delete(0, tk.END)
        projects = getattr(self, "_recent_projects", [])
        if not projects:
            menu.add_command(label="(No recent projects)", state="disabled")
            return
        for index, path in enumerate(projects[:10], start=1):
            label = f"{index}. {os.path.basename(path) or path}"
            menu.add_command(label=label, command=lambda p=path: self._load_project_from_path(p))

    def _record_recent_project(self, path: str) -> None:
        normalized = os.path.abspath(path)
        projects = [p for p in getattr(self, "_recent_projects", []) if os.path.abspath(p) != normalized]
        projects.insert(0, normalized)
        self._recent_projects = projects[:10]
        if hasattr(self, "_preferences") and isinstance(self._preferences, Preferences):
            self._preferences.recent_projects = list(self._recent_projects)
            try:
                save_preferences(self._preferences)
            except Exception:
                logger.debug("Failed to save recent projects preference", exc_info=True)
        self._refresh_recent_projects_menu()
