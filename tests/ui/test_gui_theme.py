from __future__ import annotations

import pytest

from ocarina_gui import themes


pytestmark = pytest.mark.usefixtures("ensure_original_preview")


def _lookup_state_value(style, style_name: str, option: str, state: str) -> str | None:
    entries = style.map(style_name, query_opt=option)
    for statespec, value in entries:
        if isinstance(statespec, str):
            tokens = statespec.split()
        else:
            tokens = []
            for token in statespec:
                tokens.extend(str(token).split())
        if state in tokens:
            return value
    return None


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

