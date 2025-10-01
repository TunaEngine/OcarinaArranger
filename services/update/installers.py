"""Installer implementations for platform-specific behaviour."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Protocol

from services.update.models import InstallationPlan

_LOGGER = logging.getLogger(__name__)


class Installer(Protocol):
    """Protocol describing the platform-specific installation routine."""

    def install(self, plan: InstallationPlan, version: str) -> None:
        """Execute the downloaded installer described by ``plan``."""


class WindowsInstaller:
    """Launch the downloaded installer and exit the application."""

    def __init__(self, *, exit_after_launch: bool = True) -> None:
        self._exit_after_launch = exit_after_launch

    def install(self, plan: InstallationPlan, version: str) -> None:  # pragma: no cover - requires Windows
        _LOGGER.info("Launching installer for version %s", version)
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":  # pragma: no cover - exercised on Windows
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
                startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            if creationflags:
                popen_kwargs["creationflags"] = creationflags
            if startupinfo is not None:
                popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs.setdefault("stdin", subprocess.DEVNULL)
            popen_kwargs.setdefault("stdout", subprocess.DEVNULL)
            popen_kwargs.setdefault("stderr", subprocess.DEVNULL)
        try:
            subprocess.Popen(
                list(plan.command),
                cwd=str(plan.working_directory) if plan.working_directory else None,
                **popen_kwargs,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to launch installer: {exc}") from exc
        if self._exit_after_launch:
            logging.shutdown()
            os._exit(0)
