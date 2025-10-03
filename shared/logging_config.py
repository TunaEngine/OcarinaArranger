"""Central logging configuration for the desktop application.

This module configures Python's logging framework so that debug statements
emitted by the audio preview stack end up in a deterministic location that can
be shared when diagnosing issues.  The configuration favours a small footprint
and avoids duplicate handler registration when invoked repeatedly (as happens
in tests or when multiple windows are constructed).

Two environment variables allow customising where the log file is written:

``OCARINA_LOG_FILE``
    Absolute path to the log file that should be created.

``OCARINA_LOG_DIR``
    Directory where the default log file name will be created.  Ignored when
    ``OCARINA_LOG_FILE`` is present.

The helpers are intentionally light-weight so they can be exercised in tests
without interfering with unrelated logging configuration.
"""

from __future__ import annotations

import logging
import os
import re
from enum import Enum
from pathlib import Path
import sys
from typing import Iterable

_LOG_FILE_ENV = "OCARINA_LOG_FILE"
_LOG_DIR_ENV = "OCARINA_LOG_DIR"
_DEFAULT_DIRNAME = ".ocarina_arranger"
_DEFAULT_LOGNAME = "preview.log"
_CONFIGURED = False
_LOG_PATH: Path | None = None
_HANDLER_TAG = "_ocarina_logging_handler"
_FILE_HANDLER: logging.FileHandler | None = None

USER_PLACEHOLDER = "<user>"
USER_HOME_PLACEHOLDER = "<user_home>"


class LogVerbosity(str, Enum):
    """Verbosity levels supported by the application log file."""

    DISABLED = "disabled"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    VERBOSE = "verbose"


_VERBOSITY_LEVELS: dict[LogVerbosity, int] = {
    LogVerbosity.DISABLED: logging.CRITICAL + 1,
    LogVerbosity.ERROR: logging.ERROR,
    LogVerbosity.WARNING: logging.WARNING,
    LogVerbosity.INFO: logging.INFO,
    LogVerbosity.VERBOSE: logging.DEBUG,
}

_DEFAULT_VERBOSITY = LogVerbosity.INFO
_CURRENT_VERBOSITY = _DEFAULT_VERBOSITY


def _collect_username_candidates() -> set[str]:
    candidates: set[str] = set()
    home_name = Path.home().name
    if home_name:
        candidates.add(home_name)
    for env_var in ("USERNAME", "USER", "LOGNAME"):
        value = os.environ.get(env_var)
        if value:
            candidates.add(value)
    return {candidate.strip() for candidate in candidates if candidate and candidate.strip()}


def _collect_path_candidates() -> set[str]:
    candidates: set[str] = set()
    home_path = Path.home()
    home_str = str(home_path)
    if home_str:
        candidates.add(home_str)
    for env_var in ("HOME", "USERPROFILE"):
        value = os.environ.get(env_var)
        if value:
            candidates.add(os.path.expanduser(value))
    homedrive = os.environ.get("HOMEDRIVE")
    homepath = os.environ.get("HOMEPATH")
    if homedrive and homepath:
        candidates.add(os.path.join(homedrive, homepath))
    elif homepath:
        candidates.add(homepath)

    normalised = {
        os.path.normpath(candidate)
        for candidate in candidates
        if candidate and candidate not in {os.sep, ""}
    }
    return {candidate for candidate in normalised if candidate}


