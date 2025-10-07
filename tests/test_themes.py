import json
import os
import tkinter as tk
from contextlib import suppress
from pathlib import Path

import pytest

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from ocarina_gui import themes
from shared.tk_style import apply_round_scrollbar_style, get_ttk_style
from shared.ttk import ttk


@pytest.fixture
def reset_theme():
    original = themes.get_current_theme_id()
    try:
        yield
    finally:
        themes.set_active_theme(original)


def test_default_theme_is_loaded(reset_theme):
    theme = themes.get_current_theme()
    assert theme.theme_id == themes.get_current_theme_id()
    assert theme.theme_id == "light"
    palette = theme.palette
    assert palette.window_background.startswith("#")
    assert palette.text_muted != palette.text_primary
    assert palette.text_cursor == palette.text_primary
    assert palette.piano_roll.background.startswith("#")
    assert palette.piano_roll.cursor_primary.startswith("#")
    assert palette.staff.background.startswith("#")
    assert palette.layout_editor.workspace_background.startswith("#")
    assert palette.layout_editor.instrument_surface.startswith("#")
    assert palette.layout_editor.instrument_outline.startswith("#")
    assert palette.layout_editor.hole_outline.startswith("#")
    assert palette.layout_editor.covered_fill.startswith("#")
    assert palette.layout_editor.grid_line.startswith("#")
    assert palette.layout_editor.selection_outline.startswith("#")


def test_available_themes_includes_dark(reset_theme):
    choices = themes.get_available_themes()
    ids = {choice.theme_id for choice in choices}
    assert "light" in ids
    assert "dark" in ids


def test_can_switch_to_dark_theme(reset_theme):
    themes.set_active_theme("dark")
    theme = themes.get_current_theme()
    assert theme.theme_id == "dark"
    palette = theme.palette
    assert palette.window_background != "#f0f0f0"
    assert palette.text_primary != palette.text_muted
    assert palette.text_cursor != palette.text_primary
    assert palette.piano_roll.accidental_row_fill != palette.piano_roll.natural_row_fill
    assert palette.layout_editor.workspace_background != "#f8f9fa"
    assert palette.layout_editor.handle_fill != palette.layout_editor.handle_outline
    assert palette.layout_editor.instrument_surface != palette.layout_editor.hole_fill


def test_set_active_theme_persists_selection(reset_theme):
    pref_path = Path(os.environ["OCARINA_GUI_PREFERENCES_PATH"])
    if pref_path.exists():
        pref_path.unlink()

    themes.set_active_theme("dark")

    payload = json.loads(pref_path.read_text(encoding="utf-8"))
    assert payload["theme_id"] == "dark"


def test_set_active_theme_preserves_log_verbosity(reset_theme):
    pref_path = Path(os.environ["OCARINA_GUI_PREFERENCES_PATH"])
    pref_path.write_text(json.dumps({"log_verbosity": "info"}), encoding="utf-8")

    themes.set_active_theme("dark")

    payload = json.loads(pref_path.read_text(encoding="utf-8"))
    assert payload["theme_id"] == "dark"
    assert payload["log_verbosity"] == "info"


def test_load_library_uses_saved_theme(monkeypatch, tmp_path):
    pref_path = tmp_path / "prefs.json"
    pref_path.write_text(json.dumps({"theme_id": "dark"}), encoding="utf-8")
    monkeypatch.setenv("OCARINA_GUI_PREFERENCES_PATH", str(pref_path))

    library = themes._load_library()
    assert library.current_id() == "dark"


@pytest.mark.gui
def test_apply_theme_to_toplevel_sets_dialog_defaults(reset_theme):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    try:
        themes.set_active_theme("dark")
        window = tk.Toplevel(root)
        palette = themes.apply_theme_to_toplevel(window)

        entry = tk.Entry(window)
        listbox = tk.Listbox(window)

        window.update_idletasks()

        assert window.cget("background").lower() == palette.window_background.lower()
        assert entry.cget("insertbackground").lower() == palette.text_cursor.lower()
        assert listbox.cget("background").lower() == palette.listbox.background.lower()
    finally:
        with suppress(Exception):
            entry.destroy()
        with suppress(Exception):
            listbox.destroy()
        with suppress(Exception):
            window.destroy()
        with suppress(Exception):
            root.destroy()


@pytest.mark.gui
def test_apply_theme_updates_existing_entries(reset_theme):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    try:
        themes.set_active_theme("dark")
        window = tk.Toplevel(root)
        entry = tk.Entry(window)
        entry.configure(insertbackground="#111111")
        window.update_idletasks()

        palette = themes.apply_theme_to_toplevel(window)

        assert entry.cget("insertbackground").lower() == palette.text_cursor.lower()
    finally:
        with suppress(Exception):
            entry.destroy()
        with suppress(Exception):
            window.destroy()
        with suppress(Exception):
            root.destroy()


@pytest.mark.gui
def test_apply_round_scrollbar_style_uses_bootstrap_bootstyle(reset_theme):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    try:
        get_ttk_style(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical")
    except tk.TclError:
        with suppress(Exception):
            root.destroy()
        pytest.skip("Tkinter scrollbars are unavailable")

    try:
        apply_round_scrollbar_style(scrollbar)
        bootstyle = scrollbar.cget("bootstyle")
        assert "round" in str(bootstyle)
    finally:
        with suppress(Exception):
            scrollbar.destroy()
        with suppress(Exception):
            root.destroy()


@pytest.mark.gui
def test_apply_theme_sets_ttk_entry_caret_color(reset_theme):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display is not available")

    root.withdraw()

    late_entry = None

    try:
        themes.set_active_theme("dark")
        window = tk.Toplevel(root)
        get_ttk_style(root)
        entry = ttk.Entry(window)
        style = get_ttk_style(root)

        palette = themes.apply_theme_to_toplevel(window)
        window.update_idletasks()

        style_name = entry.cget("style") or entry.winfo_class()
        configured = style.configure(style_name).get("insertcolor", "")
        assert configured.lower() == palette.text_cursor.lower()

        late_entry = ttk.Entry(window)
        window.update_idletasks()

        late_style_name = late_entry.cget("style") or late_entry.winfo_class()
        late_configured = style.configure(late_style_name).get("insertcolor", "")
        assert late_configured.lower() == palette.text_cursor.lower()
    finally:
        if late_entry is not None:
            with suppress(Exception):
                late_entry.destroy()
        with suppress(Exception):
            entry.destroy()
        with suppress(Exception):
            window.destroy()
        with suppress(Exception):
            root.destroy()
