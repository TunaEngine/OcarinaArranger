"""View-model powering the instrument layout editor UI."""

from __future__ import annotations

from typing import Dict, Sequence

from ocarina_gui.fingering import InstrumentSpec

from ._appearance import LayoutAppearanceMixin
from ._hole_management import HoleManagementMixin
from ._instrument_management import InstrumentManagementMixin
from ._note_management import NoteManagementMixin
from ._selection import SelectionMixin
from ._windway_management import WindwayManagementMixin
from .models import InstrumentLayoutState


class InstrumentLayoutEditorViewModel(
    NoteManagementMixin,
    HoleManagementMixin,
    WindwayManagementMixin,
    SelectionMixin,
    LayoutAppearanceMixin,
    InstrumentManagementMixin,
):
    """Pure state container for the layout editor widgets."""

    def __init__(self, instruments: Sequence[InstrumentSpec]) -> None:
        if not instruments:
            raise ValueError("At least one instrument specification is required")

        self._order = [instrument.instrument_id for instrument in instruments]
        self._states: Dict[str, InstrumentLayoutState] = {
            instrument.instrument_id: self._build_state(instrument)
            for instrument in instruments
        }
        self._current_id = self._order[0]
        self.state = self._states[self._current_id]


__all__ = ["InstrumentLayoutEditorViewModel"]
