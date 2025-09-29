from __future__ import annotations

from importlib import resources

from app.version import get_app_version


def _reset_cache() -> None:
    get_app_version.cache_clear()  # type: ignore[attr-defined]


def test_get_app_version_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("OCARINA_APP_VERSION", "v1.2.3")
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    _reset_cache()

    assert get_app_version() == "1.2.3"


def test_get_app_version_falls_back_to_version_file(monkeypatch) -> None:
    monkeypatch.delenv("OCARINA_APP_VERSION", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    _reset_cache()

    version_file = resources.files("app").joinpath("VERSION")
    expected = version_file.read_text(encoding="utf-8").strip()
    assert expected
    assert get_app_version() == expected
