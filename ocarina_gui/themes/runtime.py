"""Runtime helpers that apply theme palettes to Tk widgets."""

from __future__ import annotations

import logging
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from tkinter import ttk as tkttk
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from shared.tk_style import configure_style, get_ttk_style, _reset_bootstrap_instance
from shared.ttk import ttk, use_bootstrap_ttk, use_native_ttk

from .library import get_current_theme
from .palettes import ThemePalette
from .spec import ThemeSpec

logger = logging.getLogger(__name__)

INSERT_BACKGROUND_PATTERNS: Tuple[str, ...] = (
    "*insertBackground",
    "*insertbackground",
    "*Entry.insertBackground",
    "*Entry.insertbackground",
    "*Entry*insertBackground",
    "*Entry*insertbackground",
    "*Text.insertBackground",
    "*Text.insertbackground",
    "*Text*insertBackground",
    "*Spinbox.insertBackground",
    "*Spinbox.insertbackground",
    "*Spinbox*insertBackground",
    "*TEntry*insertBackground",
    "*TEntry*insertbackground",
    "*TSpinbox*insertBackground",
    "*TSpinbox*insertbackground",
    "*TCombobox*insertBackground",
    "*TCombobox*insertbackground",
)

_TTK_INSERT_STYLE_NAMES: Tuple[str, ...] = ("TEntry", "TSpinbox", "TCombobox")
_CURRENT_INSERT_COLOR = "#000000"
_INSERT_BINDINGS_INSTALLED = False

try:
    _TTK_INSERT_WIDGET_TYPES: Tuple[type, ...] = tuple(
        getattr(ttk, name)
        for name in ("Entry", "Spinbox", "Combobox")
        if hasattr(ttk, name)
    )
except Exception:  # pragma: no cover - minimal Tk distributions
    _TTK_INSERT_WIDGET_TYPES = ()


def _configure_ttk_insert_color(style: ttk.Style, style_name: str, color: str) -> None:
    configure_style(style, style_name, insertcolor=color)


def _ensure_default_ttk_insert_colors(style: ttk.Style, color: str) -> None:
    for style_name in _TTK_INSERT_STYLE_NAMES:
        _configure_ttk_insert_color(style, style_name, color)


def _widget_style_candidates(widget: tk.Misc) -> Iterable[Optional[ttk.Style]]:
    try:
        root = widget.winfo_toplevel()
    except tk.TclError:
        root = None

    if root is not None:
        style = getattr(root, "_style", None)
        if isinstance(style, ttk.Style):
            yield style

        parent = widget
        for _ in range(10):
            try:
                parent = parent.nametowidget(parent.winfo_parent())
            except (tk.TclError, AttributeError, KeyError):
                break
            style = getattr(parent, "_style", None)
            if isinstance(style, ttk.Style):
                yield style
            if parent is root:
                break

    try:
        from shared import tk_style as tk_style_module
    except ImportError:
        tk_style_module = None

    if tk_style_module is not None:
        cached = getattr(tk_style_module, "_STYLE", None)
        if isinstance(cached, ttk.Style):
            yield cached


def _resolve_widget_style(widget: tk.Misc) -> Optional[ttk.Style]:
    for candidate in _widget_style_candidates(widget):
        if candidate is not None:
            return candidate

    try:
        return get_ttk_style(widget)
    except (tk.TclError, ModuleNotFoundError):
        return None


def _maybe_set_widget_style_insert_color(widget: tk.Misc, color: str) -> None:
    if not _TTK_INSERT_WIDGET_TYPES or not isinstance(widget, _TTK_INSERT_WIDGET_TYPES):
        return

    try:
        style_name = widget.cget("style")
    except tk.TclError:
        style_name = ""

    if not style_name:
        style_name = widget.winfo_class()

    style = _resolve_widget_style(widget)
    if style is None:
        return

    _configure_ttk_insert_color(style, style_name, color)


def set_ttk_caret_color(style: ttk.Style, color: str) -> None:
    """Apply ``color`` to the insertion cursor for common ttk entry styles."""

    _ensure_default_ttk_insert_colors(style, color)


