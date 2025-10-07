from __future__ import annotations

import logging
import tkinter as tk
from importlib import resources
from typing import Callable, Dict, List

from shared.ttk import ttk

from ocarina_gui.constants import APP_TITLE
from ocarina_gui.themes import (
    INSERT_BACKGROUND_PATTERNS,
    ThemeSpec,
    ensure_insert_bindings,
    get_available_themes,
    get_current_theme,
    register_theme_listener,
    set_ttk_caret_color,
)
from shared.logging_config import get_file_log_verbosity
from shared.tk_style import get_ttk_style
from ui.logging_preferences import LOG_VERBOSITY_CHOICES

from ._logging import LOGGER
from .resources import get_main_window_resource


class ThemeInitialisationMixin:
    """Handle bootstrap theme initialisation and window chrome."""

    def _setup_theme_support(
        self, preferences: object, current_theme: ThemeSpec | None = None
    ) -> None:
        if current_theme is None:
            current_theme = get_current_theme()
        self.theme_id = tk.StringVar(master=self, value=current_theme.theme_id)
        self.theme_name = tk.StringVar(master=self, value=current_theme.name)
        self._theme_choices = get_available_themes()
        # Ensure diagnostic logs from the theme menu are emitted during headless
        # tests. The logger defaults to ``WARNING`` which would otherwise
        # suppress the informational messages our behaviour checks assert.
        LOGGER_THEME = logging.getLogger("ui.main_window.menus.theme")
        if LOGGER_THEME.level == logging.NOTSET:
            LOGGER_THEME.setLevel(logging.INFO)
        self._log_verbosity = tk.StringVar(master=self, value=get_file_log_verbosity().value)
        self._log_verbosity_choices = LOG_VERBOSITY_CHOICES
        self._restore_log_verbosity_preference(preferences)
        self.pitch_list: List[str] = list(self._viewmodel.state.pitch_list)
        self._style: ttk.Style | None = None
        self._theme_unsubscribe: Callable[[], None] | None = register_theme_listener(
            self._apply_theme
        )
        self._theme: ThemeSpec | None = None
        self._theme_actions: Dict[str, Callable[[], None]] = {}
        self._log_menu_actions: Dict[str, Callable[[], None]] = {}
        self._applied_style_maps: Dict[str, List[str]] = {}
        self._registered_menus: list[tk.Menu] = []
        self._menubar: tk.Menu | None = None
        self._menu_palette_snapshot: dict[str, str] | None = None
        self._last_title_background_attempt: str | None = None
        self._last_title_color_attempt: str | None = None
        self._last_title_dark_mode_attempt: bool | None = None
        self._last_title_hwnd_attempt: int | None = None

        self._prime_theme_defaults(current_theme)

    def _prime_theme_defaults(self, theme: ThemeSpec) -> None:
        if self._headless:
            return

        palette = theme.palette

        try:
            self.configure(background=palette.window_background)
        except tk.TclError:
            pass

        style: ttk.Style | None = getattr(self, "style", None)
        if style is not None:
            try:
                style.theme_use(theme.ttk_theme)
            except tk.TclError:
                style = None
        if style is None:
            style = get_ttk_style(self, theme=theme.ttk_theme)
        self._style = style
        try:
            ensure_insert_bindings(self, palette.text_cursor)
        except tk.TclError:
            pass
        set_ttk_caret_color(style, palette.text_cursor)

        for pattern, value in theme.options.items():
            try:
                self.option_add(pattern, value)
            except tk.TclError:
                continue

        for pattern in INSERT_BACKGROUND_PATTERNS:
            try:
                self.option_add(pattern, palette.text_cursor)
            except tk.TclError:
                continue

    def _configure_main_window_shell(self) -> None:
        if not self._headless:
            icon_image = self._load_window_photoimage("app_icon.png")
            if icon_image is not None:
                self.iconphoto(False, icon_image)
                self._window_icon_image = icon_image
            else:
                LOGGER.warning(
                    "Application icon resource %s could not be loaded",
                    "app_icon.png",
                )

            if not self._apply_windows_taskbar_icon("app_icon.ico"):
                LOGGER.warning(
                    "Windows taskbar icon resource %s could not be applied",
                    "app_icon.ico",
                )

            self.title(APP_TITLE)
            self.geometry("860x560")
            self.resizable(True, True)
            current_theme = get_current_theme()
            style: ttk.Style | None = getattr(self, "style", None)
            if style is not None:
                try:
                    style.theme_use(current_theme.ttk_theme)
                except tk.TclError:
                    style = None
            if style is None:
                style = get_ttk_style(self, theme=current_theme.ttk_theme)
            self._style = style
            self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_theme_actions()
        if not self._headless:
            self._build_menus()
        self._apply_auto_scroll_mode(self._auto_scroll_mode_value)
        LOGGER.info(
            "Main window initialised (headless=%s, log_path=%s, log_verbosity=%s)",
            self._headless,
            self._log_path,
            self._log_verbosity.get(),
        )

    def _load_window_photoimage(self, resource_name: str) -> tk.PhotoImage | None:
        resource = get_main_window_resource(resource_name)
        if resource is None:
            return None

        try:
            with resources.as_file(resource) as path:  # type: ignore[attr-defined]
                icon_path = str(path)
                return tk.PhotoImage(master=self, file=icon_path)
        except tk.TclError:
            LOGGER.exception("Failed to load application icon from %s", resource_name)
        except FileNotFoundError:
            LOGGER.warning("Application icon missing at %s", resource_name)
        return None

    def _apply_windows_taskbar_icon(self, resource_name: str) -> bool:
        resource = get_main_window_resource(resource_name)
        if resource is None:
            return False

        try:
            with resources.as_file(resource) as path:  # type: ignore[attr-defined]
                icon_path = str(path)
                try:
                    self.iconbitmap(bitmap=icon_path)
                    return True
                except tk.TclError:
                    LOGGER.exception(
                        "Failed to apply Windows taskbar icon from %s", icon_path
                    )
        except FileNotFoundError:
            LOGGER.warning("Windows taskbar icon missing at %s", resource_name)
        return False


__all__ = ["ThemeInitialisationMixin"]
