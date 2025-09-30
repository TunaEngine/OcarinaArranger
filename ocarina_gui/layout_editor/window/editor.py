"""Instrument layout editor window implementation."""

from __future__ import annotations

import copy
from typing import Callable, Dict

import tkinter as tk
from tkinter import ttk

from shared.tkinter_geometry import center_window_over_parent
from viewmodels.instrument_layout_editor_viewmodel import (
    InstrumentLayoutEditorViewModel,
    InstrumentLayoutState,
    SelectionKind,
)

from ..instrument_layout_canvas import InstrumentLayoutCanvas
from .actions import _LayoutEditorActionsMixin
from .config import _LayoutEditorConfigMixin
from .state import _LayoutEditorStateMixin
from .ui import _LayoutEditorUIMixin


class InstrumentLayoutEditor(
    _LayoutEditorConfigMixin,
    _LayoutEditorActionsMixin,
    _LayoutEditorStateMixin,
    _LayoutEditorUIMixin,
    tk.Toplevel,
):
    """Standalone window exposing a WYSIWYG instrument editor."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        viewmodel: InstrumentLayoutEditorViewModel | None = None,
        on_close: Callable[[], None] | None = None,
        on_config_saved: Callable[[Dict[str, object], str], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Instrument Layout Editor")
        self.transient(master)
        self.resizable(True, True)

        self._viewmodel = viewmodel or InstrumentLayoutEditorViewModel(self._load_specs())
        self._on_close = on_close
        self._on_config_saved = on_config_saved
        self._updating = False
        self._instrument_name_to_id: Dict[str, str] = {}
        self._initial_config: Dict[str, object] = copy.deepcopy(self._viewmodel.build_config())
        self._initial_instrument_id: str = self._viewmodel.state.instrument_id
        self._remove_button: ttk.Button | None = None
        self._add_hole_button: ttk.Button | None = None
        self._remove_hole_button: ttk.Button | None = None
        self._hole_entry: ttk.Entry | None = None
        self._json_text: tk.Text | None = None
        self._preview_frame: ttk.Frame | None = None
        self._preview_toggle: ttk.Button | None = None
        self._preview_visible = False
        self._preferred_min_combo: ttk.Combobox | None = None
        self._preferred_max_combo: ttk.Combobox | None = None
        self._candidate_min_combo: ttk.Combobox | None = None
        self._candidate_max_combo: ttk.Combobox | None = None

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)

        self.instrument_var = tk.StringVar(master=self)
        self._instrument_id_var = tk.StringVar(master=self)
        self._instrument_name_var = tk.StringVar(master=self)
        self._title_var = tk.StringVar(master=self)
        self._canvas_width_var = tk.IntVar(master=self)
        self._canvas_height_var = tk.IntVar(master=self)
        self._selection_x_var = tk.DoubleVar(master=self)
        self._selection_y_var = tk.DoubleVar(master=self)
        self._selection_radius_var = tk.DoubleVar(master=self)
        self._status_var = tk.StringVar(master=self)
        self._selection_info_var = tk.StringVar(master=self, value="No element selected")
        self._hole_identifier_var = tk.StringVar(master=self)
        self._preferred_min_var = tk.StringVar(master=self)
        self._preferred_max_var = tk.StringVar(master=self)
        self._candidate_min_var = tk.StringVar(master=self)
        self._candidate_max_var = tk.StringVar(master=self)

        self.canvas = InstrumentLayoutCanvas(
            self,
            on_select=self._on_canvas_select,
            on_move=self._on_canvas_move,
        )
        self.canvas.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=12, pady=12)

        sidebar = ttk.Frame(self)
        sidebar.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=12)
        sidebar.columnconfigure(0, weight=1)

        self._build_header(sidebar)
        self._build_selection_panel(sidebar)
        self._build_style_panel(sidebar)
        self._build_export_panel()

        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._refresh_all()

        center_window_over_parent(self, master)

    # The following overrides exist solely to aid type checking for mixins.
    def _describe_selection(self, state: InstrumentLayoutState) -> str:  # type: ignore[override]
        return super()._describe_selection(state)

    def _on_canvas_select(self, kind: SelectionKind, index: int | None) -> None:  # type: ignore[override]
        super()._on_canvas_select(kind, index)

    def _on_canvas_move(self, kind: SelectionKind, index: int, x: float, y: float) -> None:  # type: ignore[override]
        super()._on_canvas_move(kind, index, x, y)


__all__ = ["InstrumentLayoutEditor"]
