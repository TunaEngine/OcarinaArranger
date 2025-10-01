"""Release provider implementations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Protocol
from urllib.error import URLError
from urllib.request import urlopen

from services.update.constants import (
    API_URL,
    DEFAULT_ARCHIVE_ENTRY_POINT,
    WINDOWS_ARCHIVE_EXTENSIONS,
)
from services.update.models import ReleaseInfo


_LOGGER = logging.getLogger(__name__)


class ReleaseProvider(Protocol):
    """Protocol describing release metadata providers."""

    def fetch_latest(self) -> ReleaseInfo | None:
        """Return the newest available release or ``None`` when unavailable."""


class GitHubReleaseProvider:
    """Fetch release metadata from the GitHub Releases API."""

    def __init__(self, api_url: str = API_URL) -> None:
        self._api_url = api_url

    def fetch_latest(self) -> ReleaseInfo | None:
        try:
            with urlopen(self._api_url) as response:  # nosec - GitHub API over HTTPS
                data = json.load(response)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            _LOGGER.debug("Failed to query GitHub releases: %s", exc)
            return None

        version = str(data.get("tag_name") or data.get("name") or "").strip()
        if not version:
            return None
        version = version.lstrip("v")

        assets = data.get("assets") or []
        installer_asset = self._select_windows_asset(assets)
        if installer_asset is None:
            return None

        sha_asset = self._select_sha_asset(assets, installer_asset["name"])

        _LOGGER.info(
            "GitHub release %s includes installer asset %s",
            version,
            installer_asset.get("name"),
        )

        return ReleaseInfo(
            version=version,
            asset_name=str(installer_asset.get("name", "installer")),
            download_url=str(installer_asset.get("browser_download_url")),
            hash_url=str(sha_asset.get("browser_download_url")) if sha_asset else None,
            release_notes=_clean_release_notes(data.get("body")),
            entry_point=DEFAULT_ARCHIVE_ENTRY_POINT,
        )

    def _select_windows_asset(self, assets: Iterable[dict]) -> dict | None:
        for asset in assets:
            name = str(asset.get("name", "")).lower()
            if name.endswith(WINDOWS_ARCHIVE_EXTENSIONS):
                return asset
        return None

    def _select_sha_asset(self, assets: Iterable[dict], installer_name: str) -> dict | None:
        expected_prefix = installer_name.split(".")[0]
        for asset in assets:
            name = str(asset.get("name", ""))
            lower = name.lower()
            if not lower.endswith(".sha256"):
                continue
            if name.startswith(installer_name) or name.startswith(expected_prefix):
                return asset
        for asset in assets:
            if str(asset.get("name", "")).lower().endswith(".sha256"):
                return asset
        return None


class LocalFolderReleaseProvider:
    """Serve release metadata from a local directory for testing."""

    def __init__(self, folder: Path) -> None:
        self._folder = Path(folder)

    def fetch_latest(self) -> ReleaseInfo | None:
        metadata_path = self._folder / "release.json"
        if not metadata_path.exists():
            _LOGGER.debug("Local release metadata missing: %s", metadata_path)
            return None
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _LOGGER.debug("Failed to read local release metadata: %s", exc)
            return None

        version = str(data.get("version", "")).strip()
        installer_name = str(data.get("installer", "")).strip()
        if not version or not installer_name:
            _LOGGER.debug("Local release metadata incomplete: version=%s installer=%s", version, installer_name)
            return None

        asset_path = self._folder / installer_name
        if not asset_path.exists():
            _LOGGER.debug("Local installer missing: %s", asset_path)
            return None

        hash_value = data.get("sha256")
        hash_file = data.get("sha256_file")
        hash_path = (self._folder / str(hash_file)) if hash_file else None

        entry_point = _clean_entry_point(data.get("entry_point") or data.get("installer_entry"))
        if entry_point is None:
            entry_point = DEFAULT_ARCHIVE_ENTRY_POINT

        _LOGGER.info(
            "Local release %s will supply installer %s",
            version,
            installer_name,
        )

        return ReleaseInfo(
            version=version,
            asset_name=installer_name,
            source_path=asset_path,
            hash_value=str(hash_value) if hash_value else None,
            hash_path=hash_path,
            release_notes=_clean_release_notes(data.get("release_notes") or data.get("notes")),
            entry_point=entry_point,
        )


def _clean_release_notes(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    return cleaned or None


def _clean_entry_point(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().strip("/\\")
    if not cleaned:
        return None
    return cleaned.replace("\\", "/")
