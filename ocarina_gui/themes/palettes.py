"""Palette dataclasses used throughout the theming system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PianoRollPalette:
    """Color palette for the piano roll widget."""

    background: str
    natural_row_fill: str
    accidental_row_fill: str
    grid_line: str
    measure_line: str
    measure_number_text: str
    note_fill_sharp: str
    note_fill_natural: str
    note_outline: str
    note_label_text: str
    placeholder_text: str
    header_text: str
    highlight_fill: str
    loop_start_line: str
    loop_end_line: str
    cursor_primary: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PianoRollPalette":
        return cls(
            background=str(data["background"]),
            natural_row_fill=str(data.get("natural_row_fill", data["background"])),
            accidental_row_fill=str(data.get("accidental_row_fill", data["background"])),
            grid_line=str(data["grid_line"]),
            measure_line=str(data.get("measure_line", data["grid_line"])),
            measure_number_text=str(
                data.get(
                    "measure_number_text",
                    data.get("measure_line", data["grid_line"]),
                )
            ),
            note_fill_sharp=str(data["note_fill_sharp"]),
            note_fill_natural=str(data["note_fill_natural"]),
            note_outline=str(data["note_outline"]),
            note_label_text=str(data["note_label_text"]),
            placeholder_text=str(data["placeholder_text"]),
            header_text=str(data.get("header_text", data["placeholder_text"])),
            highlight_fill=str(data["highlight_fill"]),
            loop_start_line=str(data.get("loop_start_line", data["note_outline"])),
            loop_end_line=str(data.get("loop_end_line", data["note_fill_sharp"])),
            cursor_primary=str(
                data.get(
                    "cursor_primary",
                    data.get("note_outline", data.get("note_fill", data["note_fill_natural"])),
                )
            ),
        )


@dataclass(frozen=True)
class StaffPalette:
    """Color palette for the treble staff widget."""

    background: str
    outline: str
    staff_line: str
    measure_line: str
    measure_number_text: str
    accidental_text: str
    note_fill: str
    note_outline: str
    header_text: str
    cursor_primary: str
    cursor_secondary: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaffPalette":
        return cls(
            background=str(data["background"]),
            outline=str(data["outline"]),
            staff_line=str(data["staff_line"]),
            measure_line=str(data["measure_line"]),
            measure_number_text=str(
                data.get("measure_number_text", data["measure_line"])
            ),
            accidental_text=str(data["accidental_text"]),
            note_fill=str(data["note_fill"]),
            note_outline=str(data.get("note_outline", data["note_fill"])),
            header_text=str(data["header_text"]),
            cursor_primary=str(
                data.get("cursor_primary", data.get("note_outline", data["note_fill"]))
            ),
            cursor_secondary=str(data.get("cursor_secondary", data["measure_line"])),
        )


@dataclass(frozen=True)
class ListboxPalette:
    """Color palette for classic Tk listboxes."""

    background: str
    foreground: str
    select_background: str
    select_foreground: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ListboxPalette":
        return cls(
            background=str(data["background"]),
            foreground=str(data["foreground"]),
            select_background=str(data.get("select_background", data["background"])),
            select_foreground=str(data.get("select_foreground", data["foreground"])),
        )


@dataclass(frozen=True)
class TablePalette:
    """Color palette for table-like ttk widgets such as :class:`Treeview`."""

    background: str
    foreground: str
    heading_background: str
    heading_foreground: str
    row_stripe: str
    selection_background: str
    selection_foreground: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TablePalette":
        if not data:
            return cls(
                background="#ffffff",
                foreground="#000000",
                heading_background="#f0f0f0",
                heading_foreground="#000000",
                row_stripe="#ffffff",
                selection_background="#cde4ff",
                selection_foreground="#000000",
            )
        background = str(data["background"])
        foreground = str(data["foreground"])
        row_stripe = str(data.get("row_stripe", background))
        return cls(
            background=background,
            foreground=foreground,
            heading_background=str(data.get("heading_background", background)),
            heading_foreground=str(data.get("heading_foreground", foreground)),
            row_stripe=row_stripe,
            selection_background=str(data.get("selection_background", row_stripe)),
            selection_foreground=str(data.get("selection_foreground", foreground)),
        )


@dataclass(frozen=True)
class LayoutEditorPalette:
    """Color configuration for the instrument layout editor canvases."""

    workspace_background: str
    instrument_surface: str
    instrument_outline: str
    hole_outline: str
    hole_fill: str
    windway_fill: str
    windway_outline: str
    covered_fill: str
    grid_line: str
    selection_outline: str
    handle_fill: str
    handle_outline: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LayoutEditorPalette":
        return cls(
            workspace_background=str(data.get("workspace_background", "#f7f7f7")),
            instrument_surface=str(data.get("instrument_surface", "#ffffff")),
            instrument_outline=str(data.get("instrument_outline", "#4f4f4f")),
            hole_outline=str(data.get("hole_outline", "#4f4f4f")),
            hole_fill=str(data.get("hole_fill", data.get("instrument_surface", "#ffffff"))),
            windway_fill=str(data.get("windway_fill", "#e9ecef")),
            windway_outline=str(data.get("windway_outline", data.get("hole_outline", "#4f4f4f"))),
            covered_fill=str(data.get("covered_fill", "#111111")),
            grid_line=str(data.get("grid_line", "#e1e1e1")),
            selection_outline=str(data.get("selection_outline", "#ff8800")),
            handle_fill=str(data.get("handle_fill", "#ffffff")),
            handle_outline=str(data.get("handle_outline", "#2c7be5")),
        )


@dataclass(frozen=True)
class ThemePalette:
    """Collection of colors used throughout the application widgets."""

    window_background: str
    text_primary: str
    text_muted: str
    text_cursor: str
    piano_roll: PianoRollPalette
    staff: StaffPalette
    listbox: ListboxPalette
    table: TablePalette
    layout_editor: LayoutEditorPalette

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ThemePalette":
        return cls(
            window_background=str(data["window_background"]),
            text_primary=str(data["text_primary"]),
            text_muted=str(data["text_muted"]),
            text_cursor=str(data.get("text_cursor", data["text_primary"])),
            piano_roll=PianoRollPalette.from_dict(data["piano_roll"]),
            staff=StaffPalette.from_dict(data["staff"]),
            listbox=ListboxPalette.from_dict(data["listbox"]),
            table=TablePalette.from_dict(data.get("table", {})),
            layout_editor=LayoutEditorPalette.from_dict(data.get("layout_editor", {})),
        )


__all__ = [
    "ListboxPalette",
    "PianoRollPalette",
    "StaffPalette",
    "TablePalette",
    "LayoutEditorPalette",
    "ThemePalette",
]
