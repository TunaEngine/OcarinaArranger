"""Menu construction for :class:`MenuActionsMixin`."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Sequence, Tuple

from ocarina_gui.scrolling import AutoScrollMode
from shared.logging_config import LogVerbosity


class MenuBuilderMixin:
    _theme_choices: Sequence
    _theme_actions: Dict[str, Callable[[], None]]
    _log_verbosity_choices: Sequence[Tuple[str, LogVerbosity]]
    _log_menu_actions: Dict[str, Callable[[], None]]
    _log_verbosity: tk.Variable

    def _build_menus(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Project...", command=self._open_project_command)
        file_menu.add_command(label="Save Project...", command=self._save_project_command)
        self._recent_projects_menu = tk.Menu(file_menu, tearoff=False)
        file_menu.add_cascade(label="Open Recent", menu=self._recent_projects_menu)
        self._refresh_recent_projects_menu()
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)

        view_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="View", menu=view_menu)

        for choice in self._theme_choices:
            callback = self._theme_actions.get(choice.theme_id)
            if callback is None:
                callback = self._make_theme_callback(choice.theme_id)
                self._theme_actions[choice.theme_id] = callback
            view_menu.add_radiobutton(
                label=choice.name,
                command=callback,
                variable=self.theme_id,
                value=choice.theme_id,
            )

        if hasattr(self, "_auto_scroll_mode"):
            view_menu.add_separator()
            auto_scroll_menu = tk.Menu(view_menu, tearoff=False)
            view_menu.add_cascade(label="Auto-scroll Mode", menu=auto_scroll_menu)
            for mode in AutoScrollMode:
                auto_scroll_menu.add_radiobutton(
                    label=mode.label,
                    variable=self._auto_scroll_mode,
                    value=mode.value,
                    command=lambda m=mode: self._apply_auto_scroll_mode(m.value),
                )

        if hasattr(self, "preview_layout_mode"):
            view_menu.add_separator()
            layout_menu = tk.Menu(view_menu, tearoff=False)
            view_menu.add_cascade(label="Preview Layout", menu=layout_menu)
            layout_labels = getattr(self, "_preview_layout_value_to_label", {})
            ordered_values = list(layout_labels.keys())
            for value in ordered_values:
                label = layout_labels.get(value)
                if not label:
                    continue

                def _select_layout(v=value) -> None:
                    try:
                        current = self.preview_layout_mode.get()
                    except Exception:
                        current = None
                    if current != v:
                        self.preview_layout_mode.set(v)

                layout_menu.add_radiobutton(
                    label=label,
                    variable=self.preview_layout_mode,
                    value=value,
                    command=_select_layout,
                )

        logs_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Logs", menu=logs_menu)
        for label, verbosity in self._log_verbosity_choices:
            callback = self._log_menu_actions.get(verbosity.value)
            if callback is None:
                callback = self._make_log_verbosity_callback(verbosity)
                self._log_menu_actions[verbosity.value] = callback
            logs_menu.add_radiobutton(
                label=label,
                command=callback,
                variable=self._log_verbosity,
                value=verbosity.value,
            )

        tools_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(
            label="Instrument Layout Editor...",
            command=self.open_instrument_layout_editor,
        )
