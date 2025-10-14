"""Test helpers for driving the Linux automation command channel."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def read_status(status_file: Path) -> dict[str, object]:
    try:
        payload = status_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        return json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        logger.debug("Unable to decode Linux status file %s", status_file)
        return {}


def wait_for_status(
    status_file: Path,
    key: str,
    expected: str,
    *,
    timeout: float = 15.0,
    poll_interval: float = 0.1,
) -> None:
    deadline = time.monotonic() + timeout
    last_payload: dict[str, object] | None = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = read_status(status_file)
        except Exception as exc:  # pragma: no cover - diagnostic aid only
            last_error = exc
            time.sleep(poll_interval)
            continue
        last_payload = payload
        value = str(payload.get(key, "")) if payload else ""
        if value == expected:
            return
        if value == "error":
            detail = payload.get("detail", "<no detail>") if payload else "<no detail>"
            raise AssertionError(
                f"Preview status reported error before reaching '{expected}': {detail}"
            )
        time.sleep(poll_interval)
    detail = f" status_file={status_file}"
    if last_payload is not None:
        detail += f" last_payload={last_payload!r}"
    if last_error is not None:
        detail += f" last_error={last_error!r}"
    raise AssertionError(
        f"Timed out waiting for status '{key}={expected}' after {timeout}s.{detail}"
    )


def wait_for_command_ack(
    status_file: Path,
    *,
    expected_command: str,
    previous_counter: int,
    timeout: float = 10.0,
    poll_interval: float = 0.1,
) -> None:
    deadline = time.monotonic() + timeout
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        payload = read_status(status_file)
        last_payload = payload or last_payload
        counter = int(payload.get("last_command_counter", 0)) if payload else 0
        command = str(payload.get("last_command", "")) if payload else ""
        if counter > previous_counter and command == expected_command:
            status = str(payload.get("last_command_status", "handled"))
            if status == "handled":
                return
            if status == "ignored":
                raise AssertionError(
                    f"Linux automation ignored command '{expected_command}'"
                )
            if status == "error":
                detail = payload.get("last_command_error", "<no detail>")
                raise AssertionError(
                    f"Linux automation reported error for '{expected_command}': {detail}"
                )
            return
        time.sleep(poll_interval)
    raise AssertionError(
        "Timed out waiting for Linux automation command acknowledgement: "
        f"{expected_command}. last_payload={last_payload!r}"
    )


def invoke_automation_command(command_file: Path, status_file: Path, command: str) -> None:
    command = command.strip()
    if not command:
        raise AssertionError("Automation command must be non-empty")
    previous_counter = int(read_status(status_file).get("last_command_counter", 0))
    command_file.write_text(f"{command}\n", encoding="utf-8")
    wait_for_command_ack(
        status_file,
        expected_command=command,
        previous_counter=previous_counter,
    )


__all__ = [
    "invoke_automation_command",
    "read_status",
    "wait_for_command_ack",
    "wait_for_status",
]

