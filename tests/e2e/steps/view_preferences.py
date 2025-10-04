from __future__ import annotations

from typing import Dict

from pytest_bdd import given, parsers, then, when

from shared.logging_config import LogVerbosity

from tests.e2e.harness import E2EHarness
from tests.e2e.support.menu import invoke_menu_path


def _select_theme(arranger_app: E2EHarness, theme_label: str) -> None:
    invoke_menu_path(arranger_app.window, "View", theme_label)


@when(parsers.re(r'^the user selects the "(?P<theme_label>[^"]+)" theme from the View menu$'))
def select_theme_regex(arranger_app: E2EHarness, theme_label: str) -> None:
    _select_theme(arranger_app, theme_label)


@when('the user selects the "Dark" theme from the View menu')
def select_theme_dark(arranger_app: E2EHarness) -> None:
    _select_theme(arranger_app, "Dark")


def _assert_active_theme(arranger_app: E2EHarness, theme_label: str) -> None:
    window = arranger_app.window
    assert window.theme_name.get() == theme_label
    choices: Dict[str, str] = {choice.name: choice.theme_id for choice in window._theme_choices}
    expected_theme_id = choices[theme_label]
    assert window.theme_id.get() == expected_theme_id


@then(parsers.re(r'^the active theme is "(?P<theme_label>[^"]+)"$'))
def assert_active_theme_regex(arranger_app: E2EHarness, theme_label: str) -> None:
    _assert_active_theme(arranger_app, theme_label)


@then('the active theme is "Dark"')
def assert_active_theme_dark(arranger_app: E2EHarness) -> None:
    _assert_active_theme(arranger_app, "Dark")


def _assert_theme_preference(arranger_app: E2EHarness, theme_id: str) -> None:
    assert arranger_app.saved_preferences, "No preferences were saved"
    assert arranger_app.saved_preferences[-1].theme_id == theme_id
    assert arranger_app.preferences.theme_id == theme_id


@then(parsers.re(r'^the theme preference was saved as "(?P<theme_id>[^"]+)"$'))
def assert_theme_preference_regex(arranger_app: E2EHarness, theme_id: str) -> None:
    _assert_theme_preference(arranger_app, theme_id)


@then('the theme preference was saved as "dark"')
def assert_theme_preference_dark(arranger_app: E2EHarness) -> None:
    _assert_theme_preference(arranger_app, "dark")


@given("log verbosity changes are tracked")
def track_log_verbosity(arranger_app: E2EHarness, monkeypatch) -> None:
    apply_calls: list[LogVerbosity] = []
    persist_calls: list[LogVerbosity] = []
    window = arranger_app.window
    window._test_log_apply_calls = apply_calls  # type: ignore[attr-defined]
    window._test_log_persist_calls = persist_calls  # type: ignore[attr-defined]

    def _fake_apply(verbosity: LogVerbosity, *, on_failure=None):  # noqa: ANN001 - signature parity
        apply_calls.append(verbosity)
        return True

    def _fake_persist(verbosity: LogVerbosity) -> None:
        persist_calls.append(verbosity)

    monkeypatch.setattr("ui.main_window.menus.logging_menu.apply_log_verbosity", _fake_apply)
    monkeypatch.setattr("ui.main_window.menus.logging_menu.persist_log_verbosity", _fake_persist)


def _select_log_verbosity(arranger_app: E2EHarness, label: str) -> None:
    invoke_menu_path(arranger_app.window, "Logs", label)


@when(parsers.re(r'^the user selects "(?P<label>[^"]+)" log verbosity from the Logs menu$'))
def select_log_verbosity_regex(arranger_app: E2EHarness, label: str) -> None:
    _select_log_verbosity(arranger_app, label)


@when('the user selects "Verbose" log verbosity from the Logs menu')
def select_log_verbosity_verbose(arranger_app: E2EHarness) -> None:
    _select_log_verbosity(arranger_app, "Verbose")


def _assert_log_apply(arranger_app: E2EHarness, verbosity: str) -> None:
    recorded = getattr(arranger_app.window, "_test_log_apply_calls", [])
    assert recorded, "No log verbosity apply calls were recorded"
    assert recorded[-1].value == verbosity


@then(parsers.re(r'^log verbosity was applied as "(?P<verbosity>[^"]+)"$'))
def assert_log_apply_regex(arranger_app: E2EHarness, verbosity: str) -> None:
    _assert_log_apply(arranger_app, verbosity)


@then('log verbosity was applied as "verbose"')
def assert_log_apply_verbose(arranger_app: E2EHarness) -> None:
    _assert_log_apply(arranger_app, "verbose")


def _assert_log_persist(arranger_app: E2EHarness, verbosity: str) -> None:
    recorded = getattr(arranger_app.window, "_test_log_persist_calls", [])
    assert recorded, "No log verbosity persist calls were recorded"
    assert recorded[-1].value == verbosity


@then(parsers.re(r'^the log verbosity preference was saved as "(?P<verbosity>[^"]+)"$'))
def assert_log_persist_regex(arranger_app: E2EHarness, verbosity: str) -> None:
    _assert_log_persist(arranger_app, verbosity)


@then('the log verbosity preference was saved as "verbose"')
def assert_log_persist_verbose(arranger_app: E2EHarness) -> None:
    _assert_log_persist(arranger_app, "verbose")
