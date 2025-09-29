"""Grid widget that displays all configured fingerings."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Mapping, Optional, Sequence

from .library import get_current_instrument, register_instrument_listener
from .specs import InstrumentSpec, collect_instrument_note_names, parse_note_name_safe
from .view import FingeringView


__all__ = ["calculate_grid_columns", "FingeringGridView"]


def calculate_grid_columns(
    available_width: int,
    tile_width: int,
    padding: int,
    *,
    min_columns: int = 1,
) -> int:
    """Return the number of columns that fit inside ``available_width``."""

    min_columns = max(1, int(min_columns))
    tile_width = max(1, int(tile_width))
    padding = max(0, int(padding))

    if available_width <= 0:
        return min_columns

    per_tile = tile_width + (padding * 2)
    if per_tile <= 0:
        return min_columns

    columns = max(1, available_width // per_tile)
    return max(min_columns, columns)


class FingeringGridView(ttk.Frame):
    """Scrollable grid of fingering views for each configured note."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        columns: Optional[int] = None,
        scale: float = 1.0,
        padding: int = 8,
        view_factory: Optional[Callable[[tk.Misc, float], FingeringView]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._auto_columns = columns is None
        self._requested_columns = max(1, int(columns)) if columns is not None else 1
        self._column_count = 0
        self._available_width = 0
        self._scale = max(0.1, float(scale))
        self._padding = max(0, int(padding))
        self._view_factory = view_factory or (
            lambda parent, scale: FingeringView(parent, scale=scale)
        )
        self._note_order: tuple[str, ...] = ()
        self._tiles: Dict[str, FingeringView] = {}
        self._empty_label: Optional[ttk.Label] = None
        self._unsubscribe = register_instrument_listener(self._on_instrument_changed)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._yscroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._yscroll.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=self._yscroll.set)

        self._inner = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self.refresh()

    # ------------------------------------------------------------------
    def destroy(self) -> None:  # type: ignore[override]
        try:
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None
        finally:
            super().destroy()

    # ------------------------------------------------------------------
    def _on_inner_configure(self, _event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        width = int(getattr(event, "width", 0))
        if width > 0:
            self._available_width = width
        self._canvas.itemconfigure(self._canvas_window, width=event.width)
        self._update_layout()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        instrument = get_current_instrument()
        note_names = collect_instrument_note_names(instrument)
        midi_map = {note: parse_note_name_safe(note) for note in note_names}
        self.set_notes(note_names, midi_map)

    def set_notes(
        self,
        notes: Sequence[str],
        midi_map: Mapping[str, Optional[int]] | None = None,
    ) -> None:
        unique_notes = list(dict.fromkeys(notes))
        if midi_map is None:
            midi_map = {note: parse_note_name_safe(note) for note in unique_notes}

        order = tuple(unique_notes)
        if order != self._note_order:
            self._rebuild(order, midi_map)
        else:
            self._update_tiles(midi_map)

    # ------------------------------------------------------------------
    def _rebuild(
        self, order: tuple[str, ...], midi_map: Mapping[str, Optional[int]]
    ) -> None:
        for view in self._tiles.values():
            view.destroy()
        self._tiles.clear()
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

        self._note_order = order

        if not order:
            label = ttk.Label(self._inner, text="No note mappings configured")
            label.grid(row=0, column=0, padx=self._padding, pady=self._padding, sticky="w")
            self._empty_label = label
            self._column_count = 0
            self._canvas.yview_moveto(0.0)
            return

        for note in order:
            view = self._view_factory(self._inner, self._scale)
            self._tiles[note] = view

        target_columns = self._resolve_column_target(len(order))
        self._arrange_tiles(target_columns)
        self._update_tiles(midi_map)
        self._canvas.yview_moveto(0.0)

    def _update_tiles(self, midi_map: Mapping[str, Optional[int]]) -> None:
        for note, view in self._tiles.items():
            midi = midi_map.get(note)
            view.show_fingering(note, midi)

    # ------------------------------------------------------------------
    def _on_instrument_changed(self, _instrument: InstrumentSpec) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    def _resolve_column_target(self, note_count: int) -> int:
        if note_count <= 0:
            return 1
        if not self._auto_columns:
            return min(self._requested_columns, note_count)

        available = self._available_width
        if available <= 0:
            available = max(self._canvas.winfo_width(), self._inner.winfo_width())

        tile_width = self._estimate_tile_width()
        columns = calculate_grid_columns(
            available,
            tile_width,
            self._padding,
            min_columns=1,
        )
        return max(1, min(columns, note_count))

    def _estimate_tile_width(self) -> int:
        instrument = get_current_instrument()
        width = int(round(float(instrument.canvas_size[0]) * self._scale))
        return max(1, width)

    def _arrange_tiles(self, column_count: int) -> None:
        column_count = max(1, column_count)
        for view in self._tiles.values():
            view.grid_forget()

        for index, note in enumerate(self._note_order):
            view = self._tiles[note]
            row, column = divmod(index, column_count)
            view.grid(
                row=row,
                column=column,
                padx=self._padding,
                pady=self._padding,
                sticky="n",
            )

        max_columns = max(self._column_count, column_count)
        for column in range(max_columns):
            weight = 1 if column < column_count else 0
            self._inner.grid_columnconfigure(column, weight=weight)

        self._column_count = column_count

    def _update_layout(self) -> None:
        if not self._note_order:
            return
        target = self._resolve_column_target(len(self._note_order))
        if target != self._column_count:
            self._arrange_tiles(target)
