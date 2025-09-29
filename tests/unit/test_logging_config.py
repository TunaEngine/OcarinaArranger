from __future__ import annotations

import logging
from pathlib import Path

import pytest

from shared import logging_config


def _flush_managed_handlers() -> None:
    for handler in logging.getLogger().handlers:
        if getattr(handler, logging_config._HANDLER_TAG, False):  # type: ignore[attr-defined]
            handler.flush()


@pytest.fixture(autouse=True)
def reset_logging():
    logging_config._reset_for_tests()
    try:
        yield
    finally:
        logging_config._reset_for_tests()


def test_logging_creates_file_and_records_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))

    log_path = logging_config.ensure_app_logging()
    assert logging_config.get_file_log_verbosity() == logging_config.LogVerbosity.ERROR
    logging.getLogger("viewmodels.preview_playback_viewmodel").debug("debug message")
    logging.getLogger("viewmodels.preview_playback_viewmodel").error("error message")
    _flush_managed_handlers()

    contents = log_path.read_text(encoding="utf-8")
    assert "debug message" not in contents
    assert "error message" in contents


def test_logging_configuration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))

    first_path = logging_config.ensure_app_logging()
    second_path = logging_config.ensure_app_logging()

    assert first_path == second_path
    managed_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, logging_config._HANDLER_TAG, False)  # type: ignore[attr-defined]
    ]

    # Only the file handler should be installed during tests (stderr is not a tty).
    assert len(managed_handlers) == 1
    assert isinstance(managed_handlers[0], logging.FileHandler)
    assert Path(managed_handlers[0].baseFilename) == first_path


def test_can_adjust_file_log_verbosity(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))

    log_path = logging_config.ensure_app_logging()
    logging_config.set_file_log_verbosity(logging_config.LogVerbosity.VERBOSE)
    logging.getLogger("tests.logging").debug("debug message")
    logging.getLogger("tests.logging").info("info message")
    logging.getLogger("tests.logging").error("error message")
    _flush_managed_handlers()

    contents = log_path.read_text(encoding="utf-8")
    assert "debug message" in contents
    assert "info message" in contents
    assert "error message" in contents
    assert logging_config.get_file_log_verbosity() == logging_config.LogVerbosity.VERBOSE


def test_disabling_file_logging_suppresses_output(tmp_path, monkeypatch):
    monkeypatch.setenv("OCARINA_LOG_DIR", str(tmp_path))

    log_path = logging_config.ensure_app_logging()
    logging_config.set_file_log_verbosity(logging_config.LogVerbosity.DISABLED)
    _flush_managed_handlers()
    initial_size = log_path.stat().st_size

    logging.getLogger("tests.logging").critical("critical message")
    _flush_managed_handlers()

    assert log_path.stat().st_size == initial_size
