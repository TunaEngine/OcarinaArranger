"""Public API for the update service package."""

from __future__ import annotations

from services.update.builder import build_update_service, schedule_startup_update_check
from services.update.constants import (
    API_URL,
    GITHUB_REPO,
    INSTALL_ROOT_ENV,
    LOCAL_RELEASE_ENV,
    MAX_ARCHIVE_ENTRIES,
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_TOTAL_BYTES,
    MAX_COMPRESSION_RATIO,
    PREFERRED_EXECUTABLE_NAMES,
    UPDATE_FAILURE_MARKER_SUFFIX,
    WINDOWS_ARCHIVE_EXTENSIONS,
    WINDOWS_EXECUTABLE_EXTENSIONS,
)
from services.update.installers import Installer, WindowsInstaller
from services.update.models import InstallationPlan, ReleaseInfo, UpdateError
from services.update.providers import GitHubReleaseProvider, LocalFolderReleaseProvider, ReleaseProvider
from services.update.service import UpdateService

__all__ = [
    "API_URL",
    "GITHUB_REPO",
    "LOCAL_RELEASE_ENV",
    "INSTALL_ROOT_ENV",
    "MAX_ARCHIVE_ENTRIES",
    "MAX_ARCHIVE_FILE_SIZE",
    "MAX_ARCHIVE_TOTAL_BYTES",
    "MAX_COMPRESSION_RATIO",
    "PREFERRED_EXECUTABLE_NAMES",
    "UPDATE_FAILURE_MARKER_SUFFIX",
    "WINDOWS_ARCHIVE_EXTENSIONS",
    "WINDOWS_EXECUTABLE_EXTENSIONS",
    "Installer",
    "WindowsInstaller",
    "InstallationPlan",
    "ReleaseInfo",
    "UpdateError",
    "GitHubReleaseProvider",
    "LocalFolderReleaseProvider",
    "ReleaseProvider",
    "UpdateService",
    "build_update_service",
    "schedule_startup_update_check",
]
