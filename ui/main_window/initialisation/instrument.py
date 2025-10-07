from __future__ import annotations

from typing import Dict, List, Optional

from shared.ttk import ttk

from viewmodels.main_viewmodel import MainViewModelState


class InstrumentInitialisationMixin:
    """Prepare instrument-related state during initialisation."""

    def _setup_instrument_attributes(self, state: MainViewModelState) -> None:
        self._instrument_name_by_id: Dict[str, str] = {}
        self._instrument_id_by_name: Dict[str, str] = {}
        self._instrument_display_names: List[str] = []
        self._range_note_options: list[str] = []
        self._convert_instrument_combo: Optional[ttk.Combobox] = None
        self._range_min_combo: Optional[ttk.Combobox] = None
        self._range_max_combo: Optional[ttk.Combobox] = None
        self._suspend_instrument_updates = False
        self._selected_instrument_id = ""
        self._initialize_instrument_state(state)


__all__ = ["InstrumentInitialisationMixin"]
