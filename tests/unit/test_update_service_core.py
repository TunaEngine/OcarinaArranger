from __future__ import annotations

import datetime
import hashlib
import logging
from pathlib import Path
from zipfile import ZipFile

import pytest

from services.update import INSTALL_ROOT_ENV, ReleaseInfo, UpdateError, UpdateService
from tests.unit.update_service_test_utils import (
    RecordingInstaller,
    StaticReleaseProvider,
    build_update_archive,
    configure_install_root,
)


def test_update_service_installs_newer_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixed_now = datetime.datetime(2024, 1, 2, 3, 4, 5)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now

    monkeypatch.setattr("services.update.service.datetime.datetime", FixedDateTime)
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.2.4",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.3")

    install_root = configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    updated = service.check_for_updates()

    assert updated is True
    assert len(installer.installed) == 1
    plan, installed_version = installer.installed[0]
    assert installed_version == "1.2.4"
    assert plan.command[0].lower() == "powershell"
    assert "-WindowStyle" in plan.command
    window_index = plan.command.index("-WindowStyle")
    assert plan.command[window_index + 1].lower() == "hidden"
    assert "-StagePath" in plan.command
    stage_index = plan.command.index("-StagePath")
    stage_dir = Path(plan.command[stage_index + 1])
    assert stage_dir.exists()
    assert (stage_dir / "OcarinaArranger.exe").exists()
    install_index = plan.command.index("-InstallPath")
    assert Path(plan.command[install_index + 1]) == install_root
    file_index = plan.command.index("-File")
    script_path = Path(plan.command[file_index + 1])
    assert script_path.exists()
    assert script_path.suffix.lower() == ".ps1"
    assert plan.working_directory == script_path.parent
    log_index = plan.command.index("-LogPath")
    log_path = Path(plan.command[log_index + 1])
    expected_log = install_root.parent / f"{install_root.name}.update.20240102-030405.log"
    assert log_path == expected_log
    marker_index = plan.command.index("-FailureMarkerPath")
    marker_path = Path(plan.command[marker_index + 1])
    expected_marker = install_root.parent / f"{install_root.name}.update_failed.json"
    assert marker_path == expected_marker
    script_text = script_path.read_text(encoding="utf-8")
    assert "function Write-Log" in script_text
    assert "Write-Log \"Moving staged update" in script_text
    assert "Write-Log \"Installer script completed successfully" in script_text
    assert "Show-FailureMessage" not in script_text
    assert "Removing staged update at $StagePath after failure" in script_text
    assert "Close any other programs that might be using the installation folder" in script_text
    assert "Relaunching previous application version" in script_text
    assert "FailureMarkerPath" in script_text
    assert "ConvertTo-Json" in script_text
    assert "[System.IO.File]::WriteAllText" in script_text
    assert "exit 1" in script_text
    assert "function Move-ItemWithRetry" in script_text
    assert "Move-ItemWithRetry -SourcePath $InstallPath" in script_text
    assert ". Retrying in " in script_text


def test_update_service_emits_progress_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="services.update")
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.2.4",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.3")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    updated = service.check_for_updates()

    assert updated is True
    messages = [record.getMessage() for record in caplog.records]
    assert any("Update available" in message for message in messages)
    assert any("Preparing update installation" in message for message in messages)
    assert any("Verified installer" in message for message in messages)
    assert any("Staged portable update" in message for message in messages)


def test_update_service_uses_existing_log_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.4.0",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.3.0")

    log_path = tmp_path / "app.log"
    handler = logging.FileHandler(log_path)
    setattr(handler, "_ocarina_logging_handler", True)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)
        updated = service.check_for_updates()
    finally:
        root_logger.removeHandler(handler)
        handler.close()

    assert updated is True
    plan, _ = installer.installed[0]
    log_index = plan.command.index("-LogPath")
    assert Path(plan.command[log_index + 1]) == log_path


