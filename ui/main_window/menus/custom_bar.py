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

import contextlib
import tkinter as tk

from typing import Dict, List, Tuple

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
        self._labels: List[tk.Label] = []
        self._posted: tk.Menu | None = None
        self._style_prefix = style_prefix
        self._palette: Dict[str, str] = self._resolve_default_palette()
        self._active_label: tk.Label | None = None
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
            lbl = tk.Label(
                self,
                text=label,
                bd=0,
                highlightthickness=0,
                padx=10,
                pady=4,
                cursor="hand2",
                takefocus=False,
            )
            self._style_label(lbl, active=False)
            lbl.bind("<Button-1>", lambda e, m=submenu, w=lbl: self._open_menu(w, m))
            lbl.bind("<Enter>", lambda e, m=submenu, w=lbl: self._maybe_switch_menu(w, m))
            lbl.bind("<Leave>", lambda _e, w=lbl: self._on_label_leave(w))
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
        if isinstance(widget, tk.Label):
            self._set_active_label(widget)
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
        elif isinstance(widget, tk.Label) and self._posted is not None:
            self._set_active_label(widget)

    def _close_posted_menu(self, *_args) -> None:
        posted = self._posted
        if posted is None:
            return
        self._posted = None
        self._set_active_label(None)
        try:
            posted.unpost()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------------
    # Theming hooks
    # ---------------------------------------------------------------------
    def apply_palette(
        self,
        background: str,
        foreground: str,
        active_background: str,
        active_foreground: str,
    ) -> None:
        """Allow caller to adjust container palette after a theme switch."""

        self._palette = {
            "background": background,
            "foreground": foreground,
            "active_background": active_background,
            "active_foreground": active_foreground,
        }

        with contextlib.suppress(tk.TclError):
            self.configure(background=background)
        for label in self._labels:
            self._style_label(label, active=(label is self._active_label))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_default_palette(self) -> Dict[str, str]:
        background = self._lookup_color("background") or "#f0f0f0"
        foreground = self._lookup_color("foreground") or "#000000"
        return {
            "background": background,
            "foreground": foreground,
            "active_background": background,
            "active_foreground": foreground,
        }

    def _lookup_color(self, option: str) -> str:
        try:
            value = str(self.cget(option))
            if value:
                return value
        except tk.TclError:
            pass
        try:
            value = str(self.master.cget(option))
            if value:
                return value
        except Exception:
            pass
        return ""

    def _style_label(self, label: tk.Label, *, active: bool) -> None:
        palette = self._palette
        background = (
            palette["active_background"] if active else palette["background"]
        )
        foreground = (
            palette["active_foreground"] if active else palette["foreground"]
        )
        try:
            label.configure(
                background=background,
                foreground=foreground,
                activebackground=palette["active_background"],
                activeforeground=palette["active_foreground"],
            )
        except tk.TclError:
            with contextlib.suppress(tk.TclError):
                label.configure(background=background, foreground=foreground)

    def _set_active_label(self, label: tk.Label | None) -> None:
        if self._active_label is label:
            return
        previous = self._active_label
        self._active_label = label
        if previous is not None and previous in self._labels:
            self._style_label(previous, active=False)
        if label is not None and label in self._labels:
            self._style_label(label, active=True)

    def _on_label_leave(self, label: tk.Label) -> None:
        if self._posted is None or self._active_label is not label:
            self._style_label(label, active=False)