def _ensure_insert_bindings(window: tk.Misc) -> None:
    global _INSERT_BINDINGS_INSTALLED

    if _INSERT_BINDINGS_INSTALLED:
        return

    def _refresh_insert_color(event: tk.Event) -> None:
        widget = getattr(event, "widget", None)
        if widget is None:
            return
        try:
            widget.configure(insertbackground=_CURRENT_INSERT_COLOR)
        except (tk.TclError, AttributeError):
            pass
        if isinstance(widget, tk.Misc):
            _maybe_set_widget_style_insert_color(widget, _CURRENT_INSERT_COLOR)

    for class_name in ("Entry", "Spinbox", "Text", "TEntry", "TSpinbox", "TCombobox"):
        try:
            window.bind_class(class_name, "<Map>", _refresh_insert_color, add="+")
        except tk.TclError:
            continue

    _INSERT_BINDINGS_INSTALLED = True


def ensure_insert_bindings(window: tk.Misc, color: str) -> None:
    """Keep class-level insertion cursor bindings aligned with ``color``."""

    global _CURRENT_INSERT_COLOR

    _CURRENT_INSERT_COLOR = color
    _ensure_insert_bindings(window)


def apply_insert_cursor_color(widget: tk.Misc, color: str) -> None:
    """Force ``insertbackground`` on ``widget`` and all descendants."""

    queue: Deque[tk.Misc] = deque([widget])
    seen: Set[str] = set()

    while queue:
        current = queue.popleft()
        identifier = str(current)
        if identifier in seen:
            continue
        seen.add(identifier)

        if hasattr(current, "configure"):
            try:
                current.configure(insertbackground=color)
            except (tk.TclError, AttributeError):
                pass

        _maybe_set_widget_style_insert_color(current, color)

        try:
            children = current.winfo_children()
        except tk.TclError:
            continue
        for child in children:
            if isinstance(child, tk.Misc):
                queue.append(child)


def _apply_window_background(window: tk.Misc, color: str) -> None:
    try:
        window.configure(background=color)
    except tk.TclError:
        pass


def _schedule_insert_refresh(
    window: tk.Misc,
    *,
    insert_color: str,
    background_color: str,
    remaining: int,
) -> None:
    if remaining <= 0:
        return

    def _refresh() -> None:
        try:
            if window.winfo_exists():
                apply_insert_cursor_color(window, insert_color)
                _apply_window_background(window, background_color)
        except tk.TclError:
            return
        _schedule_insert_refresh(
            window,
            insert_color=insert_color,
            background_color=background_color,
            remaining=remaining - 1,
        )

    try:
        window.after_idle(_refresh)
    except tk.TclError:
        return


@dataclass(frozen=True)
class ResolvedStyle:
    """Container describing the ttk style selected for a theme."""

    style: ttk.Style
    bootstrap_active: bool


def _is_bootstrap_style(style: ttk.Style) -> bool:
    module_name = type(style).__module__
    return "ttkbootstrap" in module_name


def _ensure_theme_selected(style: ttk.Style, theme_name: Optional[str]) -> bool:
    if not theme_name:
        return True

    try:
        current_theme = str(style.theme_use())
    except Exception:
        return False

    if current_theme == theme_name:
        return True

    try:
        style.theme_use(theme_name)
    except Exception:
        return False

    try:
        return str(style.theme_use()) == theme_name
    except Exception:
        return False


def _ensure_ttk_theme(style: ttk.Style, theme_name: str, fallback: str = "clam") -> bool:
    """Activate ``theme_name`` for ``style`` or fall back to ``fallback``."""

    if not theme_name:
        return True

    try:
        style.theme_use(theme_name)
        return True
    except Exception:
        pass

    try:
        names: Set[str] = {str(name) for name in style.theme_names()}
    except Exception:
        names = set()

    if theme_name not in names:
        try:
            style.theme_create(theme_name, parent=fallback)
        except Exception:
            pass

    try:
        style.theme_use(theme_name)
        return True
    except Exception:
        if fallback:
            try:
                style.theme_use(fallback)
            except Exception:
                pass
        return False


