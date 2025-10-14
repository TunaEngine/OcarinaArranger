"""Command-file automation loop used by the Linux entrypoint."""

from __future__ import annotations

import itertools
import logging
import time
from pathlib import Path
from typing import Optional

from ocarina_gui.app import App

from .linux_shortcuts import (
    activate_theme,
    open_instrument_editor,
    open_licenses,
    select_tab,
)
from .linux_status import write_status

logger = logging.getLogger(__name__)


def dispatch_command(app: App, command: str) -> str:
    normalized = command.strip()
    if not normalized:
        return "ignored"
    if normalized == "open_instrument_layout":
        open_instrument_editor(app)
        return "handled"
    if normalized == "open_licenses":
        open_licenses(app)
        return "handled"
    if normalized.startswith("select_tab:"):
        _, _, label = normalized.partition(":")
        label = label.strip()
        select_tab(app, label or "convert")
        return "handled"
    if normalized.startswith("set_theme:"):
        _, _, theme = normalized.partition(":")
        theme_id = (theme or "").strip().lower()
        if theme_id in {"light", "dark"}:
            activate_theme(app, theme_id)
            return "handled"
        logger.warning("Unsupported Linux automation theme request: %s", command)
        return "ignored"
    logger.warning("Unsupported Linux automation command: %s", command)
    return "ignored"


def poll_command_file(app: App, command_file: Optional[Path], status_file: Optional[Path]) -> None:
    if command_file is None:
        return

    counter = itertools.count(1)

    def _process(command: str) -> None:
        sequence = next(counter)
        logger.info("Processing Linux E2E command: %s", command)
        try:
            outcome = dispatch_command(app, command)
            detail: Optional[str] = None
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            logger.exception("Linux automation command failed: %s", command)
            outcome = "error"
            detail = str(exc)
        write_status(
            status_file,
            last_command=command,
            last_command_status=outcome,
            last_command_counter=sequence,
            last_command_timestamp=time.time(),
            last_command_error=detail,
        )

    def _loop() -> None:
        try:
            content = command_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = ""
        except Exception:
            logger.exception("Failed to read Linux E2E command file")
            content = ""
        commands = [line.strip() for line in content.splitlines() if line.strip()]
        if commands:
            for command in commands:
                _process(command)
            try:
                command_file.write_text("", encoding="utf-8")
            except Exception:
                logger.exception("Unable to reset Linux E2E command file")
        app.after(200, _loop)

    app.after(200, _loop)


__all__ = ["dispatch_command", "poll_command_file"]

