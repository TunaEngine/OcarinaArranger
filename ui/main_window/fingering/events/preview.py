from __future__ import annotations

from .base import FingeringEventBaseMixin, logger


class FingeringPreviewEventsMixin(FingeringEventBaseMixin):
    """Event handlers for the fingering preview canvas."""

    def _on_fingering_preview_hole_click(self, hole_index: int) -> None:
        if not self._fingering_edit_mode:
            return

        note = self._fingering_last_selected_note
        if not note:
            return

        logger.debug(
            "Fingering preview hole click",
            extra={
                "clicked_note": note,
                "hole_index": hole_index,
            },
        )
        self._cycle_fingering_state(note, hole_index)

    def _on_fingering_preview_windway_click(self, windway_index: int) -> None:
        if not self._fingering_edit_mode:
            return

        note = self._fingering_last_selected_note
        if not note:
            return

        viewmodel = self._fingering_edit_vm
        hole_count = len(viewmodel.state.holes) if viewmodel is not None else 0

        logger.debug(
            "Fingering preview windway click",
            extra={
                "clicked_note": note,
                "windway_index": windway_index,
                "hole_count": hole_count,
            },
        )
        self._cycle_fingering_state(note, hole_count + windway_index)
