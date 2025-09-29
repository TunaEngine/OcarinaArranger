"""Preview tab construction helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..fingering import FingeringView
from ..piano_roll import PianoRoll
from ..staff import StaffView
from .preview_controls import build_preview_controls
from .preview_overlay import build_preview_progress_overlay

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_preview_tabs"]


def build_preview_tabs(app: "App", notebook: ttk.Notebook) -> None:
    side_width = 240

    orig_tab = ttk.Frame(notebook)
    arr_tab = ttk.Frame(notebook)
    notebook.add(orig_tab, text="Original")
    notebook.add(arr_tab, text="Arranged")

    app._preview_tab_frames = (orig_tab, arr_tab)
    app._preview_frames_by_side.update({"original": orig_tab, "arranged": arr_tab})
    app._preview_sides_by_frame = {orig_tab: "original", arr_tab: "arranged"}

    def _init_side(tab: ttk.Frame, side: str) -> None:
        build_preview_side(app, tab, side, side_width)

    app._register_preview_tab_initializer("original", lambda: _init_side(orig_tab, "original"))
    app._register_preview_tab_initializer("arranged", lambda: _init_side(arr_tab, "arranged"))
    app._ensure_preview_tab_initialized("arranged")


def build_preview_side(app: "App", tab: ttk.Frame, side: str, side_width: int) -> None:
    main = ttk.Frame(tab)
    main.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(0, weight=1)
    register_main = getattr(app, "_preview_main_frames", None)
    if isinstance(register_main, dict):
        register_main[side] = main
    roll = PianoRoll(main, show_fingering=False)
    roll.grid(row=0, column=0, sticky="nsew")
    staff = StaffView(main)
    staff.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    register_roll = getattr(app, "_preview_roll_widgets", None)
    if isinstance(register_roll, dict):
        register_roll[side] = roll
    register_staff = getattr(app, "_preview_staff_widgets", None)
    if isinstance(register_staff, dict):
        register_staff[side] = staff

    if hasattr(app, "_register_auto_scroll_target"):
        app._register_auto_scroll_target(roll)
        app._register_auto_scroll_target(staff)

    def _sync_staff_constraints(_event: tk.Event | None = None) -> None:
        staff.update_idletasks()
        staff_height = staff.winfo_reqheight() or staff.winfo_height()
        if staff_height <= 1:
            return
        row = 0
        try:
            info = staff.grid_info()
            row = int(info.get("row", row))
        except Exception:
            row = 0
        main.grid_rowconfigure(0, weight=1, minsize=staff_height)
        if row == 0:
            main.grid_rowconfigure(1, weight=0, minsize=0)
        else:
            main.grid_rowconfigure(1, weight=0, minsize=staff_height)

    staff.bind("<Configure>", _sync_staff_constraints, add=True)
    main.after_idle(_sync_staff_constraints)

    if side == "original":
        app.roll_orig = roll
        app.staff_orig = staff
    else:
        app.roll_arr = roll
        app.staff_arr = staff

    side_panel = ttk.Frame(tab, width=side_width)
    side_panel.pack(side="left", fill="y", padx=6, pady=8)
    register_side = getattr(app, "_preview_side_panels", None)
    if isinstance(register_side, dict):
        register_side[side] = side_panel

    fingering = FingeringView(side_panel)
    fingering.pack(pady=(0, 8))
    if side == "original":
        app.side_fing_orig = fingering
    else:
        app.side_fing_arr = fingering
    build_preview_controls(app, side_panel, side)

    roll.set_fingering_cb(lambda midi, s=side: app._on_preview_roll_hover(s, midi))
    roll.set_cursor_callback(lambda tick, s=side: app._on_preview_cursor_seek(s, tick))
    if hasattr(staff, "set_cursor_callback"):
        staff.set_cursor_callback(lambda tick, s=side: app._on_preview_cursor_seek(s, tick))

    apply_layout = getattr(app, "_apply_preview_layout_mode_to_side", None)
    if callable(apply_layout):
        try:
            apply_layout(side, data=getattr(app, "_pending_preview_data", None))
        except Exception:
            pass

    build_preview_progress_overlay(app, tab, side)
