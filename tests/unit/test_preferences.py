import json

from ocarina_gui.preferences import Preferences, load_preferences, save_preferences


def test_preferences_round_trip(tmp_path):
    path = tmp_path / "prefs.json"
    preferences = Preferences(
        theme_id="dark",
        log_verbosity="warning",
        recent_projects=["/music/song1.ocarina", "/music/song2.ocarina"],
        auto_scroll_mode="continuous",
        preview_layout_mode="piano_vertical",
        auto_update_enabled=False,
    )

    save_preferences(preferences, path)

    loaded = load_preferences(path)
    assert loaded.theme_id == "dark"
    assert loaded.log_verbosity == "warning"
    assert loaded.recent_projects == ["/music/song1.ocarina", "/music/song2.ocarina"]
    assert loaded.auto_scroll_mode == "continuous"
    assert loaded.preview_layout_mode == "piano_vertical"
    assert loaded.auto_update_enabled is False


def test_load_preferences_with_invalid_types(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text(
        json.dumps(
            {
                "theme_id": 3,
                "log_verbosity": 5,
                "recent_projects": [1, "/valid/project.ocarina", None],
                "auto_scroll_mode": 123,
                "preview_layout_mode": "unsupported",
                "auto_update_enabled": "nope",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_preferences(path)
    assert loaded.theme_id is None
    assert loaded.log_verbosity is None
    assert loaded.recent_projects == ["/valid/project.ocarina"]
    assert loaded.auto_scroll_mode is None
    assert loaded.preview_layout_mode is None
    assert loaded.auto_update_enabled is None
