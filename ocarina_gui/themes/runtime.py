"""Runtime helpers that apply theme palettes to Tk widgets."""

from __future__ import annotations

import tkinter as tk
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from shared.tk_style import configure_style, get_ttk_style
from shared.ttk import ttk

from .library import get_current_theme
from .palettes import ThemePalette

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


def _maybe_set_widget_style_insert_color(widget: tk.Misc, color: str) -> None:
    if not _TTK_INSERT_WIDGET_TYPES or not isinstance(widget, _TTK_INSERT_WIDGET_TYPES):
        return

    style_name = ""
    try:
        style_name = widget.cget("style")
    except tk.TclError:
        style_name = ""

    if not style_name:
        style_name = widget.winfo_class()

    # CRITICAL FIX: Avoid calling get_ttk_style() without theme parameter
    # This was causing the theme to reset to the default "litera"
    
    # Strategy 1: Try to find existing style instance from widget hierarchy
    style = None
    try:
        # Check if the widget's toplevel has the style
        root = widget.winfo_toplevel()
        if hasattr(root, '_style') and root._style is not None:
            style = root._style
        
        # Check if any parent widget has a style attribute
        if style is None:
            parent = widget
            for _ in range(10):  # Max 10 levels up
                parent = parent.nametowidget(parent.winfo_parent())
                if hasattr(parent, '_style') and parent._style is not None:
                    style = parent._style
                    break
                if parent == root:
                    break
    except (tk.TclError, AttributeError):
        pass
    
    # Strategy 2: Use global style if available and preserve its current theme
    if style is None:
        try:
            from shared.tk_style import _STYLE
            if _STYLE is not None:
                # Use the existing global style which should have the correct theme
                style = _STYLE
        except (ImportError, AttributeError):
            pass
    
    # Strategy 3: Only if no style found, get one without changing theme
    if style is None:
        try:
            # Get style but try to preserve current theme by not specifying theme parameter
            # This is risky as it may still default to "litera"
            style = get_ttk_style(widget)
        except tk.TclError:
            # If that fails, give up on setting insert color for this widget
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

    try:
        style = get_ttk_style(window, theme=theme.ttk_theme)
    except tk.TclError:
        style = None
    else:
        set_ttk_caret_color(style, palette.text_cursor)

    apply_insert_cursor_color(window, palette.text_cursor)
    _apply_window_background(window, palette.window_background)
    
    # Configure Panel styles for standalone windows that contain Panel.TFrame/Panel.TLabelframe widgets
    if style is not None:
        from shared.tk_style import configure_panel_styles
        try:
            configure_panel_styles(style, palette.window_background, palette.text_primary)
            # Apply Panel styles again after a brief delay to handle ttkbootstrap resets
            def _apply_panel_styles_later():
                try:
                    configure_panel_styles(style, palette.window_background, palette.text_primary)
                except Exception:
                    pass
            window.after(1, _apply_panel_styles_later)
        except Exception:
            # Don't fail if Panel style configuration fails
            pass
    
    _schedule_insert_refresh(
        window,
        insert_color=palette.text_cursor,
        background_color=palette.window_background,
        remaining=3,
    )

    return palette


__all__ = [
    "INSERT_BACKGROUND_PATTERNS",
    "apply_insert_cursor_color",
    "apply_theme_to_toplevel",
    "ensure_insert_bindings",
    "set_ttk_caret_color",
]
