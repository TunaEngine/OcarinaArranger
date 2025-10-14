"""Dialogs for selecting fingering instruments."""

from __future__ import annotations

import tkinter as tk

from tkinter import simpledialog, ttk
from typing import Optional, Sequence, Tuple

from .themes import apply_theme_to_toplevel

Choice = Tuple[str, str]

__all__ = ["prompt_for_instrument_choice"]


class _InstrumentSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, choices: Sequence[Choice], *, title: str) -> None:
        if not choices:
            raise ValueError("At least one instrument choice is required")
        self._choices: Tuple[Choice, ...] = tuple(choices)
        self._labels = [self._format_label(identifier, name) for identifier, name in self._choices]
        self._selection_index: Optional[int] = None
        super().__init__(parent, title)

    @staticmethod
    def _format_label(identifier: str, name: str) -> str:
        clean_name = str(name).strip() or str(identifier)
        clean_id = str(identifier).strip()
        if not clean_id or clean_id.lower() == clean_name.lower():
            return clean_name
        return f"{clean_name} ({clean_id})"

    def body(self, master: tk.Misc) -> tk.Widget:
        palette = apply_theme_to_toplevel(self)
        try:
            master.configure(background=palette.window_background)
        except Exception:  # pragma: no cover - defensive
            pass

        ttk.Label(master, text="Copy fingerings from:").grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 2)
        )

        listbox = tk.Listbox(
            master,
            height=min(12, max(4, len(self._labels))),
            exportselection=False,
        )
        listbox.grid(row=1, column=0, sticky="nsew", padx=4)
        listbox.bind("<<ListboxSelect>>", self._on_select)
        listbox.bind("<Double-Button-1>", self._on_double_click)
        master.grid_rowconfigure(1, weight=1)
        master.grid_columnconfigure(0, weight=1)

        for index, label in enumerate(self._labels):
            listbox.insert(tk.END, label)

        listbox.selection_set(0)
        listbox.activate(0)
        self._selection_index = 0

        self._listbox = listbox
        return listbox

    def buttonbox(self) -> None:  # pragma: no cover - Tk boilerplate
        box = ttk.Frame(self, style="Panel.TFrame")
        box.pack(fill="x", padx=4, pady=(0, 4))

        controls = ttk.Frame(box, style="Panel.TFrame")
        controls.pack(side="right")

        ok_button = ttk.Button(controls, text="OK", command=self.ok)
        ok_button.pack(side="left", padx=(0, 4))
        cancel_button = ttk.Button(controls, text="Cancel", command=self.cancel)
        cancel_button.pack(side="left")

        self.bind("<Return>", lambda _event: self.ok())
        self.bind("<Escape>", lambda _event: self.cancel())

    def validate(self) -> bool:
        return self._selection_index is not None

    def apply(self) -> None:
        if self._selection_index is None:
            self.result = None
            return
        identifier, _name = self._choices[self._selection_index]
        self.result = identifier

    # ------------------------------------------------------------------
    def _on_select(self, _event: tk.Event) -> None:
        selection = self._listbox.curselection()
        if not selection:
            self._selection_index = None
            return
        self._selection_index = selection[0]

    def _on_double_click(self, _event: tk.Event) -> None:
        if self._selection_index is not None:
            self.ok()


def prompt_for_instrument_choice(
    parent: tk.Misc,
    choices: Sequence[Choice],
    *,
    title: str = "Copy Fingerings",
) -> Optional[str]:
    """Prompt the user to choose an instrument to copy fingerings from."""

    if not choices:
        return None
    dialog = _InstrumentSelectionDialog(parent, choices, title=title)
    result = getattr(dialog, "result", None)
    return str(result) if isinstance(result, str) and result else None

