"""Custom (themed) menubar implementation.

This replaces the native OS menubar so we can apply full foreground / background
colors to the top-level menu *labels* consistently across platforms.

Design goals (SRP):
 - Only responsible for rendering clickable top-level items and posting the
   corresponding ``tk.Menu`` dropdowns.
 - Keeps all theming concerns delegated to ttk Styles configured elsewhere.
 - Avoids platform specific owner-draw hacks; pure Tk/ttk only.

Limitations / Future work:
 - Keyboard navigation (Alt/Arrow traversal) is minimal; can be extended later.
 - Accessibility / focus rings not custom drawn yet.
 - Does not (yet) mirror native accelerators in the label text styling.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple

__all__ = ["CustomMenuBar"]


class CustomMenuBar(tk.Frame):
    """A frame hosting themed labels that behave like a menu bar.

    Each label posts the associated ``tk.Menu`` when clicked. We *do not* call
    ``master.config(menu=...)`` so the native menubar is suppressed and the
    frame itself becomes the visual menu strip.
    """

    def __init__(self, master: tk.Misc, menubar: tk.Menu, *, style_prefix: str = "MenuBar") -> None:
        super().__init__(master, class_="MenuBar")
        self._menubar_source = menubar
        self._items: List[Tuple[str, tk.Menu]] = []
        self._labels: List[ttk.Label] = []
        self._posted: tk.Menu | None = None
        self._style_prefix = style_prefix
        self._build_from_menu(menubar)
        self._bind_dismiss_events()

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def _build_from_menu(self, menubar: tk.Menu) -> None:
        try:
            end_index = menubar.index("end")
        except tk.TclError:
            end_index = None
        if end_index is None:
            return
        for i in range(end_index + 1):
            try:
                if menubar.type(i) != "cascade":
                    continue
            except tk.TclError:
                continue
            try:
                label = menubar.entrycget(i, "label")
                submenu_path = menubar.entrycget(i, "menu")
                submenu = menubar.nametowidget(submenu_path)
            except tk.TclError:
                continue
            if not isinstance(submenu, tk.Menu):  # defensive
                continue
            self._items.append((label, submenu))
            lbl = ttk.Label(
                self,
                text=label,
                style=f"{self._style_prefix}.TLabel",
                padding=(10, 4),
                cursor="hand2",
            )
            lbl.bind("<Button-1>", lambda e, m=submenu, w=lbl: self._open_menu(w, m))
            lbl.bind("<Enter>", lambda e, m=submenu, w=lbl: self._maybe_switch_menu(w, m))
            lbl.pack(side="left", padx=(0, 1))
            self._labels.append(lbl)

    def _bind_dismiss_events(self) -> None:
        # Escape closes an open dropdown.
        try:
            self.bind_all("<Escape>", self._close_posted_menu, add="+")
        except tk.TclError:
            pass
        # Clicking anywhere else should close the menu. We bind on the toplevel.
        toplevel = self.winfo_toplevel()
        try:
            toplevel.bind("<Button-1>", self._close_posted_menu, add="+")
        except tk.TclError:
            pass

    # ---------------------------------------------------------------------
    # Dropdown handling
    # ---------------------------------------------------------------------
    def _open_menu(self, widget: tk.Widget, menu: tk.Menu) -> None:
        if self._posted is menu:
            # Toggle off if same menu clicked again.
            self._close_posted_menu()
            return
        self._close_posted_menu()
        try:
            x = widget.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
        except tk.TclError:
            return
        self._posted = menu
        try:
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _maybe_switch_menu(self, widget: tk.Widget, menu: tk.Menu) -> None:
        # If a menu is already posted and we hover another label, switch.
        if self._posted is not None and self._posted is not menu:
            self._open_menu(widget, menu)

    def _close_posted_menu(self, *_args) -> None:
        posted = self._posted
        if posted is None:
            return
        self._posted = None
        try:
            posted.unpost()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------------
    # Theming hooks
    # ---------------------------------------------------------------------
    def apply_palette(self, background: str) -> None:
        """Allow caller to adjust container background after a theme switch."""
        try:
            self.configure(background=background)
        except tk.TclError:
            pass

