import json

import pytest

from app.config import (
    AppConfig,
    AutoScrollConfig,
    FlipAutoScrollConfig,
    PlaybackTiming,
    get_auto_scroll_config,
    get_playback_timing,
    load_app_config,
    reset_app_config_cache,
)


def test_default_config_exposes_playback_fps() -> None:
    reset_app_config_cache()
    config = load_app_config()
    assert isinstance(config, AppConfig)
    assert config.playback.idle_fps == 30
    assert config.playback.active_fps == 60
    assert config.playback.idle_interval_ms == 33
    assert config.playback.active_interval_ms == 16


def test_default_config_includes_flip_auto_scroll_settings() -> None:
    reset_app_config_cache()
    config = load_app_config()
    assert isinstance(config.auto_scroll, AutoScrollConfig)
    assert config.auto_scroll.flip == FlipAutoScrollConfig(threshold_percent=75, page_offset_percent=25)
    assert config.auto_scroll.flip.threshold_fraction == pytest.approx(0.75)
    assert config.auto_scroll.flip.page_offset_fraction == pytest.approx(0.25)


def test_load_app_config_from_custom_path(tmp_path) -> None:
    custom_config = {
        "playback": {
            "idle_fps": 48,
            "active_fps": 120,
        },
        "auto_scroll": {
            "flip": {
                "threshold_percent": 60,
                "page_offset_percent": 30,
            }
        },
    }
    config_path = tmp_path / "app.json"
    config_path.write_text(json.dumps(custom_config), encoding="utf-8")

    config = load_app_config(config_path)
    assert config.playback.idle_fps == 48
    assert config.playback.active_fps == 120
    assert config.playback.idle_interval_ms == 20
    assert config.playback.active_interval_ms == 8
    assert config.auto_scroll.flip == FlipAutoScrollConfig(threshold_percent=60, page_offset_percent=30)


def test_invalid_config_values_fall_back_to_defaults(tmp_path) -> None:
    invalid_config = {
        "playback": {
            "idle_fps": "zero",
            "active_fps": -15,
        },
        "auto_scroll": {
            "flip": {
                "threshold_percent": "never",
                "page_offset_percent": 150,
            }
        },
    }
    config_path = tmp_path / "app.json"
    config_path.write_text(json.dumps(invalid_config), encoding="utf-8")

    config = load_app_config(config_path)
    assert config.playback == PlaybackTiming(idle_fps=30, active_fps=60)
    assert config.auto_scroll.flip == FlipAutoScrollConfig(threshold_percent=75, page_offset_percent=25)


def test_get_playback_timing_uses_cached_config(monkeypatch, tmp_path) -> None:
    initial_config = {"playback": {"idle_fps": 40, "active_fps": 90}}
    config_path = tmp_path / "app.json"
    config_path.write_text(json.dumps(initial_config), encoding="utf-8")

    original_loader = load_app_config

    def _load_override(path=None):  # noqa: ANN001 - signature dictated by monkeypatch
        return original_loader(config_path)

    reset_app_config_cache()
    monkeypatch.setattr("app.config.load_app_config", _load_override)

    first = get_playback_timing()
    assert first.idle_interval_ms == 25
    assert first.active_interval_ms == 11

    updated_config = {"playback": {"idle_fps": 30, "active_fps": 60}}
    config_path.write_text(json.dumps(updated_config), encoding="utf-8")

    second = get_playback_timing()
    assert second is first
    assert second.idle_interval_ms == 25
    assert second.active_interval_ms == 11


def test_get_auto_scroll_config_uses_cached_config(monkeypatch, tmp_path) -> None:
    initial_config = {
        "auto_scroll": {"flip": {"threshold_percent": 64, "page_offset_percent": 40}}
    }
    config_path = tmp_path / "app.json"
    config_path.write_text(json.dumps(initial_config), encoding="utf-8")

    original_loader = load_app_config

    def _load_override(path=None):  # noqa: ANN001 - signature dictated by monkeypatch
        return original_loader(config_path)

    reset_app_config_cache()
    monkeypatch.setattr("app.config.load_app_config", _load_override)

    first = get_auto_scroll_config()
    assert first.flip == FlipAutoScrollConfig(threshold_percent=64, page_offset_percent=40)

    updated_config = {
        "auto_scroll": {"flip": {"threshold_percent": 50, "page_offset_percent": 20}}
    }
    config_path.write_text(json.dumps(updated_config), encoding="utf-8")

    second = get_auto_scroll_config()
    assert second is first
    assert second.flip == FlipAutoScrollConfig(threshold_percent=64, page_offset_percent=40)
