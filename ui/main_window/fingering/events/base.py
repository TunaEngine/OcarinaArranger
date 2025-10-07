from __future__ import annotations

import logging
from tkinter import messagebox

logger = logging.getLogger("ui.main_window.fingering.events")


class FingeringEventBaseMixin:
    """Shared helpers for fingering editor event handling."""

    def _cycle_fingering_state(self, note: str, element_index: int) -> None:
        viewmodel = self._fingering_edit_vm
        if viewmodel is None:
            return

        state = viewmodel.state
        hole_count = len(state.holes)
        windway_count = len(state.windways)
        total_count = hole_count + windway_count
        if element_index < 0 or element_index >= total_count:
            logger.debug(
                "Ignoring fingering toggle outside range",
                extra={
                    "fingering_note": note,
                    "element_index": element_index,
                    "hole_count": hole_count,
                    "windway_count": windway_count,
                },
            )
            return

        original_pattern = list(state.note_map.get(note, [0] * total_count))
        if len(original_pattern) < total_count:
            original_pattern = original_pattern + [0] * (total_count - len(original_pattern))
        elif len(original_pattern) > total_count:
            original_pattern = original_pattern[:total_count]

        pattern = list(original_pattern)

        current = int(pattern[element_index]) if element_index < len(pattern) else 0
        if element_index < hole_count:
            if self._half_notes_enabled():
                next_value = (current + 1) % 3
            else:
                next_value = 0 if current >= 2 else 2
            element_kind = "hole"
            element_offset = element_index
        else:
            next_value = 0 if current >= 2 else 2
            element_kind = "windway"
            element_offset = element_index - hole_count
        pattern[element_index] = next_value
        logger.debug(
            "Cycling fingering element",
            extra={
                "fingering_note": note,
                "element_kind": element_kind,
                "element_index": element_offset,
                "absolute_index": element_index,
                "previous_state": current,
                "next_state": next_value,
                "pattern_before": original_pattern,
            },
        )
        try:
            viewmodel.set_note_pattern(note, pattern)
        except ValueError as exc:
            messagebox.showerror("Update fingering", str(exc), parent=self)
            return

        self._apply_fingering_editor_changes(note)
