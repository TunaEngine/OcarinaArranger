"""Helpers for constructing and scheduling the update service."""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable

from app.version import get_app_version
from services.update.constants import LOCAL_RELEASE_ENV
from services.update.installers import Installer, WindowsInstaller
from services.update.models import ReleaseInfo, UpdateError
from services.update.providers import GitHubReleaseProvider, LocalFolderReleaseProvider, ReleaseProvider
from services.update.service import UpdateService


_LOGGER = logging.getLogger(__name__)


def _build_provider_from_env() -> ReleaseProvider | None:
    local_dir = os.environ.get(LOCAL_RELEASE_ENV)
    if local_dir:
        folder = Path(local_dir)
        if folder.exists():
            _LOGGER.info("Using local update source at %s", folder)
            return LocalFolderReleaseProvider(folder)
        _LOGGER.warning("Configured local update directory does not exist: %s", folder)
    return GitHubReleaseProvider()


def build_update_service(installer: Installer | None = None) -> UpdateService | None:
    """Construct an :class:`UpdateService` for the current environment."""

    if not sys.platform.startswith("win"):
        _LOGGER.debug("Skipping update service build on non-Windows platform: %s", sys.platform)
        return None

    provider = _build_provider_from_env()
    if provider is None:
        _LOGGER.debug("No release provider configured")
        return None

    installer = installer or WindowsInstaller()
    current_version = get_app_version()
    return UpdateService(provider, installer, current_version=current_version)


def _run_update_check(
    service: UpdateService,
    on_release_available: Callable[[UpdateService, ReleaseInfo], None] | None,
    on_complete: Callable[[], None] | None,
) -> None:
    try:
        release = service.get_available_release()
    except UpdateError as exc:
        _LOGGER.warning("Automatic update failed: %s", exc)
        if on_complete:
            on_complete()
        return
    except Exception:  # pragma: no cover - defensive guard
        _LOGGER.exception("Unexpected error while checking for updates")
        if on_complete:
            on_complete()
        return

    if release is None:
        if on_complete:
            on_complete()
        return

    if on_release_available is not None:
        try:
            on_release_available(service, release)
        finally:
            if on_complete:
                on_complete()
        return

    try:
        service.download_and_install(release)
    except UpdateError as exc:
        _LOGGER.warning("Automatic update failed: %s", exc)
    except Exception:  # pragma: no cover - defensive guard
        _LOGGER.exception("Unexpected error while installing update")
    finally:
        if on_complete:
            on_complete()


def schedule_startup_update_check(
    installer: Installer | None = None,
    *,
    enabled: bool = True,
    on_release_available: Callable[[UpdateService, ReleaseInfo], None] | None = None,
    on_complete: Callable[[], None] | None = None,
) -> None:
    """Kick off an asynchronous update check if running on Windows."""

    if not enabled:
        _LOGGER.debug("Automatic updates disabled by user preference")
        return

    service = build_update_service(installer=installer)
    if service is None:
        return

    thread = threading.Thread(
        target=_run_update_check,
        args=(service, on_release_available, on_complete),
        name="ocarina-update",
        daemon=True,
    )
    thread.start()


__all__ = [
    "build_update_service",
    "schedule_startup_update_check",
]
