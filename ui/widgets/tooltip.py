"""Lightweight tooltip helper for form controls."""

from __future__ import annotations

import tkinter as tk
from typing import Optional


class _Tooltip:
    """Display delayed contextual help for a widget."""

    def __init__(self, widget: tk.Widget, text: str, *, delay: int, wraplength: int) -> None:
        self._widget = widget
        self._text = text
        self._delay = max(0, delay)
        self._wraplength = max(120, wraplength)
        self._after_id: Optional[str] = None
        self._window: Optional[tk.Toplevel] = None

        self._enter_binding = widget.bind("<Enter>", self._on_enter, add="+")
        self._leave_binding = widget.bind("<Leave>", self._on_leave, add="+")
        self._press_binding = widget.bind("<ButtonPress>", self._on_leave, add="+")
        self._focus_binding = widget.bind("<FocusOut>", self._on_leave, add="+")
        self._destroy_binding = widget.bind("<Destroy>", self._on_destroy, add="+")

    def _on_enter(self, _event: tk.Event) -> None:
        if self._after_id is not None:
            self._widget.after_cancel(self._after_id)
        self._after_id = self._widget.after(self._delay, self._show)

    def _on_leave(self, _event: tk.Event) -> None:
        self._cancel()

    def _on_destroy(self, _event: tk.Event) -> None:
        self._cancel()
        self._unbind()

    def _show(self) -> None:
        self._after_id = None
        if not self._text:
            return
        if not self._widget.winfo_exists():
            return
        if self._window is not None and self._window.winfo_exists():
            return

        root = self._widget.winfo_toplevel()
        window = tk.Toplevel(master=root)
        window.wm_overrideredirect(True)
        window.attributes("-topmost", True)

        x = self._widget.winfo_rootx() + 12
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            window,
            text=self._text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=self._wraplength,
            padx=6,
            pady=4,
        )
        label.pack()
        self._window = window

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None

    def _unbind(self) -> None:
        widget = self._widget
        if self._enter_binding is not None:
            widget.unbind("<Enter>", self._enter_binding)
        if self._leave_binding is not None:
            widget.unbind("<Leave>", self._leave_binding)
        if self._press_binding is not None:
            widget.unbind("<ButtonPress>", self._press_binding)
        if self._focus_binding is not None:
            widget.unbind("<FocusOut>", self._focus_binding)
        if self._destroy_binding is not None:
            widget.unbind("<Destroy>", self._destroy_binding)

    def detach(self) -> None:
        """Remove the tooltip bindings from the widget."""

        self._cancel()
        self._unbind()


def attach_tooltip(
    widget: tk.Widget,
    text: str,
    *,
    delay: int = 400,
    wraplength: int = 280,
) -> None:
    """Attach a tooltip with *text* to the given Tk *widget*."""

    if not isinstance(widget, tk.Widget):  # pragma: no cover - defensive
        return

    tooltip = _Tooltip(widget, text, delay=delay, wraplength=wraplength)
    setattr(widget, "_ocarina_tooltip", tooltip)
