from __future__ import annotations

import sys
import tkinter as tk

import pytest

from ocarina_gui import themes
from ocarina_gui.color_utils import hex_to_rgb, mix_colors, rgb_to_hex


pytestmark = pytest.mark.usefixtures("ensure_original_preview")


def _lookup_state_value(style, style_name: str, option: str, state: str) -> str | None:
    entries = style.map(style_name, query_opt=option)
    for entry in entries:
        if not entry:
            continue

        *statespec_parts, value = entry
        tokens: list[str] = []
        if not statespec_parts:
            tokens.append("")
        for spec in statespec_parts:
            if isinstance(spec, str):
                tokens.extend(spec.split())
            else:
                for token in spec:
                    tokens.extend(str(token).split())
        if state in tokens:
            return value
    return None


@pytest.mark.gui
def test_runtime_theme_switch_uses_bootstrap_theme(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Requires Tk display to inspect ttk theme usage")

    style = getattr(gui_app, "_style", None)
    if style is None:
        pytest.skip("Requires Tk style information")

    try:
        initial_theme = str(style.theme_use())
    except tk.TclError:
        pytest.skip("Unable to query ttk theme")

    gui_app.activate_theme_menu("dark")
    gui_app.update_idletasks()

    try:
        dark_theme = str(style.theme_use())
    except tk.TclError:
        pytest.fail("Failed to query ttk theme after switching to dark")
    assert dark_theme.lower() == "darkly"

    gui_app.activate_theme_menu("light")
    gui_app.update_idletasks()

    try:
        light_theme = str(style.theme_use())
    except tk.TclError:
        pytest.fail("Failed to query ttk theme after switching back to light")
    assert light_theme.lower() == "litera"

    assert initial_theme.lower() in {"litera", "darkly"}


def test_theme_menu_switches_active_theme(gui_app):
    available = {choice.theme_id: choice.name for choice in themes.get_available_themes()}
    dark_name = available["dark"]
    light_name = available["light"]

    gui_app.activate_theme_menu("dark")
    gui_app.update_idletasks()
    assert themes.get_current_theme_id() == "dark"
    assert gui_app.theme_id.get() == "dark"
    assert gui_app.theme_name.get() == dark_name

    gui_app.activate_theme_menu("light")
    gui_app.update_idletasks()
    assert themes.get_current_theme_id() == "light"
    assert gui_app.theme_id.get() == "light"
    assert gui_app.theme_name.get() == light_name


def test_dark_theme_hover_states_use_high_contrast(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Requires Tk display to inspect ttk style maps")

    style = gui_app._style
    if style is None:
        pytest.skip("Requires Tk style information")

    themes.set_active_theme("dark")
    gui_app.update_idletasks()

    button_active = _lookup_state_value(style, "TButton", "background", "active")
    check_active = _lookup_state_value(style, "TCheckbutton", "background", "active")
    combo_active = _lookup_state_value(style, "TCombobox", "fieldbackground", "active")
    radio_active = _lookup_state_value(style, "TRadiobutton", "background", "active")
    tab_selected_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "selected")
    tab_active_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "active")
    tab_unselected_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "!selected")
    tab_selected_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "selected")
    tab_active_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "active")
    tab_unselected_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "!selected")

    assert button_active == "#3a3f4b"
    assert check_active == "#2c313c"
    assert combo_active == "#303541"
    assert radio_active == "#2c313c"
    assert tab_selected_fg == "#ffffff"
    assert tab_active_fg == "#ffffff"
    assert tab_unselected_fg == "#c5d1eb"
    assert tab_selected_bg == "#1e1e1e"
    assert tab_active_bg == "#3a3f4b"
    assert tab_unselected_bg == "#2d2d2d"


def test_light_theme_restores_tab_style_after_dark(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Requires Tk display to inspect ttk style maps")

    style = gui_app._style
    if style is None:
        pytest.skip("Requires Tk style information")

    themes.set_active_theme("dark")
    gui_app.update_idletasks()
    themes.set_active_theme("light")
    gui_app.update_idletasks()

    tab_selected_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "selected")
    tab_active_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "active")
    tab_unselected_fg = _lookup_state_value(style, "TNotebook.Tab", "foreground", "!selected")
    tab_selected_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "selected")
    tab_active_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "active")
    tab_unselected_bg = _lookup_state_value(style, "TNotebook.Tab", "background", "!selected")

    assert tab_selected_fg == "#111111"
    assert tab_active_fg == "#111111"
    assert tab_unselected_fg == "#111111"
    assert tab_selected_bg == "#ffffff"
    assert tab_active_bg == "#d8ebff"
    assert tab_unselected_bg == "#e6e6e6"


def test_widgets_follow_theme_palette(gui_app):
    palette = themes.get_current_theme().palette

    roll = gui_app.roll_orig
    assert roll is not None
    if not hasattr(roll.canvas, "__getitem__"):
        pytest.skip("Theme palette verification requires Tk-based widgets")
    assert roll.canvas["background"] == palette.piano_roll.background
    assert roll.labels["background"] == palette.piano_roll.background

    staff = gui_app.staff_orig
    assert staff is not None
    if not hasattr(staff.canvas, "__getitem__"):
        pytest.skip("Theme palette verification requires Tk-based widgets")
    assert staff.canvas["background"] == palette.staff.background


def test_dark_theme_updates_menu_and_title(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Requires Tk display to inspect menu styling")

    menus = [
        menu
        for menu in getattr(gui_app, "_registered_menus", [])
        if hasattr(menu, "cget")
    ]
    if not menus:
        pytest.skip("Requires Tk menus to verify styling")

    themes.set_active_theme("dark")
    gui_app.update_idletasks()

    palette = themes.get_current_theme().palette

    expected_select_color = rgb_to_hex(
        mix_colors(
            hex_to_rgb(palette.window_background),
            hex_to_rgb(palette.text_primary),
            0.5,
        )
    )

    for menu in menus:
        assert menu.cget("background") == palette.window_background
        assert menu.cget("foreground") == palette.text_primary
        assert menu.cget("activebackground") == palette.table.selection_background
        assert menu.cget("activeforeground") == palette.table.selection_foreground
        assert menu.cget("disabledforeground") == palette.text_muted
        assert menu.cget("selectcolor") == expected_select_color
        try:
            indicator_color = menu.cget("indicatorforeground")
        except Exception:
            indicator_color = None
        if indicator_color is not None:
            assert indicator_color == palette.text_primary

    assert getattr(gui_app, "_last_title_background_attempt", None) == palette.window_background
    assert getattr(gui_app, "_last_title_color_attempt", None) == palette.text_primary
    assert getattr(gui_app, "_last_title_dark_mode_attempt", None) is True
    if sys.platform == "win32":
        assert getattr(gui_app, "_last_title_hwnd_attempt", None)
        assert getattr(gui_app, "_last_menubar_brush_color_attempt", None) == palette.window_background
        assert getattr(gui_app, "_last_title_geometry_nudge", None)
        assert getattr(gui_app, "_windows_dark_mode_app_allowed", None) is not None
        assert getattr(gui_app, "_last_dark_mode_window_attempt", None) is True
        assert getattr(gui_app, "_last_dark_mode_window_result", None) is not None

