import json
import os
from pathlib import Path

import pytest

from ocarina_gui import themes


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
    assert palette.piano_roll.background.startswith("#")
    assert palette.piano_roll.cursor_primary.startswith("#")
    assert palette.staff.background.startswith("#")


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
    assert palette.piano_roll.accidental_row_fill != palette.piano_roll.natural_row_fill


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
