"""Release provider implementations."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable, Iterator, Protocol
from urllib.error import URLError
from urllib.request import urlopen

from services.update.constants import (
    API_URL,
    API_RELEASES_URL,
    DEFAULT_ARCHIVE_ENTRY_POINT,
    UPDATE_CHANNELS,
    UPDATE_CHANNEL_BETA,
    UPDATE_CHANNEL_STABLE,
    WINDOWS_ARCHIVE_EXTENSIONS,
    WINDOWS_EXECUTABLE_EXTENSIONS,
)
from services.update.models import ReleaseInfo


_LOGGER = logging.getLogger(__name__)

_PLATFORM_SKIP_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(linux|darwin|mac(?:osx?)?|osx)(?:[^a-z0-9]|$)"
)


class ReleaseProvider(Protocol):
    """Protocol describing release metadata providers."""

    def fetch_latest(self) -> ReleaseInfo | None:
        """Return the newest available release or ``None`` when unavailable."""


class GitHubReleaseProvider:
    """Fetch release metadata from the GitHub Releases API."""

    def __init__(
        self,
        api_url: str = API_URL,
        *,
        releases_url: str = API_RELEASES_URL,
        channel: str = UPDATE_CHANNEL_STABLE,
    ) -> None:
        self._api_url = api_url
        self._releases_url = releases_url
        self._channel = self._normalise_channel(channel)

    def fetch_latest(self) -> ReleaseInfo | None:
        for release in self._candidate_releases():
            if not self._is_channel_compatible(release):
                continue
            info = self._build_release_info(release)
            if info is not None:
                return info
        return None

    def _request_json(self, url: str) -> dict | None:
        try:
            with urlopen(url) as response:  # nosec - GitHub API over HTTPS
                return json.load(response)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            _LOGGER.debug("Failed to query GitHub releases endpoint %s: %s", url, exc)
            return None

    def _extract_asset_digest(self, asset: dict) -> str | None:
        digest = asset.get("digest")
        if not isinstance(digest, str):
            return None
        digest = digest.strip()
        if not digest:
            return None
        algorithm: str | None = None
        value = digest
        if ":" in digest:
            algorithm, value = digest.split(":", 1)
        elif "=" in digest:
            algorithm, value = digest.split("=", 1)
        if algorithm is not None and algorithm.strip().lower() != "sha256":
            _LOGGER.debug(
                "Ignoring unsupported asset digest algorithm '%s' for asset %s",
                algorithm.strip(),
                asset.get("name"),
            )
            return None
        value = value.strip().lower()
        if not value:
            return None
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            _LOGGER.debug(
                "Asset digest for %s was not a valid SHA-256 hex string", asset.get("name")
            )
            return None
        return value

    def _candidate_releases(self) -> Iterator[dict]:
        if self._channel == UPDATE_CHANNEL_BETA:
            payload = self._request_json(self._releases_url)
            if isinstance(payload, list):
                for entry in payload:
                    details = self._resolve_release_details(entry)
                    if details is not None:
                        yield details
            return

        data = self._request_json(self._api_url)
        if data is None:
            return
        details = self._resolve_release_details(data)
        if details is not None:
            yield details

    def _resolve_release_details(self, payload: dict) -> dict | None:
        if not isinstance(payload, dict):
            return None
        release_url = payload.get("url")
        if isinstance(release_url, str) and release_url:
            details = self._request_json(release_url)
            if details is not None:
                return details
        return payload

    def _normalise_channel(self, channel: str | None) -> str:
        if isinstance(channel, str):
            lowered = channel.strip().lower()
            if lowered in UPDATE_CHANNELS:
                return lowered
        return UPDATE_CHANNEL_STABLE

    def _is_channel_compatible(self, release: dict) -> bool:
        if release.get("draft"):
            return False

        version = str(release.get("tag_name") or release.get("name") or "").strip()
        if not version:
            return False

        prerelease = bool(release.get("prerelease"))
        if self._channel == UPDATE_CHANNEL_STABLE and prerelease:
            return False

        normalised = version.lstrip("v").lower()
        if self._channel == UPDATE_CHANNEL_STABLE and self._looks_like_beta_version(normalised):
            return False

        return True

    def _looks_like_beta_version(self, version: str) -> bool:
        lowered = version.lower()
        return ".dev" in lowered or lowered.endswith("dev")

    def _build_release_info(self, data: dict) -> ReleaseInfo | None:
        version = str(data.get("tag_name") or data.get("name") or "").strip()
        if not version:
            return None
        version = version.lstrip("v")

        assets = data.get("assets") or []
        installer_asset = self._select_windows_asset(assets)
        if installer_asset is None:
            return None

        inline_hash = self._extract_asset_digest(installer_asset)
        hash_url: str | None = None
        if inline_hash is None:
            hash_asset = self._find_companion_hash_asset(installer_asset, assets)
            if hash_asset is None:
                _LOGGER.error(
                    "Release asset %s is missing a SHA-256 digest and no companion hash file was found; refusing to use release %s",
                    installer_asset.get("name"),
                    version,
                )
                return None

            candidate_url = hash_asset.get("browser_download_url")
            if not isinstance(candidate_url, str) or not candidate_url.strip():
                _LOGGER.error(
                    "Release %s includes hash asset %s without a download URL",
                    version,
                    hash_asset.get("name"),
                )
                return None

            hash_url = candidate_url.strip()
            _LOGGER.info(
                "GitHub release %s will retrieve SHA-256 from companion asset %s",
                version,
                hash_asset.get("name"),
            )

        _LOGGER.info(
            "GitHub release %s includes installer asset %s",
            version,
            installer_asset.get("name"),
        )

        return ReleaseInfo(
            version=version,
            asset_name=str(installer_asset.get("name", "installer")),
            download_url=str(installer_asset.get("browser_download_url")),
            hash_value=inline_hash,
            hash_url=hash_url,
            release_notes=_clean_release_notes(data.get("body")),
            entry_point=DEFAULT_ARCHIVE_ENTRY_POINT,
        )

    def _select_windows_asset(self, assets: Iterable[dict]) -> dict | None:
        """Return the release asset most likely to target Windows."""

        executables: list[dict] = []
        archives: list[dict] = []
        fallbacks: list[dict] = []

        for asset in assets:
            name = str(asset.get("name", ""))
            lower = name.lower()

            if not lower or lower.endswith(".sha256"):
                continue
            if _PLATFORM_SKIP_PATTERN.search(lower):
                continue

            if lower.endswith(WINDOWS_EXECUTABLE_EXTENSIONS):
                executables.append(asset)
                continue

            if lower.endswith(WINDOWS_ARCHIVE_EXTENSIONS):
                if "win" in lower or "windows" in lower:
                    archives.insert(0, asset)
                else:
                    archives.append(asset)
                continue

            fallbacks.append(asset)

        if executables:
            return executables[0]
        if archives:
            return archives[0]
        if fallbacks:
            return fallbacks[0]
        return None

    def _find_companion_hash_asset(
        self, installer_asset: dict, assets: Iterable[dict]
    ) -> dict | None:
        installer_name = str(installer_asset.get("name") or "").strip()
        if not installer_name:
            return None

        expected_name = f"{installer_name}.sha256".lower()
        fallback: dict | None = None

        for asset in assets:
            name = str(asset.get("name") or "").strip()
            if not name or not name.lower().endswith(".sha256"):
                continue

            lower_name = name.lower()
            if lower_name == expected_name:
                return asset
            if fallback is None and lower_name.startswith(installer_name.lower()):
                fallback = asset

        return fallback

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
