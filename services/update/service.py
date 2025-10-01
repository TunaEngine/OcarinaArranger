"""Service responsible for discovering and installing updates."""

from __future__ import annotations

import datetime
import logging
import os
import shutil
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path

from services.update.constants import WINDOWS_ARCHIVE_EXTENSIONS
from services.update.archive import ArchiveExtraction, extract_archive, locate_archive_entry
from services.update.hashing import calculate_sha256, parse_hash_text
from services.update.installers import Installer
from services.update.models import InstallationPlan, ReleaseInfo, UpdateError
from services.update.providers import ReleaseProvider
from services.update.recovery import find_install_root, get_failure_marker_path


_LOGGER = logging.getLogger(__name__)


def _find_primary_log_file() -> Path | None:
    """Return the application log file if one is configured."""

    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and hasattr(handler, "baseFilename"):
            if getattr(handler, "_ocarina_logging_handler", False):
                return Path(handler.baseFilename)
    return None


class UpdateService:
    """Coordinate release discovery, download and verification."""

    def __init__(self, provider: ReleaseProvider, installer: Installer, *, current_version: str) -> None:
        self._provider = provider
        self._installer = installer
        self._current_version = current_version

    def get_available_release(self) -> ReleaseInfo | None:
        """Return the newest release newer than the current version."""

        release = self._provider.fetch_latest()
        if release is None:
            _LOGGER.debug("No release information available")
            return None

        if not self._is_version_newer(release.version):
            _LOGGER.debug("Current version %s is up to date", self._current_version)
            return None

        _LOGGER.info(
            "Update available: %s -> %s", self._current_version, release.version
        )
        return release

    def download_and_install(self, release: ReleaseInfo) -> None:
        """Download, verify and launch the installer for ``release``."""

        _LOGGER.info("Preparing update installation for version %s", release.version)
        download_path = self._obtain_installer(release)
        _LOGGER.debug("Installer asset stored at %s", download_path)
        expected_hash = self._resolve_expected_hash(release)
        actual_hash = calculate_sha256(download_path)
        if expected_hash.lower() != actual_hash.lower():
            raise UpdateError(
                f"Installer hash mismatch: expected {expected_hash} but received {actual_hash}"
            )

        _LOGGER.info("Verified installer for version %s", release.version)
        plan = self._build_installation_plan(download_path, release)
        _LOGGER.debug("Installation plan command: %s", plan.command)
        self._installer.install(plan, release.version)

    def check_for_updates(self) -> bool:
        release = self.get_available_release()
        if release is None:
            return False

        self.download_and_install(release)
        return True

    def _is_version_newer(self, candidate: str) -> bool:
        if candidate == self._current_version:
            return False
        try:
            from packaging.version import InvalidVersion, Version  # type: ignore
        except Exception:  # pragma: no cover - packaging not installed
            return self._fallback_compare(candidate)

        try:
            return Version(candidate) > Version(self._current_version)
        except InvalidVersion:
            return self._fallback_compare(candidate)

    def _fallback_compare(self, candidate: str) -> bool:
        def tokenize(version: str) -> list[tuple[int, object]]:
            tokens: list[tuple[int, object]] = []
            for raw in version.replace("-", ".").replace("+", ".").split("."):
                if not raw:
                    continue
                if raw.isdigit():
                    tokens.append((0, int(raw)))
                else:
                    tokens.append((1, raw.lower()))
            return tokens

        current_tokens = tokenize(self._current_version)
        candidate_tokens = tokenize(candidate)
        length = max(len(current_tokens), len(candidate_tokens))
        for index in range(length):
            current_token = current_tokens[index] if index < len(current_tokens) else (0, 0)
            candidate_token = candidate_tokens[index] if index < len(candidate_tokens) else (0, 0)
            if candidate_token != current_token:
                return candidate_token > current_token
        return False

    def _obtain_installer(self, release: ReleaseInfo) -> Path:
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

    def _resolve_expected_hash(self, release: ReleaseInfo) -> str:
        if release.hash_value:
            _LOGGER.debug(
                "Using inline hash for version %s", release.version
            )
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

    def _build_installation_plan(self, asset_path: Path, release: ReleaseInfo) -> InstallationPlan:
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

        return self._plan_archive_installation(asset_path, release)

    def _plan_archive_installation(self, archive_path: Path, release: ReleaseInfo) -> InstallationPlan:
        _LOGGER.info("Preparing archive installation from %s", archive_path)
        extract_dir = extract_archive(archive_path)
        extraction = locate_archive_entry(extract_dir, release.entry_point)
        install_root = self._resolve_install_root()
        stage_dir, final_executable = self._stage_portable_update(extraction, install_root)
        failure_marker = get_failure_marker_path(install_root)
        log_path = self._determine_script_log_path(install_root)
        script_path = self._write_portable_update_script(
            stage_dir, install_root, final_executable, failure_marker
        )
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
        return InstallationPlan(tuple(command))

    def _determine_script_log_path(self, install_root: Path) -> Path | None:
        log_path = _find_primary_log_file()
        if log_path is not None:
            return log_path
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return install_root.parent / f"{install_root.name}.update.{timestamp}.log"

    def _resolve_install_root(self) -> Path:
        install_root = find_install_root()
        if install_root is None:
            raise UpdateError("Automatic updates require a packaged application build")
        _LOGGER.debug("Resolved packaged install root to %s", install_root)
        return install_root

    def _stage_portable_update(
        self, extraction: ArchiveExtraction, install_root: Path
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

    def _write_portable_update_script(
        self, stage_dir: Path, install_root: Path, executable: Path, failure_marker: Path
    ) -> Path:
        script_dir = Path(tempfile.mkdtemp(prefix="ocarina-update-script-"))
        script_path = script_dir / "install.ps1"
        content = textwrap.dedent(
            """
            param(
                [int]$ProcessId,
                [string]$StagePath,
                [string]$InstallPath,
                [string]$ExecutablePath,
                [string]$LogPath = '',
                [string]$FailureMarkerPath = ''
            )

            $ErrorActionPreference = 'Stop'

            function Write-Log {
                param([string]$Message)

                $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
                $line = "$timestamp $Message"

                if ($LogPath -ne '') {
                    try {
                        $logDirectory = Split-Path -Path $LogPath -Parent
                        if ($logDirectory -and -not (Test-Path -LiteralPath $logDirectory)) {
                            New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
                        }
                        Add-Content -LiteralPath $LogPath -Value $line
                    }
                    catch {
                        # Swallow logging errors so installation can proceed.
                    }
                }

                Write-Output $line
            }

            function Clear-FailureMarker {
                if ($FailureMarkerPath -eq '') {
                    return
                }

                try {
                    if (Test-Path -LiteralPath $FailureMarkerPath) {
                        Remove-Item -LiteralPath $FailureMarkerPath -Force
                    }
                }
                catch {
                    Write-Log ("Failed to remove failure marker: " + $_.Exception.Message)
                }
            }

            function Write-FailureMarker {
                param([string]$Reason, [string]$Advice)

                if ($FailureMarkerPath -eq '') {
                    return
                }

                try {
                    $directory = Split-Path -Path $FailureMarkerPath -Parent
                    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
                        New-Item -ItemType Directory -Path $directory -Force | Out-Null
                    }

                    $payload = @{
                        reason = $Reason
                        advice = $Advice
                        recorded_at = (Get-Date -Format 'o')
                    } | ConvertTo-Json -Compress

                    $encoding = New-Object System.Text.UTF8Encoding($false)
                    [System.IO.File]::WriteAllText($FailureMarkerPath, $payload, $encoding)
                }
                catch {
                    Write-Log ("Failed to record failure marker: " + $_.Exception.Message)
                }
            }

            Write-Log "Waiting for process $ProcessId to exit before installing update."
            while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
                Start-Sleep -Milliseconds 500
            }
            Write-Log "Process $ProcessId has exited."

            Clear-FailureMarker

            $installParent = Split-Path -Path $InstallPath -Parent
            $installName = Split-Path -Path $InstallPath -Leaf
            $backupPath = Join-Path -Path $installParent -ChildPath ($installName + '.backup')

            if (Test-Path -LiteralPath $backupPath) {
                Write-Log "Removing previous backup at $backupPath."
                Remove-Item -LiteralPath $backupPath -Recurse -Force
            }

            try {
                if (Test-Path -LiteralPath $InstallPath) {
                    Write-Log "Moving existing installation from $InstallPath to backup at $backupPath."
                    Move-Item -LiteralPath $InstallPath -Destination $backupPath -Force
                }

                Write-Log "Moving staged update from $StagePath to $InstallPath."
                Move-Item -LiteralPath $StagePath -Destination $InstallPath -Force

                if (Test-Path -LiteralPath $backupPath) {
                    Write-Log "Removing backup at $backupPath after successful install."
                    Remove-Item -LiteralPath $backupPath -Recurse -Force
                }
            }
            catch {
                $failure = $_
                $rawMessage = $failure.Exception.Message
                Write-Log ("Installer script failed: " + $rawMessage)
                if (Test-Path -LiteralPath $backupPath) {
                    try {
                        Write-Log "Attempting to restore backup from $backupPath to $InstallPath."
                        if (Test-Path -LiteralPath $InstallPath) {
                            Remove-Item -LiteralPath $InstallPath -Recurse -Force
                        }

                        Move-Item -LiteralPath $backupPath -Destination $InstallPath -Force
                    }
                    catch {
                        $restoreError = $_
                        Write-Log ("Failed to restore backup: " + $restoreError.Exception.Message)
                    }
                }

                if (Test-Path -LiteralPath $StagePath) {
                    try {
                        Write-Log "Removing staged update at $StagePath after failure."
                        Remove-Item -LiteralPath $StagePath -Recurse -Force
                    }
                    catch {
                        $stageError = $_
                        Write-Log ("Failed to remove staged update: " + $stageError.Exception.Message)
                    }
                }

                $advice = 'Please try again after restarting Ocarina Arranger.'
                if ($rawMessage -match 'in use' -or $rawMessage -match 'used by another process') {
                    $advice = 'Close any other programs that might be using the installation folder (for example File Explorer or Command Prompt) and try again.'
                }
                elseif ($rawMessage -match 'access is denied') {
                    $advice = 'Ensure you have permission to modify the installation folder and try again.'
                }

                Write-FailureMarker $rawMessage $advice

                $exeDir = Split-Path -Path $ExecutablePath
                Write-Log "Relaunching previous application version at $ExecutablePath due to failure."
                try {
                    Start-Process -FilePath $ExecutablePath -WorkingDirectory $exeDir
                }
                catch {
                    $launchError = $_
                    Write-Log ("Failed to relaunch application: " + $launchError.Exception.Message)
                }
                exit 1
            }

            Clear-FailureMarker

            $exeDir = Split-Path -Path $ExecutablePath
            Write-Log "Launching updated application at $ExecutablePath."
            Start-Process -FilePath $ExecutablePath -WorkingDirectory $exeDir
            Write-Log "Installer script completed successfully."
            """
        ).strip()
        script_path.write_text(content, encoding="utf-8")
        _LOGGER.debug("Wrote portable update script to %s", script_path)
        return script_path
