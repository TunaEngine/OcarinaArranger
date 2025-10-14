"""Utilities for acquiring and validating release installer assets."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from services.update.hashing import parse_hash_text
from services.update.models import ReleaseInfo, UpdateError


_LOGGER = logging.getLogger(__name__)

__all__ = ["obtain_installer_asset", "resolve_expected_hash"]


def obtain_installer_asset(release: ReleaseInfo) -> Path:
    """Return a local filesystem path to the installer payload for ``release``."""

    if release.source_path is not None:
        _LOGGER.info(
            "Copying installer for version %s from local source %s",
            release.version,
            release.source_path,
        )
        target_dir = Path(tempfile.mkdtemp(prefix="ocarina-update-"))
        target_path = target_dir / release.asset_name
        shutil.copy2(release.source_path, target_path)
        return target_path

    if release.download_url is None:
        raise UpdateError("Release is missing a download URL")

    _LOGGER.info(
        "Downloading installer for version %s from %s",
        release.version,
        release.download_url,
    )
    target_dir = Path(tempfile.mkdtemp(prefix="ocarina-update-"))
    target_path = target_dir / release.asset_name
    try:
        from urllib.request import urlopen

        with urlopen(release.download_url) as response, target_path.open("wb") as destination:  # nosec - HTTPS
            shutil.copyfileobj(response, destination)
    except OSError as exc:
        raise UpdateError(f"Failed to download installer: {exc}") from exc
    _LOGGER.debug("Downloaded installer to %s", target_path)
    return target_path


def resolve_expected_hash(release: ReleaseInfo) -> str:
    """Return the expected SHA256 hash for ``release``'s installer asset."""

    if release.hash_value:
        _LOGGER.debug("Using inline hash for version %s", release.version)
        return release.hash_value.strip()
    if release.hash_path is not None:
        try:
            _LOGGER.debug(
                "Reading hash value for version %s from %s",
                release.version,
                release.hash_path,
            )
            return parse_hash_text(release.hash_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise UpdateError(f"Failed to read hash file: {exc}") from exc
    if release.hash_url is not None:
        try:
            _LOGGER.debug(
                "Downloading hash file for version %s from %s",
                release.version,
                release.hash_url,
            )
            from urllib.request import urlopen

            with urlopen(release.hash_url) as response:
                text = response.read().decode("utf-8")
        except OSError as exc:
            raise UpdateError(f"Failed to download hash file: {exc}") from exc
        return parse_hash_text(text)
    raise UpdateError("Release metadata missing security hash")
