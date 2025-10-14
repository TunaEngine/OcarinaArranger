"""Build installation plans for downloaded installer assets."""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from pathlib import Path

import datetime as _datetime_module

from services.update.archive import ArchiveExtraction, extract_archive, locate_archive_entry
from services.update.constants import WINDOWS_ARCHIVE_EXTENSIONS
from services.update.models import InstallationPlan, ReleaseInfo, UpdateError
from services.update.recovery import find_install_root, get_failure_marker_path
from services.update.powershell_script import write_portable_update_script


_LOGGER = logging.getLogger(__name__)

__all__ = ["build_installation_plan"]


def build_installation_plan(asset_path: Path, release: ReleaseInfo) -> InstallationPlan:
    """Return an :class:`InstallationPlan` for ``asset_path``."""

    suffix = asset_path.suffix.lower()
    is_archive = suffix in WINDOWS_ARCHIVE_EXTENSIONS
    if not is_archive:
        try:
            is_archive = zipfile.is_zipfile(asset_path)
        except OSError:
            is_archive = False
    if not is_archive:
        _LOGGER.info("Installer %s is an executable payload", asset_path.name)
        return InstallationPlan((str(asset_path),))

    return _plan_archive_installation(asset_path, release)


def _plan_archive_installation(archive_path: Path, release: ReleaseInfo) -> InstallationPlan:
    _LOGGER.info("Preparing archive installation from %s", archive_path)
    extract_dir = extract_archive(archive_path)
    extraction = locate_archive_entry(extract_dir, release.entry_point)
    install_root = _resolve_install_root()
    stage_dir, final_executable = _stage_portable_update(extraction, install_root)
    failure_marker = get_failure_marker_path(install_root)
    log_path = _determine_script_log_path(install_root)
    script_path = write_portable_update_script()
    script_working_dir = script_path.parent
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _LOGGER.info("Installer script output will be appended to %s", log_path)
    command: list[str] = [
        "powershell",
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-ProcessId",
        str(os.getpid()),
        "-StagePath",
        str(stage_dir),
        "-InstallPath",
        str(install_root),
        "-ExecutablePath",
        str(final_executable),
    ]
    if log_path is not None:
        command.extend(["-LogPath", str(log_path)])
    command.extend(["-FailureMarkerPath", str(failure_marker)])
    return InstallationPlan(tuple(command), working_directory=script_working_dir)


def _determine_script_log_path(install_root: Path) -> Path | None:
    log_path = _find_primary_log_file()
    if log_path is not None:
        return log_path
    try:
        from services.update import service as update_service  # type: ignore
    except ImportError:  # pragma: no cover - fallback for isolated use
        datetime_module = _datetime_module
    else:
        datetime_module = getattr(update_service, "datetime", _datetime_module)
    timestamp = datetime_module.datetime.now().strftime("%Y%m%d-%H%M%S")
    return install_root.parent / f"{install_root.name}.update.{timestamp}.log"


def _resolve_install_root() -> Path:
    install_root = find_install_root()
    if install_root is None:
        raise UpdateError("Automatic updates require a packaged application build")
    _LOGGER.debug("Resolved packaged install root to %s", install_root)
    return install_root


def _stage_portable_update(
    extraction: ArchiveExtraction, install_root: Path
) -> tuple[Path, Path]:
    parts = extraction.relative_entry.parts
    package_root = extraction.root
    relative_within_package = extraction.relative_entry
    if parts:
        first_component = extraction.root / parts[0]
        if first_component.is_dir():
            package_root = first_component
            if len(parts) > 1:
                relative_within_package = Path(*parts[1:])
            else:
                relative_within_package = Path(parts[0])

    stage_dir = install_root.parent / f"{install_root.name}.update"
    stage_dir.parent.mkdir(parents=True, exist_ok=True)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    _LOGGER.debug(
        "Copying extracted package from %s to staging directory %s",
        package_root,
        stage_dir,
    )
    shutil.copytree(package_root, stage_dir)

    shutil.rmtree(extraction.root, ignore_errors=True)

    final_executable = install_root / relative_within_package
    _LOGGER.info(
        "Staged portable update at %s with executable %s",
        stage_dir,
        final_executable,
    )
    return stage_dir, final_executable


def _find_primary_log_file() -> Path | None:
    """Return the application log file if one is configured."""

    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and hasattr(handler, "baseFilename"):
            if getattr(handler, "_ocarina_logging_handler", False):
                return Path(handler.baseFilename)
    return None