def resolve_theme_style(master: tk.Misc, theme: ThemeSpec) -> ResolvedStyle:
    """Return a ttk ``Style`` configured for ``theme`` with graceful fallbacks."""

    style: Optional[ttk.Style] = None
    bootstrap_active = False

    try:
        candidate = get_ttk_style(master, theme=theme.ttk_theme)
    except ModuleNotFoundError:
        logger.debug("ttkbootstrap unavailable; using native ttk style")
    except Exception:
        logger.debug("Failed to create ttkbootstrap style; falling back to native ttk", exc_info=True)
    else:
        style = candidate
        bootstrap_active = _is_bootstrap_style(candidate) and _ensure_theme_selected(
            candidate, theme.ttk_theme
        )
        if bootstrap_active:
            _guard_bootstyle_theme_updates()
        else:
            logger.debug(
                "Requested ttkbootstrap theme '%s' missing; using native ttk", theme.ttk_theme
            )

    if style is None or not bootstrap_active:
        style = tkttk.Style(master=master)
        _ensure_ttk_theme(style, theme.ttk_theme)
        _reset_bootstrap_instance()
        bootstrap_active = False

    return ResolvedStyle(style=style, bootstrap_active=bootstrap_active)


def _activate_ttk_namespace(bootstrap_active: bool) -> bool:
    if not bootstrap_active:
        use_native_ttk()
        return False

    try:
        use_bootstrap_ttk()
    except ModuleNotFoundError:
        logger.debug(
            "ttkbootstrap reported as active but import now fails; reverting to native ttk",
            exc_info=True,
        )
        use_native_ttk()
        return False

    return True


def apply_theme_to_toplevel(window: tk.Misc) -> ThemePalette:
    """Apply the current theme's Tk option defaults to ``window``."""

    theme = get_current_theme()
    palette = theme.palette
    option_priority = 200

    try:
        ensure_insert_bindings(window, palette.text_cursor)
    except tk.TclError:
        pass

    for pattern, value in theme.options.items():
        try:
            window.option_add(pattern, value, option_priority)
        except tk.TclError:
            continue

    for pattern in INSERT_BACKGROUND_PATTERNS:
        try:
            window.option_add(pattern, palette.text_cursor, option_priority)
        except tk.TclError:
            continue

    resolution = resolve_theme_style(window, theme)
    style = resolution.style
    bootstrap_active = _activate_ttk_namespace(resolution.bootstrap_active)

    try:
        set_ttk_caret_color(style, palette.text_cursor)
    except Exception:
        logger.debug("Unable to update ttk caret colour", exc_info=True)

    apply_insert_cursor_color(window, palette.text_cursor)
    _apply_window_background(window, palette.window_background)

    try:
        from shared.tk_style import configure_panel_styles

        configure_panel_styles(style, palette.window_background, palette.text_primary)

        def _apply_panel_styles_later() -> None:
            try:
                configure_panel_styles(style, palette.window_background, palette.text_primary)
            except Exception:
                pass

        window.after(1, _apply_panel_styles_later)
    except Exception:
        pass

    _schedule_insert_refresh(
        window,
        insert_color=palette.text_cursor,
        background_color=palette.window_background,
        remaining=3,
    )

    return palette


def _guard_bootstyle_theme_updates() -> None:
    """Prevent ttkbootstrap from raising when a requested theme is unavailable."""

    try:
        from ttkbootstrap.style import Bootstyle
    except ModuleNotFoundError:  # pragma: no cover - ttkbootstrap missing entirely
        return

    if getattr(Bootstyle, "_ocarina_guard_installed", False):
        return

    original_update = Bootstyle.update_ttk_widget_style

    def safe_update(widget=None, style_string=None, **kwargs):
        try:
            return original_update(widget, style_string, **kwargs)
        except KeyError:
            resolved = style_string
            if isinstance(style_string, (tuple, list)):
                resolved = " ".join(str(token) for token in style_string if token)
            if isinstance(resolved, str) and resolved and resolved.lower() != "default":
                return resolved
            return ""

    Bootstyle.update_ttk_widget_style = staticmethod(safe_update)
    Bootstyle._ocarina_guard_installed = True


__all__ = [
    "INSERT_BACKGROUND_PATTERNS",
    "ResolvedStyle",
    "apply_insert_cursor_color",
    "apply_theme_to_toplevel",
    "ensure_insert_bindings",
    "resolve_theme_style",
    "set_ttk_caret_color",
]
