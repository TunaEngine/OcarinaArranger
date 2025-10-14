"""Dialog for selecting MusicXML parts prior to import."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence

from ocarina_tools.parts import MusicXmlPartInfo
from shared.ttk import ttk
from ocarina_gui.themes import apply_theme_to_toplevel
from shared.tkinter_geometry import center_window_over_parent


class PartSelectionDialog(tk.Toplevel):
    """Modal dialog presenting score parts for single or multiple selection."""

    def __init__(
        self,
        *,
        master: tk.Widget | None,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str] = (),
    ) -> None:
        if master is None:
            master = tk._default_root  # type: ignore[attr-defined]
        super().__init__(master=master)
        self.title("Select score parts")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        apply_theme_to_toplevel(self)

        self._parts = list(parts)
        self._allow_multiple = len(self._parts) > 1
        self._selection: tuple[str, ...] | None = None

        container = ttk.Frame(self, padding=16, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        description = "Select the parts to import:"
        ttk.Label(container, text=description).grid(row=0, column=0, sticky="w")

        tree = ttk.Treeview(
            container,
            columns=("id", "name", "range"),
            show="headings",
            height=min(8, max(3, len(self._parts))),
            selectmode="extended" if self._allow_multiple else "browse",
        )
        tree.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        tree.heading("id", text="ID")
        tree.heading("name", text="Name")
        tree.heading("range", text="Range")
        tree.column("id", width=120, anchor="w")
        tree.column("name", width=180, anchor="w")
        tree.column("range", width=160, anchor="w")

        for part in self._parts:
            range_text = _format_range(part)
            tree.insert(
                "",
                "end",
                iid=part.part_id,
                values=(part.part_id, part.name or "Unnamed", range_text),
            )

        if self._parts:
            default_selection = tuple(preselected) or tuple(
                part.part_id for part in self._parts
            )
            valid_defaults = [
                part_id
                for part_id in default_selection
                if tree.exists(part_id)
            ]
            if not valid_defaults and self._parts:
                valid_defaults = [self._parts[0].part_id]
            tree.selection_set(valid_defaults)
            tree.focus(valid_defaults[0])
            tree.see(valid_defaults[0])

        self._tree = tree

        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

        button_frame = ttk.Frame(container, style="Panel.TFrame")
        button_frame.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))

        self._select_button = ttk.Button(
            button_frame,
            text="Select",
            command=self._on_accept,
        )
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).grid(
            row=0, column=0, padx=(0, 8)
        )
        self._select_button.grid(row=0, column=1)

        self._update_button_state()

        self._tree.bind("<<TreeviewSelect>>", lambda _evt: self._update_button_state())
        self._tree.bind("<Double-1>", lambda _evt: self._on_accept())
        self.bind("<Return>", lambda _evt: self._on_accept())
        self.bind("<Escape>", lambda _evt: self._on_cancel())

        center_window_over_parent(self, master)

    def result(self) -> tuple[str, ...] | None:
        """Return the selected part identifiers, or ``None`` if cancelled."""

        return self._selection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_button_state(self) -> None:
        has_selection = bool(self._tree.selection())
        state = "!disabled" if has_selection else "disabled"
        self._select_button.state([state])

    def _on_accept(self) -> None:
        selected = self._tree.selection()
        if not selected:
            return
        if not self._allow_multiple:
            selected = selected[:1]
        self._selection = tuple(selected)
        self.destroy()

    def _on_cancel(self) -> None:
        self._selection = None
        self.destroy()


def _format_range(part: MusicXmlPartInfo) -> str:
    low = part.min_pitch or ""
    high = part.max_pitch or ""
    if low and high and low != high:
        return f"{low} – {high}"
    return low or high or ""


def ask_part_selection(
    *,
    parts: Sequence[MusicXmlPartInfo],
    preselected: Sequence[str] = (),
    master: tk.Widget | None = None,
) -> tuple[str, ...] | None:
    """Show the selection dialog and return chosen part identifiers."""

    dialog = PartSelectionDialog(master=master, parts=parts, preselected=preselected)
    dialog.wait_window()
    return dialog.result()


__all__ = ["ask_part_selection", "PartSelectionDialog"]
