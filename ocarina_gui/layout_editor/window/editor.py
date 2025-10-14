"""Instrument layout editor window implementation."""

from __future__ import annotations

import copy
import logging
from typing import Callable, Dict

import tkinter as tk
from shared.ttk import ttk

from shared.tkinter_geometry import center_window_over_parent
from shared.tk_style import apply_round_scrollbar_style
from ocarina_gui.themes import apply_theme_to_toplevel
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


LOGGER = logging.getLogger(__name__)


class InstrumentLayoutEditor(
    _LayoutEditorConfigMixin,
    _LayoutEditorActionsMixin,
    _LayoutEditorStateMixin,
    _LayoutEditorUIMixin,
    tk.Toplevel,
):
    """Standalone window exposing a WYSIWYG instrument editor."""

    _last_selected_instrument_id: str | None = None

    def __init__(
        self,
        master: tk.Misc,
        *,
        viewmodel: InstrumentLayoutEditorViewModel | None = None,
        on_close: Callable[[], None] | None = None,
        on_config_saved: Callable[[Dict[str, object], str], None] | None = None,
        allow_half_var: tk.BooleanVar | None = None,
        on_half_toggle: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Instrument Layout Editor")
        self.transient(master)
        self.resizable(True, True)

        self._viewmodel = viewmodel or InstrumentLayoutEditorViewModel(self._load_specs())
        remembered_id = self.__class__._last_selected_instrument_id
        if remembered_id:
            try:
                self._viewmodel.select_instrument(remembered_id)
            except ValueError:
                pass
        self._on_close = on_close
        self._on_config_saved = on_config_saved
        self._updating = False
        self._instrument_name_to_id: Dict[str, str] = {}
        self._initial_config: Dict[str, object] = copy.deepcopy(self._viewmodel.build_config())
        self._initial_instrument_id: str = self._viewmodel.state.instrument_id
        self._remove_button: ttk.Button | None = None
        self._add_hole_button: ttk.Button | None = None
        self._add_windway_button: ttk.Button | None = None
        self._remove_element_button: ttk.Button | None = None
        self._hole_entry: ttk.Entry | None = None
        self._width_entry: ttk.Entry | None = None
        self._height_entry: ttk.Entry | None = None
        self._json_text: tk.Text | None = None
        self._preview_frame: ttk.Frame | None = None
        self._preview_toggle: ttk.Button | None = None
        self._done_button: ttk.Button | None = None
        self._cancel_button: ttk.Button | None = None
        self._preview_visible = False
        self._footer_menus: tuple[tk.Menu, ...] | None = None
        self._preferred_min_combo: ttk.Combobox | None = None
        self._preferred_max_combo: ttk.Combobox | None = None
        self._candidate_min_combo: ttk.Combobox | None = None
        self._candidate_max_combo: ttk.Combobox | None = None
        self._allow_half_check: ttk.Checkbutton | None = None
        self._allow_half_var = allow_half_var
        self._on_half_toggle = on_half_toggle
        self._last_instrument_id: str | None = None
        self._sidebar_canvas: tk.Canvas | None = None
        self._sidebar_scrollbar: ttk.Scrollbar | None = None
        self._sidebar_window_id: int | None = None
        self._sidebar_frame: ttk.Frame | None = None

        palette = apply_theme_to_toplevel(self)

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
        self._selection_width_var = tk.DoubleVar(master=self)
        self._selection_height_var = tk.DoubleVar(master=self)
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

        sidebar_container = ttk.Frame(self)
        sidebar_container.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=12)
        sidebar_container.columnconfigure(0, weight=1)
        sidebar_container.rowconfigure(0, weight=1)

        sidebar_canvas = tk.Canvas(
            sidebar_container,
            highlightthickness=0,
            borderwidth=0,
            background=palette.window_background,
        )
        sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_canvas.configure(yscrollincrement=20)
        sidebar_scrollbar = ttk.Scrollbar(
            sidebar_container,
            orient="vertical",
            command=sidebar_canvas.yview,
        )
        apply_round_scrollbar_style(sidebar_scrollbar)
        sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)

        sidebar = ttk.Frame(sidebar_canvas)
        window_id = sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.columnconfigure(0, weight=1)

        def _update_scrollregion(_event: tk.Event) -> None:
            sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))

        def _sync_canvas_width(event: tk.Event) -> None:
            sidebar_canvas.itemconfigure(window_id, width=event.width)

        def _on_scroll(event: tk.Event) -> str | None:
            if sidebar_canvas.yview() == (0.0, 1.0):
                return None
            delta = 0
            if hasattr(event, "delta") and event.delta:
                normalized = int(event.delta)
                if normalized > 0:
                    delta = -1
                elif normalized < 0:
                    delta = 1
            elif getattr(event, "num", None) in (4, 5):
                delta = -1 if event.num == 4 else 1
            if delta:
                sidebar_canvas.yview_scroll(delta, "units")
                return "break"
            return None

        sidebar.bind("<Configure>", _update_scrollregion)
        sidebar_canvas.bind("<Configure>", _sync_canvas_width)
        sidebar_canvas.bind("<MouseWheel>", _on_scroll, add="+")
        sidebar_canvas.bind("<Button-4>", _on_scroll, add="+")
        sidebar_canvas.bind("<Button-5>", _on_scroll, add="+")
        sidebar.bind("<MouseWheel>", _on_scroll, add="+")
        sidebar.bind("<Button-4>", _on_scroll, add="+")
        sidebar.bind("<Button-5>", _on_scroll, add="+")

        self._sidebar_canvas = sidebar_canvas
        self._sidebar_scrollbar = sidebar_scrollbar
        self._sidebar_window_id = window_id
        self._sidebar_frame = sidebar

        self._build_header(sidebar)
        self._build_selection_panel(sidebar)
        self._build_export_panel()

        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._refresh_all()

        self.update_idletasks()
        requested_width = self.winfo_reqwidth()
        requested_height = self.winfo_reqheight()
        screen_width = max(1, self.winfo_screenwidth())
        screen_height = max(1, self.winfo_screenheight())
        max_width = max(640, screen_width - 80)
        usable_height = max(720, screen_height - 40)
        min_required_height = max(requested_height, 520)

        sidebar_canvas = self._sidebar_canvas
        sidebar_frame = self._sidebar_frame
        if sidebar_canvas is not None and sidebar_frame is not None:
            sidebar_canvas_req = sidebar_canvas.winfo_reqheight()
            sidebar_content_req = sidebar_frame.winfo_reqheight()
            other_height = max(0, requested_height - sidebar_canvas_req)
            min_required_height = max(
                min_required_height, other_height + sidebar_content_req
            )
            available_sidebar_height = max(0, screen_height - other_height)
            if (
                sidebar_content_req > 0
                and sidebar_content_req <= available_sidebar_height
                and sidebar_content_req > sidebar_canvas_req
            ):
                sidebar_canvas.configure(height=sidebar_content_req)
                self.update_idletasks()
                requested_width = self.winfo_reqwidth()
                requested_height = self.winfo_reqheight()
                min_required_height = max(min_required_height, requested_height)

        width = min(requested_width, max_width)
        resolved_height = min(screen_height, max(min_required_height, usable_height))
        min_height = min(min_required_height, screen_height)
        self.geometry(f"{width}x{resolved_height}")
        self.minsize(min(requested_width, max_width), min_height)

        LOGGER.debug(
            "Instrument layout editor initial geometry width=%s height=%s screen=(%s,%s) "
            "requested=(%s,%s) min_required=%s usable_height=%s",
            width,
            resolved_height,
            screen_width,
            screen_height,
            requested_width,
            requested_height,
            min_required_height,
            usable_height,
        )

        center_window_over_parent(self, master)
        self.deiconify()

    # The following overrides exist solely to aid type checking for mixins.
    def _describe_selection(self, state: InstrumentLayoutState) -> str:  # type: ignore[override]
        return super()._describe_selection(state)

    def _on_canvas_select(self, kind: SelectionKind, index: int | None) -> None:  # type: ignore[override]
        super()._on_canvas_select(kind, index)

    def _on_canvas_move(self, kind: SelectionKind, index: int, x: float, y: float) -> None:  # type: ignore[override]
        super()._on_canvas_move(kind, index, x, y)

    def _remember_last_instrument(self, instrument_id: str) -> None:
        if instrument_id:
            self.__class__._last_selected_instrument_id = instrument_id


__all__ = ["InstrumentLayoutEditor"]
