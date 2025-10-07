"""Preview tab construction helpers."""

from __future__ import annotations

import importlib.resources as resources
import tkinter as tk
from shared.ttk import ttk
from typing import TYPE_CHECKING

from ..fingering import FingeringView
from ..piano_roll import PianoRoll
from ..staff import StaffView
from .preview_controls import build_arranged_preview_controls
from .preview_overlay import build_preview_progress_overlay

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from ..app import App


__all__ = ["build_preview_tabs"]


def build_preview_tabs(app: "App", notebook: ttk.Notebook) -> None:
    side_width = 240

    orig_tab = ttk.Frame(notebook, style="Panel.TFrame")
    arr_tab = ttk.Frame(notebook, style="Panel.TFrame")
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
    _build_modern_preview_side(app, tab, side, side_width)


def _build_modern_preview_side(
    app: "App", tab: ttk.Frame, side: str, side_width: int
) -> None:
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_columnconfigure(1, weight=0)
    tab.grid_rowconfigure(0, weight=1)

    main = ttk.Frame(tab, style="Panel.TFrame")
    main.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=12)
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(0, weight=0)
    main.grid_rowconfigure(1, weight=0)
    main.grid_rowconfigure(2, weight=1)

    layout_area = ttk.Frame(main, style="Panel.TFrame")
    layout_area.grid(row=2, column=0, sticky="nsew")
    layout_area.grid_columnconfigure(0, weight=1)
    layout_area.grid_rowconfigure(0, weight=1)
    layout_area.grid_rowconfigure(1, weight=0)

    register_main = getattr(app, "_preview_main_frames", None)
    if isinstance(register_main, dict):
        register_main[side] = layout_area

    transport = ttk.Frame(main, padding=(0, 4), style="Panel.TFrame")
    transport.grid(row=0, column=0, sticky="ew")
    transport.grid_columnconfigure(0, weight=0)
    transport.grid_columnconfigure(1, weight=1)
    transport.grid_columnconfigure(2, weight=0)

    zoom_frame = ttk.Frame(transport, style="Panel.TFrame")
    zoom_frame.grid(row=0, column=0, sticky="w")
    ttk.Label(zoom_frame, text="Time Zoom").pack(side="left", padx=(0, 6))
    zoom_in_icon = _load_arranged_icon(app, "zoom_in")
    zoom_in_kwargs: dict[str, object] = {
        "command": lambda: app._hzoom_all(1.25),
        "padding": 2,
    }
    if zoom_in_icon is not None:
        zoom_in_kwargs["image"] = zoom_in_icon
    else:
        zoom_in_kwargs["text"] = "＋"
        zoom_in_kwargs["width"] = 3
    zoom_in_btn = ttk.Button(zoom_frame, **zoom_in_kwargs)
    zoom_in_btn.pack(side="left", padx=(0, 6))
    zoom_out_icon = _load_arranged_icon(app, "zoom_out")
    zoom_out_kwargs: dict[str, object] = {
        "command": lambda: app._hzoom_all(0.8),
        "padding": 2,
    }
    if zoom_out_icon is not None:
        zoom_out_kwargs["image"] = zoom_out_icon
    else:
        zoom_out_kwargs["text"] = "－"
        zoom_out_kwargs["width"] = 3
    zoom_out_btn = ttk.Button(zoom_frame, **zoom_out_kwargs)
    zoom_out_btn.pack(side="left")

    volume_frame = ttk.Frame(transport, style="Panel.TFrame")
    volume_frame.grid(row=0, column=1, sticky="w", padx=(12, 12))
    volume_icon = _load_arranged_icon(app, "volume")
    muted_volume_icon = _load_arranged_icon(app, "volume_muted")
    volume_kwargs: dict[str, object] = {
        "command": lambda s=side: app._handle_preview_volume_button(s, None),
        "padding": 2,
    }
    if volume_icon is not None:
        volume_kwargs["image"] = volume_icon
    else:
        volume_kwargs["text"] = "🔈"
        volume_kwargs["width"] = 3
    volume_btn = ttk.Button(volume_frame, **volume_kwargs)
    volume_btn.grid(row=0, column=0, sticky="w")
    volume_btn.bind(
        "<ButtonRelease-1>",
        lambda event, s=side: app._handle_preview_volume_button(s, event),
        add="+",
    )
    volume_slider = ttk.Scale(
        volume_frame,
        from_=0,
        to=100,
        orient="horizontal",
        variable=app._preview_volume_vars[side],
        bootstyle="info",
        length=120,
    )
    volume_slider.grid(row=0, column=1, sticky="w", padx=(8, 0))
    volume_slider.bind(
        "<ButtonPress-1>",
        lambda event, s=side: app._on_preview_volume_press(s, event),
        add="+",
    )
    volume_slider.bind(
        "<B1-Motion>",
        lambda event, s=side: app._on_preview_volume_drag(s, event),
        add="+",
    )
    volume_slider.bind(
        "<ButtonRelease-1>",
        lambda event, s=side: app._on_preview_volume_release(s, event),
        add="+",
    )

    playback_bar = ttk.Frame(transport, style="Panel.TFrame")
    playback_bar.grid(row=0, column=2, sticky="e")
    playback_bar.grid_columnconfigure(0, weight=0)
    playback_bar.grid_columnconfigure(1, weight=0)

    play_icon = _load_arranged_icon(app, "play")
    pause_icon = _load_arranged_icon(app, "pause")
    icon_map = getattr(app, "_preview_play_icons", None)
    if not isinstance(icon_map, dict):
        icon_map = {}
        app._preview_play_icons = icon_map
    side_icons = icon_map.setdefault(side, {})
    side_icons["play"] = play_icon
    side_icons["pause"] = pause_icon
    play_kwargs: dict[str, object] = {
        "textvariable": app._preview_play_vars[side],
        "command": lambda s=side: app._on_preview_play_toggle(s),
        "padding": 2,
    }
    if play_icon is not None:
        play_kwargs["image"] = play_icon
        play_kwargs["compound"] = "left"
    else:
        play_kwargs["width"] = 8
    play_btn = ttk.Button(playback_bar, **play_kwargs)
    if hasattr(app, "_apply_icon_button_style"):
        try:
            app._apply_icon_button_style(play_btn)
        except Exception:
            pass
    play_btn.grid(row=0, column=0)

    buttons = getattr(app, "_preview_play_buttons", None)
    if not isinstance(buttons, dict):
        buttons = {}
        app._preview_play_buttons = buttons
    buttons[side] = play_btn

    time_frame = ttk.Frame(playback_bar)
    time_frame.grid(row=0, column=1, sticky="w", padx=(12, 0))
    ttk.Label(
        time_frame,
        textvariable=app._preview_position_vars[side],
        font=("", 11, "bold"),
    ).pack(side="left")
    ttk.Label(time_frame, text="/").pack(side="left", padx=4)
    ttk.Label(
        time_frame,
        textvariable=app._preview_duration_vars[side],
        foreground="#64748b",
    ).pack(side="left")

    register_icon = getattr(app, "_register_arranged_icon_target", None)
    if callable(register_icon):
        register_icon("zoom_in", zoom_in_btn)
        register_icon("zoom_out", zoom_out_btn)
        register_icon("volume", volume_btn)

    volume_controls = getattr(app, "_preview_volume_controls", None)
    if isinstance(volume_controls, dict):
        volume_controls[side] = (volume_btn, volume_slider)
    volume_icon_sets = getattr(app, "_preview_volume_icons", None)
    if not isinstance(volume_icon_sets, dict):
        volume_icon_sets = {}
        app._preview_volume_icons = volume_icon_sets
    volume_icon_sets[side] = {
        "normal": volume_icon,
        "muted": muted_volume_icon,
    }
    volume_buttons = getattr(app, "_preview_volume_buttons", None)
    if isinstance(volume_buttons, dict):
        volume_buttons[side] = volume_btn
    if hasattr(app, "_update_mute_button_state"):
        try:
            app._update_mute_button_state(side)
        except Exception:
            pass

    ttk.Separator(main, orient="horizontal").grid(
        row=1, column=0, sticky="ew", pady=(6, 6)
    )

    roll = PianoRoll(layout_area, show_fingering=False)
    roll.grid(row=0, column=0, sticky="nsew")
    staff = StaffView(layout_area)
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
        try:
            manager = staff.winfo_manager()
        except tk.TclError:
            manager = ""
        if manager != "grid":
            layout_area.grid_rowconfigure(0, weight=1, minsize=0)
            layout_area.grid_rowconfigure(1, weight=0, minsize=0)
            return
        try:
            staff.update_idletasks()
        except tk.TclError:
            pass
        staff_height = staff.winfo_reqheight() or staff.winfo_height()
        staff_height = max(0, staff_height)
        try:
            info = staff.grid_info()
            row = int(info.get("row", 1))
        except Exception:
            row = 1
        if row == 0:
            layout_area.grid_rowconfigure(0, weight=1, minsize=staff_height)
            layout_area.grid_rowconfigure(1, weight=0, minsize=0)
        else:
            layout_area.grid_rowconfigure(0, weight=1, minsize=0)
            layout_area.grid_rowconfigure(1, weight=0, minsize=staff_height)

    staff.bind("<Configure>", _sync_staff_constraints, add=True)
    main.after_idle(_sync_staff_constraints)

    if side == "original":
        app.roll_orig = roll
        app.staff_orig = staff
    else:
        app.roll_arr = roll
        app.staff_arr = staff

    side_panel = ttk.Frame(tab, width=side_width, padding=(12, 12), style="Panel.TFrame")
    side_panel.grid(row=0, column=1, sticky="ns", pady=12, padx=(0, 12))
    side_panel.grid_columnconfigure(0, weight=1)
    side_panel.grid_rowconfigure(2, weight=1)

    register_side = getattr(app, "_preview_side_panels", None)
    if isinstance(register_side, dict):
        register_side[side] = side_panel

    heading = ttk.Label(side_panel, text="Fingering Preview", anchor="center")
    heading.grid(row=0, column=0, sticky="ew")

    fingering_box = ttk.Frame(side_panel, padding=12, relief="groove", borderwidth=1, style="Panel.TFrame")
    fingering_box.grid(row=1, column=0, sticky="ew", pady=(8, 16))
    fingering_box.grid_columnconfigure(0, weight=1)

    fingering = FingeringView(fingering_box)
    fingering.grid(row=0, column=0, sticky="n")
    if side == "original":
        app.side_fing_orig = fingering
    else:
        app.side_fing_arr = fingering

    control_container = ttk.Frame(side_panel, style="Panel.TFrame")
    control_container.grid(row=2, column=0, sticky="nsew")
    control_container.grid_columnconfigure(0, weight=1)

    build_arranged_preview_controls(app, control_container, side)

    roll.set_fingering_cb(lambda midi, s=side: app._on_preview_roll_hover(s, midi))
    roll.set_cursor_callback(lambda tick, s=side: app._on_preview_cursor_seek(s, tick))
    if hasattr(roll, "set_cursor_drag_state_cb"):
        roll.set_cursor_drag_state_cb(
            lambda dragging, s=side: app._on_preview_cursor_drag_state(s, dragging)
        )
    if hasattr(staff, "set_cursor_callback"):
        staff.set_cursor_callback(lambda tick, s=side: app._on_preview_cursor_seek(s, tick))
    if hasattr(staff, "set_cursor_drag_state_cb"):
        staff.set_cursor_drag_state_cb(
            lambda dragging, s=side: app._on_preview_cursor_drag_state(s, dragging)
        )

    apply_layout = getattr(app, "_apply_preview_layout_mode_to_side", None)
    if callable(apply_layout):
        try:
            apply_layout(side, data=getattr(app, "_pending_preview_data", None))
        except Exception:
            pass

    build_preview_progress_overlay(app, tab, side)


