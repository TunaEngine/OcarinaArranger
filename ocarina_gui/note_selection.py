"""Reusable dialog helpers for selecting fingering note names."""

from __future__ import annotations

import tkinter as tk
from contextlib import suppress

from tkinter import simpledialog, ttk
from typing import Iterable, Optional, Sequence, Set

from .themes import apply_theme_to_toplevel


class _NoteSelectionDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent: tk.Misc,
        choices: Sequence[str],
        disabled: Iterable[str] = (),
        *,
        title: str,
    ) -> None:
        self._choices = list(choices)
        self._disabled: Set[str] = {name.strip() for name in disabled if name}
        self._selection: Optional[str] = None
        self._error_var: tk.StringVar | None = None
        self._listbox: tk.Listbox | None = None
        super().__init__(parent, title)

    def body(self, master: tk.Misc) -> tk.Widget:
        palette = apply_theme_to_toplevel(self)
        with suppress(tk.TclError):
            master.configure(background=palette.window_background)

        ttk.Label(master, text="Select a note:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 2))

        listbox = tk.Listbox(master, height=min(12, max(4, len(self._choices))), exportselection=False)
        listbox.grid(row=1, column=0, sticky="nsew", padx=4)
        listbox.bind("<<ListboxSelect>>", self._on_select)
        listbox.bind("<Double-Button-1>", self._on_double_click)
        master.grid_rowconfigure(1, weight=1)
        master.grid_columnconfigure(0, weight=1)

        first_available = None
        for index, name in enumerate(self._choices):
            listbox.insert(tk.END, name)
            if name in self._disabled:
                try:
                    listbox.itemconfig(index, foreground="#888888")
                except tk.TclError:
                    pass
            elif first_available is None:
                first_available = index

        if first_available is not None:
            listbox.selection_set(first_available)
            listbox.activate(first_available)
            self._selection = self._choices[first_available]

        error_var = tk.StringVar(master=master, value="")
        ttk.Label(master, textvariable=error_var, foreground="#b00000").grid(
            row=2, column=0, sticky="w", padx=4, pady=(2, 4)
        )

        self._error_var = error_var
        self._listbox = listbox
        return listbox

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        box.pack(fill="x", padx=4, pady=(0, 4))

        controls = ttk.Frame(box)
        controls.pack(side="right")

        ok_button = ttk.Button(controls, text="OK", command=self.ok)
        ok_button.pack(side="left", padx=(0, 4))
        cancel_button = ttk.Button(controls, text="Cancel", command=self.cancel)
        cancel_button.pack(side="left")

        self.bind("<Return>", lambda _event: self.ok())
        self.bind("<Escape>", lambda _event: self.cancel())

    def validate(self) -> bool:
        if self._selection is None or self._selection in self._disabled:
            if self._error_var is not None:
                self._error_var.set("Select a note that is not already added.")
            return False
        return True

    def apply(self) -> None:
        self.result = self._selection

    # ------------------------------------------------------------------
    def _on_select(self, _event: tk.Event) -> None:
        listbox = self._listbox
        if listbox is None:
            return
        selection = listbox.curselection()
        if not selection:
            self._selection = None
            return
        index = selection[0]
        choice = self._choices[index]
        if choice in self._disabled:
            listbox.selection_clear(index)
            if self._error_var is not None:
                self._error_var.set("This note already has a fingering.")
            self._selection = None
        else:
            self._selection = choice
            if self._error_var is not None:
                self._error_var.set("")

    def _on_double_click(self, _event: tk.Event) -> None:
        if self._selection is not None and self._selection not in self._disabled:
            self.ok()


def prompt_for_note_name(
    parent: tk.Misc,
    choices: Sequence[str],
    *,
    disabled: Iterable[str] = (),
    title: str = "Add Fingering",
) -> Optional[str]:
    """Show a dialog to pick a fingering note name from ``choices``."""

    dialog = _NoteSelectionDialog(parent, choices, disabled, title=title)
    result = getattr(dialog, "result", None)
    return str(result) if isinstance(result, str) and result else None
