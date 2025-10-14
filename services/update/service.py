"""Service responsible for discovering and installing updates."""

from __future__ import annotations

import datetime as _datetime_module
import logging
from collections.abc import Iterable

from services.update.hashing import calculate_sha256
from services.update.installation_planner import build_installation_plan
from services.update.installers import Installer
from services.update.models import InstallationPlan, ReleaseInfo, UpdateError
from services.update.providers import ReleaseProvider
from services.update.release_assets import obtain_installer_asset, resolve_expected_hash
from services.update.versioning import is_version_newer, should_offer_downgrade

# ``datetime`` remains part of the module namespace for compatibility with tests
# and legacy callers that monkeypatch ``services.update.service.datetime``.
datetime = _datetime_module


_LOGGER = logging.getLogger(__name__)


class UpdateService:
    """Coordinate release discovery, download and verification."""

    def __init__(
        self,
        provider: ReleaseProvider,
        installer: Installer,
        *,
        current_version: str,
        fallback_providers: Iterable[ReleaseProvider] | None = None,
    ) -> None:
        self._provider = provider
        self._installer = installer
        self._current_version = current_version
        self._fallback_providers = list(fallback_providers or [])

    def get_available_release(self) -> ReleaseInfo | None:
        """Return the newest release newer than the current version."""

        release, fallback_name = self._fetch_release()
        if release is None:
            _LOGGER.debug("No release information available")
            return None

        if fallback_name is not None:
            _LOGGER.debug(
                "Primary release provider returned no release; using fallback provider %s",
                fallback_name,
            )

        if not is_version_newer(self._current_version, release.version):
            if should_offer_downgrade(self._current_version, release.version):
                _LOGGER.info(
                    "Downgrade available: %s -> %s",
                    self._current_version,
                    release.version,
                )
                return release

            _LOGGER.debug("Current version %s is up to date", self._current_version)
            return None

        _LOGGER.info(
            "Update available: %s -> %s", self._current_version, release.version
        )
        return release

    def download_and_install(self, release: ReleaseInfo) -> None:
        """Download, verify and launch the installer for ``release``."""

        _LOGGER.info("Preparing update installation for version %s", release.version)
        download_path = obtain_installer_asset(release)
        _LOGGER.debug("Installer asset stored at %s", download_path)
        expected_hash = resolve_expected_hash(release)
        actual_hash = calculate_sha256(download_path)
        if expected_hash.lower() != actual_hash.lower():
            raise UpdateError(
                f"Installer hash mismatch: expected {expected_hash} but received {actual_hash}"
            )
        _LOGGER.info("Verified installer for version %s", release.version)

        plan: InstallationPlan = build_installation_plan(download_path, release)
        _LOGGER.debug("Installation plan command: %s", plan.command)
        self._installer.install(plan, release.version)

    def check_for_updates(self) -> bool:
        release = self.get_available_release()
        if release is None:
            return False

        self.download_and_install(release)
        return True

    def _fetch_release(self) -> tuple[ReleaseInfo | None, str | None]:
        providers: list[ReleaseProvider] = [self._provider, *self._fallback_providers]
        for index, provider in enumerate(providers):
            provider_name = type(provider).__name__
            _LOGGER.debug("Querying release provider %s", provider_name)
            release = provider.fetch_latest()
            if release is None:
                _LOGGER.debug(
                    "Release provider %s returned no release metadata", provider_name
                )
                continue

            self._log_release_metadata(provider_name, release)

            if index == 0:
                return release, None
            return release, provider_name
        return None, None

    def _log_release_metadata(self, provider_name: str, release: ReleaseInfo) -> None:
        _LOGGER.debug(
            "Release provider %s returned version %s (entry=%s, asset=%s, hash=%s%s)",
            provider_name,
            release.version,
            release.entry_point,
            release.asset_name,
            "inline" if release.hash_value else "file",
            " available"
            if release.hash_value or release.hash_path or release.hash_url
            else " missing",
        )
        if release.download_url is not None:
            _LOGGER.debug(
                "Release %s download URL: %s", release.version, release.download_url
            )
        if release.source_path is not None:
            _LOGGER.debug(
                "Release %s sourced from local path %s",
                release.version,
                release.source_path,
            )
