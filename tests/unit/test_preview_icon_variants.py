from types import SimpleNamespace

import pytest

from ocarina_gui.ui_builders import preview


def test_ensure_arranged_icon_entry_prefers_variant_specific_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    sentinel_light = object()
    sentinel_dark = object()

    def _fake_loader(app: object, package: str, candidates: tuple[str, ...]):
        calls.append(candidates)
        if candidates[0].endswith("_light.png"):
            return sentinel_light
        if candidates[0].endswith("_dark.png"):
            return sentinel_dark
        return None

    monkeypatch.setattr(
        preview, "_load_arranged_icon_from_candidates", _fake_loader
    )

    app = SimpleNamespace(_arranged_icon_cache={})

    entry = preview._ensure_arranged_icon_entry(app, "play")

    assert entry == {"light": sentinel_light, "dark": sentinel_dark}
    assert calls == [
        ("arranged_play_light.png", "arranged_play.png"),
        ("arranged_play_dark.png",),
    ]


def test_ensure_arranged_icon_entry_falls_back_to_light_for_dark_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_light = object()

    def _fake_loader(app: object, package: str, candidates: tuple[str, ...]):
        if candidates[0].endswith("_light.png"):
            return sentinel_light
        return None

    monkeypatch.setattr(
        preview, "_load_arranged_icon_from_candidates", _fake_loader
    )

    app = SimpleNamespace(_arranged_icon_cache={})

    entry = preview._ensure_arranged_icon_entry(app, "zoom_in")

    assert entry["light"] is sentinel_light
    assert entry["dark"] is sentinel_light


def test_load_arranged_icon_respects_theme_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel_light = object()
    sentinel_dark = object()

    monkeypatch.setattr(
        preview,
        "_ensure_arranged_icon_entry",
        lambda app, name: {"light": sentinel_light, "dark": sentinel_dark},
    )

    app = SimpleNamespace(_is_preview_theme_dark=lambda: True)

    assert preview._load_arranged_icon(app, "play") is sentinel_dark


def test_load_arranged_icon_falls_back_when_dark_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_light = object()

    monkeypatch.setattr(
        preview,
        "_ensure_arranged_icon_entry",
        lambda app, name: {"light": sentinel_light},
    )

    app = SimpleNamespace(_is_preview_theme_dark=lambda: True)

    assert preview._load_arranged_icon(app, "pause") is sentinel_light
