"""Windway editing helpers for the instrument layout editor view-model."""

from __future__ import annotations

from typing import Optional

from .models import EditableWindway, InstrumentLayoutState, Selection, SelectionKind
from .note_patterns import sync_note_map_length


class WindwayManagementMixin:
    """Encapsulate add/remove/update logic for instrument windways."""

    state: InstrumentLayoutState

    # ------------------------------------------------------------------
    def add_windway(
        self,
        identifier: Optional[str] = None,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> EditableWindway:
        state = self.state
        previous_windways = len(state.windways)
        previous_holes = len(state.holes)
        windway_id = self._normalize_windway_identifier(identifier, state)
        windway_width = float(width) if width is not None else 16.0
        windway_height = float(height) if height is not None else 10.0
        center_x = float(x) if x is not None else state.canvas_width / 2.0
        center_y = float(y) if y is not None else state.canvas_height / 2.0

        windway = EditableWindway(
            identifier=windway_id,
            x=center_x,
            y=center_y,
            width=max(1.0, windway_width),
            height=max(1.0, windway_height),
        )
        state.windways.append(windway)
        sync_note_map_length(
            state,
            previous_hole_count=previous_holes,
            previous_windway_count=previous_windways,
        )
        state.selection = Selection(kind=SelectionKind.WINDWAY, index=len(state.windways) - 1)
        state.dirty = True
        return windway

    def remove_windway(self, index: int) -> None:
        state = self.state
        if not (0 <= index < len(state.windways)):
            raise IndexError(f"Windway index {index} is out of range")

        hole_count = len(state.holes)
        previous_windways = len(state.windways)
        state.windways.pop(index)
        sync_note_map_length(
            state,
            removed_offset=hole_count + index,
            previous_hole_count=hole_count,
            previous_windway_count=previous_windways,
        )
        state.dirty = True

        selection = state.selection
        if selection is None or selection.kind != SelectionKind.WINDWAY:
            return

        if not state.windways:
            state.selection = None
            return

        if selection.index > index:
            state.selection = Selection(kind=SelectionKind.WINDWAY, index=selection.index - 1)
        else:
            new_index = min(selection.index, len(state.windways) - 1)
            state.selection = Selection(kind=SelectionKind.WINDWAY, index=new_index)

    def update_windway_identifier(self, index: int, identifier: str) -> None:
        state = self.state
        if not (0 <= index < len(state.windways)):
            raise IndexError(f"Windway index {index} is out of range")

        new_identifier = self._normalize_windway_identifier(
            identifier,
            state,
            allow_existing_index=index,
            allow_generate=False,
        )
        windway = state.windways[index]
        if windway.identifier == new_identifier:
            return
        windway.identifier = new_identifier
        state.dirty = True

    def set_windway_size(self, index: int, width: float, height: float) -> None:
        state = self.state
        if not (0 <= index < len(state.windways)):
            raise IndexError(f"Windway index {index} is out of range")

        windway = state.windways[index]
        new_width = max(1.0, float(width))
        new_height = max(1.0, float(height))
        if windway.width == new_width and windway.height == new_height:
            return
        windway.width = new_width
        windway.height = new_height
        state.dirty = True

    # ------------------------------------------------------------------
    def _normalize_windway_identifier(
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
                raise ValueError("Windway description cannot be empty")
            base = "windway"
            suffix = len(state.windways) + 1
            existing = {
                entry.identifier
                for entry in list(state.windways) + list(state.holes)
            }
            if allow_existing_index is not None and 0 <= allow_existing_index < len(state.windways):
                existing.remove(state.windways[allow_existing_index].identifier)
            candidate = f"{base}_{suffix}"
            while candidate in existing:
                suffix += 1
                candidate = f"{base}_{suffix}"
            return candidate

        duplicates = {
            idx
            for idx, entry in enumerate(state.windways)
            if entry.identifier == text and idx != allow_existing_index
        }
        if duplicates:
            raise ValueError(f"Windway identifier '{text}' already exists")
        if any(hole.identifier == text for hole in state.holes):
            raise ValueError(f"Identifier '{text}' is already used by a hole")
        return text


__all__ = ["WindwayManagementMixin"]
