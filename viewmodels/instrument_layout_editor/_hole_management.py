"""Hole editing helpers for the instrument layout editor view-model."""

from __future__ import annotations

from typing import List, Optional, Sequence

from .models import EditableHole, InstrumentLayoutState, Selection, SelectionKind
from .note_patterns import normalize_pattern, sync_note_map_length


class HoleManagementMixin:
    """Encapsulate add/remove/reorder logic for tone holes."""

    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    def add_hole(
        self,
        identifier: Optional[str] = None,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        radius: Optional[float] = None,
    ) -> EditableHole:
        state = self.state
        previous_holes = len(state.holes)
        windway_count = len(state.windways)
        hole_id = self._normalize_hole_identifier(identifier, state)
        hole_radius = float(radius) if radius is not None else 8.0
        hole_x = float(x) if x is not None else state.canvas_width / 2.0
        hole_y = float(y) if y is not None else state.canvas_height / 2.0

        new_hole = EditableHole(identifier=hole_id, x=hole_x, y=hole_y, radius=hole_radius)
        state.holes.append(new_hole)
        sync_note_map_length(
            state,
            previous_hole_count=previous_holes,
            previous_windway_count=windway_count,
        )
        state.selection = Selection(kind=SelectionKind.HOLE, index=len(state.holes) - 1)
        state.dirty = True
        return new_hole

    def remove_hole(self, index: int) -> None:
        state = self.state
        if not (0 <= index < len(state.holes)):
            raise IndexError(f"Hole index {index} is out of range")

        previous_holes = len(state.holes)
        state.holes.pop(index)
        sync_note_map_length(
            state,
            removed_offset=index,
            previous_hole_count=previous_holes,
            previous_windway_count=len(state.windways),
        )
        state.dirty = True

        selection = state.selection
        if selection is None or selection.kind != SelectionKind.HOLE:
            return

        if not state.holes:
            state.selection = None
            return

        if selection.index > index:
            state.selection = Selection(kind=SelectionKind.HOLE, index=selection.index - 1)
        else:
            new_index = min(selection.index, len(state.holes) - 1)
            state.selection = Selection(kind=SelectionKind.HOLE, index=new_index)

    def reorder_holes(self, order: Sequence[int]) -> None:
        state = self.state
        hole_count = len(state.holes)
        if hole_count <= 1:
            return

        normalized: List[int] = []
        for raw in order:
            try:
                index = int(raw)
            except (TypeError, ValueError):
                continue
            if 0 <= index < hole_count and index not in normalized:
                normalized.append(index)

        for index in range(hole_count):
            if index not in normalized:
                normalized.append(index)

        if normalized == list(range(hole_count)):
            return

        original_holes = list(state.holes)
        state.holes = [original_holes[index] for index in normalized]

        selection = state.selection
        if selection and selection.kind == SelectionKind.HOLE:
            selected_identifier = original_holes[selection.index].identifier
            for new_index, hole in enumerate(state.holes):
                if hole.identifier == selected_identifier:
                    state.selection = Selection(kind=SelectionKind.HOLE, index=new_index)
                    break
            else:
                state.selection = None

        windway_count = len(state.windways)
        for note, pattern in list(state.note_map.items()):
            normalized_pattern = normalize_pattern(pattern, hole_count, windway_count)
            hole_values = [normalized_pattern[index] for index in normalized]
            windway_values = normalized_pattern[hole_count : hole_count + windway_count]
            state.note_map[note] = hole_values + windway_values

        state.dirty = True

    def update_hole_identifier(self, index: int, identifier: str) -> None:
        state = self.state
        if not (0 <= index < len(state.holes)):
            raise IndexError(f"Hole index {index} is out of range")

        new_identifier = self._normalize_hole_identifier(
            identifier,
            state,
            allow_existing_index=index,
            allow_generate=False,
        )
        hole = state.holes[index]
        if hole.identifier == new_identifier:
            return
        hole.identifier = new_identifier
        state.dirty = True

    # ------------------------------------------------------------------
    def _normalize_hole_identifier(
        self,
        identifier: Optional[str],
        state: InstrumentLayoutState,
        *,
        allow_existing_index: Optional[int] = None,
        allow_generate: bool = True,
    ) -> str:
        text = str(identifier).strip() if identifier is not None else ""
        if not text:
            if not allow_generate:
                raise ValueError("Hole description cannot be empty")
            base = "hole"
            suffix = len(state.holes) + 1
            existing = {hole.identifier for hole in state.holes}
            if allow_existing_index is not None and 0 <= allow_existing_index < len(state.holes):
                existing.remove(state.holes[allow_existing_index].identifier)
            candidate = f"{base}_{suffix}"
            while candidate in existing:
                suffix += 1
                candidate = f"{base}_{suffix}"
            return candidate

        duplicates = {
            idx
            for idx, hole in enumerate(state.holes)
            if hole.identifier == text and idx != allow_existing_index
        }
        if duplicates:
            raise ValueError(f"Hole identifier '{text}' already exists")
        return text