def test_update_service_honours_entry_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = build_update_archive(
        tmp_path,
        {
            "OcarinaArranger.exe": b"primary",
            "tools/Helper.exe": b"helper",
        },
    )
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.2.5",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
        entry_point="OcarinaArranger/tools/Helper.exe",
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.4")

    install_root = configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    updated = service.check_for_updates()

    assert updated is True
    assert len(installer.installed) == 1
    plan, installed_version = installer.installed[0]
    assert installed_version == "1.2.5"
    assert "-ExecutablePath" in plan.command
    exe_index = plan.command.index("-ExecutablePath")
    assert plan.command[exe_index + 1].endswith("tools\\Helper.exe") or plan.command[exe_index + 1].endswith(
        "tools/Helper.exe"
    )
    install_index = plan.command.index("-InstallPath")
    assert Path(plan.command[install_index + 1]) == install_root


def test_update_service_errors_when_archive_missing_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = build_update_archive(tmp_path, {"docs/readme.txt": b"info"})
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.0.1",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_update_service_skips_when_versions_match(tmp_path: Path) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.0.0",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    updated = service.check_for_updates()

    assert updated is False
    assert installer.installed == []


def test_update_service_raises_on_hash_mismatch(tmp_path: Path) -> None:
    archive_path = build_update_archive(tmp_path)
    release = ReleaseInfo(
        version="1.1.0",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value="deadbeef",
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_update_service_errors_when_hash_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = build_update_archive(tmp_path)
    release = ReleaseInfo(
        version="1.3.0",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.0")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    with pytest.raises(UpdateError, match="missing security hash"):
        service.check_for_updates()

    assert installer.installed == []


def test_update_service_rejects_archive_exceeding_limits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_TOTAL_BYTES", 16, raising=False)
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_FILE_SIZE", 1024, raising=False)
    archive_path = build_update_archive(tmp_path, {"OcarinaArranger.exe": b"x" * 32})
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="2.0.0",
        asset_name=archive_path.name,
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_update_service_rejects_archive_with_extreme_compression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_TOTAL_BYTES", 10_000, raising=False)
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_FILE_SIZE", 10_000, raising=False)
    archive_path = build_update_archive(tmp_path, {"OcarinaArranger.exe": b"a" * 2048})
    with ZipFile(archive_path) as archive:
        info = next(entry for entry in archive.infolist() if not entry.is_dir())
    ratio = info.file_size / max(1, info.compress_size)
    assert ratio > 1
    monkeypatch.setattr("services.update.constants.MAX_COMPRESSION_RATIO", ratio - 0.5, raising=False)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="2.0.1",
        asset_name=archive_path.name,
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_get_available_release_returns_newer_version(tmp_path: Path) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="2.0.0",
        asset_name=archive_path.name,
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    available = service.get_available_release()

    assert available == release


def test_get_available_release_returns_none_when_current_is_newer(tmp_path: Path) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="0.9.0",
        asset_name=archive_path.name,
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.0.0")

    available = service.get_available_release()

    assert available is None


def test_get_available_release_offers_stable_downgrade_for_prerelease(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="services.update")
    release = ReleaseInfo(
        version="1.2.1",
        asset_name="OcarinaArranger-windows.zip",
        download_url="https://example.invalid/stable.zip",
        hash_value="deadbeef" * 8,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.2.dev")

    available = service.get_available_release()

    assert available == release
    messages = [record.getMessage() for record in caplog.records]
    assert any("Downgrade available" in message for message in messages)


def test_get_available_release_uses_fallback_provider_when_primary_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="services.update")
    release = ReleaseInfo(
        version="1.2.1",
        asset_name="OcarinaArranger-windows.zip",
        download_url="https://example.invalid/stable.zip",
        hash_value="cafebabe" * 8,
    )
    provider = StaticReleaseProvider(None)
    fallback_provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(
        provider,
        installer,
        current_version="1.2.2.dev",
        fallback_providers=[fallback_provider],
    )

    available = service.get_available_release()

    assert available == release
    messages = [record.getMessage() for record in caplog.records]
    assert any("fallback provider" in message for message in messages)


def test_update_service_installs_stable_downgrade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    release = ReleaseInfo(
        version="1.2.1",
        asset_name="OcarinaArranger-windows.zip",
        source_path=archive_path,
        hash_value=digest,
    )
    provider = StaticReleaseProvider(release)
    installer = RecordingInstaller()
    service = UpdateService(provider, installer, current_version="1.2.2.dev")

    configure_install_root(monkeypatch, tmp_path, INSTALL_ROOT_ENV)

    updated = service.check_for_updates()

    assert updated is True
    assert [version for _, version in installer.installed] == ["1.2.1"]