def _load_arranged_icon(app: "App", name: str) -> tk.PhotoImage | None:
    entry = _ensure_arranged_icon_entry(app, name)
    if not entry:
        return None

    resolver = getattr(app, "_is_preview_theme_dark", None)
    variant = "dark" if callable(resolver) and resolver() else "light"
    image = entry.get(variant)
    if image is None and variant == "dark":
        # Fall back to the light variant if a dark image was not provided.
        image = entry.get("light")
    return image


def _ensure_arranged_icon_entry(app: "App", name: str) -> dict[str, tk.PhotoImage | None] | None:
    cache = getattr(app, "_arranged_icon_cache", None)
    if cache is None:
        cache = {}
        app._arranged_icon_cache = cache
    entry = cache.get(name)
    if entry is not None:
        return entry

    package = "ocarina_gui.ui_builders.assets"
    entry: dict[str, tk.PhotoImage | None] = {}

    light_candidates = (f"arranged_{name}_light.png", f"arranged_{name}.png")
    dark_candidates = (f"arranged_{name}_dark.png",)

    light_image = _load_arranged_icon_from_candidates(app, package, light_candidates)
    if light_image is not None:
        entry["light"] = light_image

    dark_image = _load_arranged_icon_from_candidates(app, package, dark_candidates)
    if dark_image is not None:
        entry["dark"] = dark_image

    if "light" in entry and "dark" not in entry:
        entry["dark"] = entry["light"]
    elif "dark" in entry and "light" not in entry:
        entry["light"] = entry["dark"]

    cache[name] = entry
    return entry


def _load_arranged_icon_from_candidates(
    app: "App", package: str, candidates: tuple[str, ...]
) -> tk.PhotoImage | None:
    for resource_name in candidates:
        image = _load_photoimage_from_resource(app, package, resource_name)
        if image is not None:
            return image
    return None


def _load_photoimage_from_resource(
    app: "App", package: str, resource_name: str
) -> tk.PhotoImage | None:
    try:
        resource = resources.files(package).joinpath(resource_name)
    except (FileNotFoundError, ModuleNotFoundError):
        return None

    if resource is None or not getattr(resource, "is_file", lambda: False)():
        return None

    try:
        with resources.as_file(resource) as path:
            return tk.PhotoImage(master=app, file=str(path))
    except (FileNotFoundError, tk.TclError):
        return None


