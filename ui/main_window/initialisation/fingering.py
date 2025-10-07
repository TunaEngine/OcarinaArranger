from __future__ import annotations

import tkinter as tk
from typing import Dict, Optional, Tuple

from shared.ttk import ttk

from ocarina_gui.fingering import FingeringGridView, FingeringView
from viewmodels.instrument_layout_editor_viewmodel import InstrumentLayoutEditorViewModel


class FingeringInitialisationMixin:
    """Initialise fingering-related attributes and defaults."""

    def _setup_fingering_defaults(self) -> None:
        self._fingering_table_style: str | None = None
        self._fingering_heading_lines: int = 1
        self._fingering_heading_font_name: str | None = None
        self._fingering_heading_base_padding: Tuple[int, int, int, int] | None = None
        self._fingering_edit_mode: bool = False
        self._fingering_edit_vm: InstrumentLayoutEditorViewModel | None = None
        self._fingering_edit_backup: Dict[str, object] | None = None
        self._fingering_edit_button: Optional[ttk.Button] = None
        self._fingering_cancel_button: Optional[ttk.Button] = None
        self._fingering_cancel_pad: Tuple[int, int] | None = None
        self._fingering_remove_button: Optional[ttk.Button] = None
        self._fingering_edit_controls: Optional[ttk.Frame] = None
        self._fingering_ignore_next_select: bool = False
        self._fingering_last_selected_note: Optional[str] = None
        self._fingering_click_guard_note: Optional[str] = None
        self._fingering_column_index: Dict[str, int] = {}
        self._fingering_display_columns_override: list[str] | None = None
        self._fingering_display_columns: tuple[str, ...] = ()
        self._fingering_column_drag_source: str | None = None
        self._fingering_drop_indicator: tk.Widget | None = None
        self._fingering_drop_indicator_color: str | None = None
        self._fingering_drop_target_id: str | None = None
        self._fingering_drop_insert_after: bool = False
        self._fingering_half_notes_enabled: bool = False
        if self._headless:
            self._fingering_allow_half_var = None
        else:
            self._fingering_allow_half_var = tk.BooleanVar(master=self, value=False)
        self._apply_half_note_default(self._selected_instrument_id)


__all__ = ["FingeringInitialisationMixin"]
