from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ui.main_window.initialisation import MainWindowInitialisationMixin


class _InitialisationHarness(MainWindowInitialisationMixin):
    """Test double exposing ``MainWindowInitialisationMixin`` helpers."""

    def __init__(self) -> None:  # pragma: no cover - simple harness initialiser
        # ``MainWindowInitialisationMixin`` does not define ``__init__`` and the
        # real ``MainWindow`` base class would construct a ``tk.Tk`` instance.
        # The harness overrides ``__init__`` so tests can instantiate it without
        # touching Tkinter.
        pass


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Ensure tests observe predictable logging handlers."""

    # ``ensure_app_logging`` installs handlers on the root logger, so the tests
    # need a clean slate around each invocation to avoid leaking handlers.
    from shared import logging_config

    logging_config._reset_for_tests()
    try:
        yield
    finally:
        logging_config._reset_for_tests()


def test_initialise_preferences_logs_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    preferences = object()
    log_path = tmp_path / "ocarina.log"

    calls: list[Path] = []

    def fake_ensure_app_logging() -> Path:
        calls.append(log_path)
        return log_path

    monkeypatch.setattr("ui.main_window.initialisation.ensure_app_logging", fake_ensure_app_logging)
    monkeypatch.setattr("ui.main_window.initialisation.load_preferences", lambda: preferences)
    monkeypatch.setattr("ui.main_window.initialisation.get_app_version", lambda: "1.2.3")

    harness = _InitialisationHarness()

    with caplog.at_level(logging.INFO, logger="ui.main_window.initialisation"):
        result = harness._initialise_preferences()

    assert result is preferences
    assert harness._preferences is preferences
    assert harness._log_path == log_path
    assert calls == [log_path]
    assert any(
        record.getMessage() == "Starting Ocarina Arranger version 1.2.3"
        for record in caplog.records
    )


def test_initialise_preferences_writes_version_to_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_path = tmp_path / "ocarina.log"
    monkeypatch.setenv("OCARINA_LOG_FILE", str(log_path))
    monkeypatch.setattr("ui.main_window.initialisation.get_app_version", lambda: "9.9.9")

    harness = _InitialisationHarness()
    harness._initialise_preferences()

    for handler in logging.getLogger().handlers:
        handler.flush()

    contents = log_path.read_text(encoding="utf-8")
    assert "Starting Ocarina Arranger version 9.9.9" in contents
