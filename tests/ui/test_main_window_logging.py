import json

import pytest

from ocarina_gui.preferences import Preferences
from shared import logging_config
from ui.logging_preferences import (
    apply_log_verbosity,
    persist_log_verbosity,
    restore_log_verbosity_preference,
)


@pytest.fixture(autouse=True)
def reset_logging():
    logging_config._reset_for_tests()
    try:
        yield
    finally:
        logging_config._reset_for_tests()


def test_restore_log_verbosity_preference_applies_saved_level(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))
    logging_config.ensure_app_logging()
    restored = restore_log_verbosity_preference(
        Preferences(log_verbosity=logging_config.LogVerbosity.ERROR.value)
    )

    assert restored is logging_config.LogVerbosity.ERROR
    assert logging_config.get_file_log_verbosity() is logging_config.LogVerbosity.ERROR


def test_restore_log_verbosity_ignores_invalid_level(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))
    logging_config.ensure_app_logging()
    restored = restore_log_verbosity_preference(Preferences(log_verbosity="invalid"))

    assert restored is None
    assert logging_config.get_file_log_verbosity() is logging_config.LogVerbosity.ERROR


def test_persist_log_verbosity_writes_preference(tmp_path, monkeypatch):
    pref_path = tmp_path / "prefs.json"
    monkeypatch.setenv("OCARINA_GUI_PREFERENCES_PATH", str(pref_path))
    persist_log_verbosity(logging_config.LogVerbosity.WARNING)

    payload = json.loads(pref_path.read_text(encoding="utf-8"))
    assert payload["log_verbosity"] == "warning"


def test_apply_log_verbosity_reports_failure(monkeypatch):
    captured: list[tuple[logging_config.LogVerbosity, Exception]] = []

    def fake_set(verbosity: logging_config.LogVerbosity) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("ui.logging_preferences.set_file_log_verbosity", fake_set)

    success = apply_log_verbosity(
        logging_config.LogVerbosity.INFO,
        on_failure=lambda verbosity, exc: captured.append((verbosity, exc)),
    )

    assert not success
    assert captured and isinstance(captured[0][1], RuntimeError)
