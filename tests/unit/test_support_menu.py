from __future__ import annotations

import types

import pytest

from ui.main_window.menus import support


@pytest.fixture(autouse=True)
def _patch_support_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(support, "_SUPPORT_FORM_ID", "FORM_ID", raising=False)
    monkeypatch.setattr(support, "_ROUTER_QUESTION_ID", "ROUTER_ID", raising=False)
    monkeypatch.setattr(support, "_APP_VERSION_QUESTION_ID", "APP_VERSION_ID", raising=False)
    monkeypatch.setattr(support, "_OS_QUESTION_ID", "OS_ID", raising=False)
    monkeypatch.setattr(support, "get_app_version", lambda: "1.2.3", raising=False)


@pytest.fixture
def platform_stub(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    stub = types.SimpleNamespace(system=lambda: "TestOS", release=lambda: "2024.4")
    monkeypatch.setattr(support.platform, "system", stub.system)
    monkeypatch.setattr(support.platform, "release", stub.release)
    return stub


def test_build_support_form_url(platform_stub: types.SimpleNamespace) -> None:
    mixin = support.SupportMenuMixin()
    url = mixin._build_support_form_url("Bug report")
    assert (
        url
        == "https://docs.google.com/forms/d/e/FORM_ID/viewform?usp=pp_url"
        "&entry.ROUTER_ID=Bug+report&entry.APP_VERSION_ID=1.2.3&entry.OS_ID=TestOS+2024.4"
    )


def test_detect_platform_label_falls_back_to_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(support.platform, "system", lambda: "")
    monkeypatch.setattr(support.platform, "release", lambda: "kernel-1.0")
    mixin = support.SupportMenuMixin()
    assert mixin._detect_platform_label() == "kernel-1.0"


def test_open_support_form_logs_warning_when_browser_rejects(
    platform_stub: types.SimpleNamespace, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_url: dict[str, str] = {}

    def _fake_open(url: str, *, new: int, autoraise: bool) -> bool:
        captured_url["value"] = url
        return False

    monkeypatch.setattr(support.webbrowser, "open", _fake_open)
    mixin = support.SupportMenuMixin()

    with caplog.at_level("WARNING"):
        mixin._report_problem_command()

    assert captured_url["value"].endswith(
        "entry.ROUTER_ID=Bug+report&entry.APP_VERSION_ID=1.2.3&entry.OS_ID=TestOS+2024.4"
    )
    assert "Support form URL did not open" in caplog.text
