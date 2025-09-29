"""Dialog helpers for collecting PDF export options from the user."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ocarina_gui.pdf_export.types import PdfExportOptions
from shared.tkinter_geometry import center_window_over_parent


class PdfExportOptionsDialog(tk.Toplevel):
    """Modal dialog prompting for PDF page size and orientation."""

    def __init__(self, master: tk.Widget | None = None) -> None:
        super().__init__(master=master)
        self.title("PDF export options")
        self.transient(master)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._result: Optional[PdfExportOptions] = None

        container = ttk.Frame(self, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        ttk.Label(container, text="Page size:").grid(row=0, column=0, sticky="w")
        self._size_var = tk.StringVar(value="A4")
        size_frame = ttk.Frame(container)
        size_frame.grid(row=1, column=0, sticky="w", pady=(4, 12))
        for idx, size in enumerate(("A4", "A6")):
            ttk.Radiobutton(
                size_frame,
                text=size,
                value=size,
                variable=self._size_var,
                command=self._on_page_option_changed,
            ).grid(row=0, column=idx, padx=(0 if idx == 0 else 12, 0))

        ttk.Label(container, text="Orientation:").grid(row=2, column=0, sticky="w")
        self._orientation_var = tk.StringVar(value="portrait")
        orient_frame = ttk.Frame(container)
        orient_frame.grid(row=3, column=0, sticky="w", pady=(4, 12))
        orientations = ("portrait", "landscape")
        for idx, orientation in enumerate(orientations):
            ttk.Radiobutton(
                orient_frame,
                text=orientation.capitalize(),
                value=orientation,
                variable=self._orientation_var,
                command=self._on_page_option_changed,
            ).grid(row=0, column=idx, padx=(0 if idx == 0 else 12, 0))

        ttk.Label(container, text="Fingering columns:").grid(row=4, column=0, sticky="w")
        columns_frame = ttk.Frame(container)
        columns_frame.grid(row=5, column=0, sticky="w", pady=(4, 12))
        default_columns = PdfExportOptions.default_columns_for(
            self._size_var.get(), self._orientation_var.get()
        )
        self._current_default_columns = default_columns
        self._columns_var = tk.IntVar(value=default_columns)
        self._columns_spin = ttk.Spinbox(
            columns_frame,
            from_=1,
            to=6,
            textvariable=self._columns_var,
            width=6,
        )
        self._columns_spin.grid(row=0, column=0, sticky="w")

        ttk.Label(container, text="Include in PDF:").grid(row=6, column=0, sticky="w")
        sections_frame = ttk.Frame(container)
        sections_frame.grid(row=7, column=0, sticky="w", pady=(4, 12))

        self._include_piano_roll_var = tk.BooleanVar(value=True)
        self._include_staff_var = tk.BooleanVar(value=True)
        self._include_text_var = tk.BooleanVar(value=True)
        self._include_fingerings_var = tk.BooleanVar(value=True)

        section_controls = (
            ("Piano roll", self._include_piano_roll_var),
            ("Staff", self._include_staff_var),
            ("Text", self._include_text_var),
            ("Fingerings", self._include_fingerings_var),
        )
        for index, (label, variable) in enumerate(section_controls):
            row, column = divmod(index, 2)
            ttk.Checkbutton(
                sections_frame,
                text=label,
                variable=variable,
            ).grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 12 if column == 0 else 0),
                pady=(0, 4 if row == 0 else 0),
            )

        button_frame = ttk.Frame(container)
        button_frame.grid(row=8, column=0, sticky="e")
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(button_frame, text="Export", command=self._on_accept).grid(
            row=0, column=1
        )

        self.bind("<Return>", lambda _event: self._on_accept())
        self.bind("<Escape>", lambda _event: self._on_cancel())

        center_window_over_parent(self, master)

    def _on_accept(self) -> None:
        size = self._size_var.get().strip().upper()
        orientation = self._orientation_var.get().strip().lower()
        columns = max(1, int(self._columns_var.get() or 1))
        self._result = PdfExportOptions(
            page_size=size,
            orientation=orientation,
            columns=columns,
            include_piano_roll=self._include_piano_roll_var.get(),
            include_staff=self._include_staff_var.get(),
            include_text=self._include_text_var.get(),
            include_fingerings=self._include_fingerings_var.get(),
        )
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    def _on_page_option_changed(self) -> None:
        default_columns = PdfExportOptions.default_columns_for(
            self._size_var.get(), self._orientation_var.get()
        )
        if self._columns_var.get() == self._current_default_columns:
            self._columns_var.set(default_columns)
        self._current_default_columns = default_columns

    def result(self) -> Optional[PdfExportOptions]:
        return self._result


def ask_pdf_export_options(master: tk.Widget | None = None) -> Optional[PdfExportOptions]:
    """Show the modal dialog and return the chosen PDF export options."""

    dialog = PdfExportOptionsDialog(master)
    dialog.wait_window()
    return dialog.result()


__all__ = ["ask_pdf_export_options", "PdfExportOptionsDialog"]
