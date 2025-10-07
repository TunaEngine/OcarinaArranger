"""Grid widget that displays all configured fingerings."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Mapping, Optional, Sequence, Set, Tuple

from .library import get_current_instrument, register_instrument_listener
from .specs import InstrumentSpec, collect_instrument_note_names, parse_note_name_safe
from .view import FingeringView


__all__ = ["calculate_grid_columns", "FingeringGridView"]


_LOGGER = logging.getLogger(__name__)


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
        self._geometry_signature: tuple | None = None
        self._last_patterns: Dict[str, Tuple[int, ...] | None] = {}
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
        self._update_from_instrument(instrument, force_reconcile=True)

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

    # ------------------------------------------------------------------
    def _rebuild(
        self, order: tuple[str, ...], midi_map: Mapping[str, Optional[int]]
    ) -> None:
        created = self._reconcile_tiles(order)
        if created:
            for note in created:
                view = self._tiles.get(note)
                if view is None:
                    continue
                view.show_fingering(note, midi_map.get(note))

    # ------------------------------------------------------------------
    def _on_instrument_changed(self, instrument: InstrumentSpec) -> None:
        self._update_from_instrument(instrument)

    def _instrument_signature(self, instrument: InstrumentSpec) -> tuple:
        return (
            int(instrument.canvas_size[0]),
            int(instrument.canvas_size[1]),
            tuple(
                (
                    round(float(hole.x), 4),
                    round(float(hole.y), 4),
                    round(float(hole.radius), 4),
                )
                for hole in instrument.holes
            ),
            tuple(
                (
                    round(float(windway.x), 4),
                    round(float(windway.y), 4),
                    round(float(windway.width), 4),
                    round(float(windway.height), 4),
                )
                for windway in instrument.windways
            ),
        )

    def _snapshot_patterns(
        self, instrument: InstrumentSpec, order: Sequence[str]
    ) -> Dict[str, Tuple[int, ...] | None]:
        hole_count = len(instrument.holes)
        windway_count = len(instrument.windways)
        total = hole_count + windway_count
        patterns: Dict[str, Tuple[int, ...] | None] = {}

        for note in order:
            raw = instrument.note_map.get(note)
            if raw is None:
                patterns[note] = None
                continue

            values = list(raw)
            if total:
                if len(values) < total:
                    values.extend([0] * (total - len(values)))
                elif len(values) > total:
                    values = values[:total]

            normalized: list[int] = []
            for index, value in enumerate(values[:total]):
                number = int(value)
                if index < hole_count:
                    if number < 0:
                        number = 0
                    elif number > 2:
                        number = 2
                else:
                    number = 0 if number <= 0 else 2
                normalized.append(number)

            patterns[note] = tuple(normalized)

        return patterns

    # ------------------------------------------------------------------
    def _reconcile_tiles(self, order: tuple[str, ...]) -> Set[str]:
        """Ensure the grid tiles match ``order`` and return notes that were created."""

        created_notes: Set[str] = set()

        # Clean up any placeholder label before reconciling real tiles.
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

        existing = dict(self._tiles)
        new_tiles: Dict[str, FingeringView] = {}
        reused = 0
        created = 0

        if not order:
            for view in existing.values():
                view.destroy()
            self._tiles.clear()
            self._note_order = ()
            label = ttk.Label(self._inner, text="No note mappings configured")
            label.grid(row=0, column=0, padx=self._padding, pady=self._padding, sticky="w")
            self._empty_label = label
            self._column_count = 0
            self._canvas.yview_moveto(0.0)
            return created_notes

        for note in order:
            view = existing.pop(note, None)
            if view is None:
                view = self._view_factory(self._inner, self._scale)
                created_notes.add(note)
                created += 1
            else:
                view.grid_forget()
                reused += 1
            new_tiles[note] = view

        destroyed = len(existing)
        for view in existing.values():
            view.destroy()

        self._tiles = new_tiles
        self._note_order = order

        target_columns = self._resolve_column_target(len(order))
        self._arrange_tiles(target_columns)
        self._canvas.yview_moveto(0.0)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Fingering grid reconciled tiles reused=%s created=%s destroyed=%s order_len=%s",
                reused,
                created,
                destroyed,
                len(order),
            )

        return created_notes

    def _update_from_instrument(
        self, instrument: InstrumentSpec, *, force_reconcile: bool = False
    ) -> None:
        note_names = collect_instrument_note_names(instrument)
        order = tuple(dict.fromkeys(note_names))
        midi_map = {note: parse_note_name_safe(note) for note in order}
        geometry_signature = self._instrument_signature(instrument)
        new_patterns = self._snapshot_patterns(instrument, order)

        order_changed = force_reconcile or order != self._note_order
        geometry_changed = force_reconcile or geometry_signature != self._geometry_signature

        created_notes: Set[str] = set()
        if order_changed or geometry_changed:
            created_notes = self._reconcile_tiles(order)

        if geometry_changed:
            notes_to_update: Set[str] = set(order)
        else:
            notes_to_update = {
                note
                for note, pattern in new_patterns.items()
                if force_reconcile or pattern != self._last_patterns.get(note)
            }
            notes_to_update |= created_notes

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Fingering grid update order_changed=%s geometry_changed=%s updated_tiles=%s",
                order_changed,
                geometry_changed,
                len(notes_to_update),
            )

        for note in notes_to_update:
            view = self._tiles.get(note)
            if view is None:
                continue
            midi = midi_map.get(note)
            view.show_fingering(note, midi)

        self._geometry_signature = geometry_signature
        self._last_patterns = new_patterns

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
