"""File dialog adapters decoupling UI logic from Tk implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from ocarina_tools.parts import MusicXmlPartInfo


class FileDialogAdapter(Protocol):
    """Interface for selecting files via a GUI or headless mechanism."""

    def ask_open_path(self) -> str | None:
        """Return a path to open or ``None`` if the user cancelled."""

    def ask_save_path(self, suggested_name: str) -> str | None:
        """Return the destination path or ``None`` if the user cancelled."""

    def ask_open_project_path(self) -> str | None:
        """Return a project archive to open or ``None`` if cancelled."""

    def ask_save_project_path(self, suggested_name: str) -> str | None:
        """Return a project archive destination or ``None`` if cancelled."""

    def ask_open_gp_preset_path(self) -> str | None:
        """Return a GP preset path to open or ``None`` if cancelled."""

    def ask_save_gp_preset_path(self, suggested_name: str) -> str | None:
        """Return a GP preset destination or ``None`` if cancelled."""

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> Sequence[str] | None:
        """Return the selected part identifiers or ``None`` if cancelled."""


@dataclass(slots=True)
class TkFileDialogAdapter:
    """Tk-backed dialog adapter using :mod:`tkinter.filedialog`."""

    title_open: str = "Select MusicXML, MXL, or MIDI file"
    title_save: str = "Save MusicXML as..."
    title_open_project: str = "Open Ocarina Arranger Project"
    title_save_project: str = "Save Project As..."
    title_open_gp_preset: str = "Import GP Arranger Preset"
    title_save_gp_preset: str = "Export GP Arranger Preset"

    def ask_open_path(self) -> str | None:
        from tkinter import filedialog

        return filedialog.askopenfilename(
            title=self.title_open,
            filetypes=[
                (
                    "MusicXML/MXL/MIDI",
                    "*.musicxml *.xml *.mxl *.mxl.zip *.mid *.midi",
                ),
                ("All files", "*.*"),
            ],
        )

    def ask_save_path(self, suggested_name: str) -> str | None:
        from tkinter import filedialog

        return filedialog.asksaveasfilename(
            title=self.title_save,
            defaultextension=".musicxml",
            initialfile=suggested_name,
            filetypes=[("MusicXML", "*.musicxml")],
        )

    def ask_open_project_path(self) -> str | None:
        from tkinter import filedialog

        return filedialog.askopenfilename(
            title=self.title_open_project,
            filetypes=[("Ocarina Project", "*.ocarina"), ("All files", "*.*")],
        )

    def ask_save_project_path(self, suggested_name: str) -> str | None:
        from tkinter import filedialog

        return filedialog.asksaveasfilename(
            title=self.title_save_project,
            defaultextension=".ocarina",
            initialfile=suggested_name,
            filetypes=[("Ocarina Project", "*.ocarina")],
        )

    def ask_open_gp_preset_path(self) -> str | None:
        from tkinter import filedialog

        return filedialog.askopenfilename(
            title=self.title_open_gp_preset,
            filetypes=[
                ("GP Arranger Preset", "*.gp-preset *.gp.json"),
                ("JSON", "*.json"),
                ("All files", "*.*"),
            ],
        )

    def ask_save_gp_preset_path(self, suggested_name: str) -> str | None:
        from tkinter import filedialog

        return filedialog.asksaveasfilename(
            title=self.title_save_gp_preset,
            defaultextension=".gp.json",
            initialfile=suggested_name,
            filetypes=[
                ("GP Arranger Preset", "*.gp.json"),
                ("JSON", "*.json"),
            ],
        )

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> Sequence[str] | None:
        from ui.dialogs.part_selection import ask_part_selection

        return ask_part_selection(parts=parts, preselected=preselected)


__all__ = ["FileDialogAdapter", "TkFileDialogAdapter"]