def _compile_username_pattern(username: str) -> re.Pattern[str]:
    escaped = re.escape(username)
    if any(character.isalnum() for character in username):
        return re.compile(rf"(?<!\\w){escaped}(?!\\w)", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _compile_path_pattern(path: str) -> re.Pattern[str]:
    flags = re.IGNORECASE if os.name == "nt" else 0
    return re.compile(re.escape(path), flags)


def _build_redaction_patterns() -> list[tuple[re.Pattern[str], str]]:
    patterns: list[tuple[re.Pattern[str], str]] = []
    seen: set[tuple[str, str]] = set()

    for path in _collect_path_candidates():
        variants = {path}
        alternate = path.replace("\\", "/")
        if alternate != path:
            variants.add(alternate)
        backslashed = path.replace("/", "\\")
        if backslashed != path:
            variants.add(backslashed)
        for variant in variants:
            normalised_variant = os.path.normpath(variant)
            if normalised_variant in {os.sep, ""}:
                continue
            key = (
                normalised_variant.lower() if os.name == "nt" else normalised_variant,
                USER_HOME_PLACEHOLDER,
            )
            if key in seen:
                continue
            patterns.append((_compile_path_pattern(normalised_variant), USER_HOME_PLACEHOLDER))
            seen.add(key)

    usernames = sorted(_collect_username_candidates(), key=len, reverse=True)
    for username in usernames:
        patterns.append((_compile_username_pattern(username), USER_PLACEHOLDER))

    return patterns


_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(_build_redaction_patterns())


def _sanitize_text(message: str) -> str:
    if not message or not _REDACTION_PATTERNS:
        return message
    redacted = message
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return _sanitize_text(formatted)


def ensure_app_logging() -> Path:
    """Configure the root logger for the desktop application.

    The first invocation sets up a rotating file handler (at DEBUG level) and a
    console handler (INFO level, only when stderr is interactive).  Subsequent
    calls are no-ops and return the already configured log file path.

    Returns
    -------
    Path
        Location of the log file that records application diagnostics.
    """

    global _CONFIGURED, _LOG_PATH

    if _CONFIGURED and _LOG_PATH is not None:
        return _LOG_PATH

    log_path = _resolve_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = _RedactingFormatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(_VERBOSITY_LEVELS[_CURRENT_VERBOSITY])
    file_handler.setFormatter(formatter)
    setattr(file_handler, _HANDLER_TAG, True)
    root.addHandler(file_handler)
    global _FILE_HANDLER
    _FILE_HANDLER = file_handler

    if _should_log_to_stderr(root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        setattr(stream_handler, _HANDLER_TAG, True)
        root.addHandler(stream_handler)

    _CONFIGURED = True
    _LOG_PATH = log_path

    logging.getLogger(__name__).info(
        "Writing application logs to %s (verbosity=%s)",
        log_path,
        _CURRENT_VERBOSITY.value,
    )
    return log_path


def set_file_log_verbosity(verbosity: LogVerbosity | str) -> None:
    """Adjust the minimum severity recorded in the application log file."""

    global _CURRENT_VERBOSITY

    if isinstance(verbosity, str):
        try:
            verbosity = LogVerbosity(verbosity.lower())
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported log verbosity: {verbosity}") from exc

    ensure_app_logging()
    handler = _FILE_HANDLER
    if handler is None:  # pragma: no cover - defensive
        return

    _CURRENT_VERBOSITY = verbosity
    handler.setLevel(_VERBOSITY_LEVELS[verbosity])
    logging.getLogger(__name__).info("File log verbosity set to %s", verbosity.value)


def get_file_log_verbosity() -> LogVerbosity:
    """Return the current verbosity level for the application log file."""

    return _CURRENT_VERBOSITY


def _resolve_log_path() -> Path:
    env_file = os.environ.get(_LOG_FILE_ENV)
    if env_file:
        return Path(env_file).expanduser()

    env_dir = os.environ.get(_LOG_DIR_ENV)
    if env_dir:
        return Path(env_dir).expanduser() / _DEFAULT_LOGNAME

    home = Path.home()
    return home / _DEFAULT_DIRNAME / "logs" / _DEFAULT_LOGNAME


def _should_log_to_stderr(handlers: Iterable[logging.Handler]) -> bool:
    if not hasattr(sys, "stderr"):
        return False
    stderr = sys.stderr
    is_tty = getattr(stderr, "isatty", None)
    if callable(is_tty):
        try:
            if not is_tty():
                return False
        except Exception:  # pragma: no cover - defensive against odd stderr
            return False
    else:
        return False

    for handler in handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is stderr:
            return False
    return True


def _reset_for_tests() -> None:
    """Remove handlers installed by :func:`ensure_app_logging`."""

    global _CONFIGURED, _LOG_PATH, _FILE_HANDLER, _CURRENT_VERBOSITY

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_TAG, False):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # pragma: no cover - close should rarely fail
                pass

    _CONFIGURED = False
    _LOG_PATH = None
    _FILE_HANDLER = None
    _CURRENT_VERBOSITY = _DEFAULT_VERBOSITY

