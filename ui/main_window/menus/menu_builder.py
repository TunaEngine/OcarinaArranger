"""Menu construction for :class:`MenuActionsMixin`."""

from __future__ import annotations

import sys
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
        # Decide whether to use native menubar (macOS) or custom (others).
        self._use_native_menubar = (sys.platform == "darwin")
        if self._use_native_menubar:
            menubar = self._register_menu(menubar, role="menubar")
            self.config(menu=menubar)
        else:
            # Register but as a normal submenu so Windows native theming logic
            # does not try to recolor a non-existent OS menubar.
            menubar = self._register_menu(menubar, role="submenu")
            # Defer creation of the CustomMenuBar until after items are added.

        file_menu = self._register_menu(tk.Menu(menubar, tearoff=False))
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Project...", command=self._open_project_command)
        file_menu.add_command(label="Save Project...", command=self._save_project_command)
        self._recent_projects_menu = self._register_menu(tk.Menu(file_menu, tearoff=False))
        file_menu.add_cascade(label="Open Recent", menu=self._recent_projects_menu)
        self._refresh_recent_projects_menu()
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)

        view_menu = self._register_menu(tk.Menu(menubar, tearoff=False))
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
            auto_scroll_menu = self._register_menu(tk.Menu(view_menu, tearoff=False))
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
            layout_menu = self._register_menu(tk.Menu(view_menu, tearoff=False))
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

        logs_menu = self._register_menu(tk.Menu(menubar, tearoff=False))
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

        tools_menu = self._register_menu(tk.Menu(menubar, tearoff=False))
        menubar.add_cascade(label="Tools", menu=tools_menu)

        update_entries_added = False

        manual_update = getattr(self, "_check_for_updates_command", None)
        if callable(manual_update):
            tools_menu.add_command(
                label="Check for Updates...",
                command=manual_update,
            )
            update_entries_added = True

        auto_update_var = getattr(self, "_auto_update_enabled_var", None)
        toggle_auto_update = getattr(self, "_on_auto_update_toggled", None)
        if isinstance(auto_update_var, tk.BooleanVar) and callable(toggle_auto_update):
            if update_entries_added:
                tools_menu.add_separator()
            tools_menu.add_checkbutton(
                label="Enable Automatic Updates",
                variable=auto_update_var,
                command=toggle_auto_update,
            )
            update_entries_added = True

        channel_var = getattr(self, "_update_channel_var", None)
        channel_changed = getattr(self, "_on_update_channel_changed", None)
        choices = getattr(self, "_update_channel_choices", [])
        if isinstance(channel_var, tk.StringVar) and callable(channel_changed) and choices:
            if update_entries_added:
                tools_menu.add_separator()
            for label, value in choices:
                tools_menu.add_radiobutton(
                    label=label,
                    variable=channel_var,
                    value=value,
                    command=channel_changed,
                )
            update_entries_added = True

        if update_entries_added:
            tools_menu.add_separator()

        tools_menu.add_command(
            label="Instrument Layout Editor...",
            command=self.open_instrument_layout_editor,
        )

        help_menu = self._register_menu(tk.Menu(menubar, tearoff=False))
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(
            label="Send Feedback...",
            command=self._send_feedback_command,
        )
        help_menu.add_command(
            label="Report a Problem...",
            command=self._report_problem_command,
        )
        help_menu.add_command(
            label="Suggest a Feature...",
            command=self._suggest_feature_command,
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="Community (Discord)",
            command=self._open_discord_command,
        )

        # If using the custom menubar, build it now that cascades are defined.
        if not getattr(self, "_use_native_menubar", False) and not getattr(self, "_headless", False):
            try:
                from .custom_bar import CustomMenuBar  # local import to avoid cycles
            except Exception:
                CustomMenuBar = None  # type: ignore
            if CustomMenuBar is not None:
                try:
                    self._custom_menubar = CustomMenuBar(self, menubar)
                    self._custom_menubar.pack(side="top", fill="x")
                except Exception:
                    self._custom_menubar = None
