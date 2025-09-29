"""Tooltip widget used by the layout editor canvases."""

from __future__ import annotations

from typing import Callable, Dict, Tuple

import tkinter as tk

from ..color_utils import hex_to_rgb, mix_colors, rgb_to_hex
from ..themes import ThemeSpec, get_current_theme, register_theme_listener


class CanvasTooltip:
    """Lightweight tooltip for canvas elements."""

    def __init__(self, widget: tk.Widget) -> None:
        self._widget = widget
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._text: str = ""
        self._colors = self._resolve_colors(get_current_theme())
        self._unsubscribe: Callable[[], None] | None = register_theme_listener(
            self._on_theme_changed
        )

    def show(self, text: str, x: int, y: int) -> None:
        if not text:
            self.hide()
            return

        if self._window is None:
            self._window = tk.Toplevel(self._widget)
            self._window.withdraw()
            self._window.wm_overrideredirect(True)
            try:
                self._window.transient(self._widget.winfo_toplevel())
            except tk.TclError:  # pragma: no cover - widget destroyed
                pass
            self._apply_colors()
            self._label = tk.Label(
                self._window,
                text=text,
                background=self._colors["background"],
                foreground=self._colors["foreground"],
                borderwidth=0,
                padx=6,
                pady=3,
            )
            self._label.pack(padx=1, pady=1)

        if self._label and text != self._text:
            self._label.configure(text=text)

        self._text = text
        if self._window is not None:
            self._window.geometry(f"+{int(x)}+{int(y)}")
            self._window.deiconify()
            self._window.lift()

    def hide(self) -> None:
        window = self._window
        if window is not None:
            try:
                if window.winfo_exists():
                    window.withdraw()
                else:
                    self._window = None
                    self._label = None
            except tk.TclError:
                self._window = None
                self._label = None
        self._text = ""

    def close(self) -> None:
        self.hide()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        window = self._window
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass
        self._window = None
        self._label = None

    # ------------------------------------------------------------------
    def _apply_colors(self) -> None:
        if self._window is not None:
            self._window.configure(background=self._colors["border"], padx=0, pady=0)
        if self._label is not None:
            self._label.configure(
                background=self._colors["background"],
                foreground=self._colors["foreground"],
            )

    @staticmethod
    def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
        def _channel(value: int) -> float:
            normalized = value / 255.0
            if normalized <= 0.03928:
                return normalized / 12.92
            return ((normalized + 0.055) / 1.055) ** 2.4

        r, g, b = (_channel(component) for component in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _resolve_colors(self, theme: ThemeSpec) -> Dict[str, str]:
        window_rgb = hex_to_rgb(theme.palette.window_background)
        text_rgb = hex_to_rgb(theme.palette.text_primary)
        window_luma = self._relative_luminance(window_rgb)
        text_luma = self._relative_luminance(text_rgb)

        if window_luma < text_luma:
            background_rgb = mix_colors(window_rgb, (255, 255, 255), 0.25)
            border_rgb = mix_colors(window_rgb, (255, 255, 255), 0.4)
            foreground_rgb = text_rgb
        else:
            background_rgb = mix_colors(window_rgb, (0, 0, 0), 0.1)
            border_rgb = mix_colors(window_rgb, (0, 0, 0), 0.2)
            foreground_rgb = text_rgb

        return {
            "background": rgb_to_hex(background_rgb),
            "foreground": rgb_to_hex(foreground_rgb),
            "border": rgb_to_hex(border_rgb),
        }

    def _on_theme_changed(self, theme: ThemeSpec) -> None:
        self._colors = self._resolve_colors(theme)
        self._apply_colors()


__all__ = ["CanvasTooltip"]
