from __future__ import annotations

import datetime
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from services.update import (
    INSTALL_ROOT_ENV,
    build_update_service,
    LocalFolderReleaseProvider,
    ReleaseInfo,
    UpdateError,
    UpdateService,
    schedule_startup_update_check,
)
from services.update.models import InstallationPlan


class RecordingInstaller:
    def __init__(self) -> None:
        self.installed: list[tuple[InstallationPlan, str]] = []

    def install(self, plan: InstallationPlan, version: str) -> None:
        self.installed.append((plan, version))


@dataclass
class StaticReleaseProvider:
    release: ReleaseInfo | None

    def fetch_latest(self) -> ReleaseInfo | None:
        return self.release


def _build_update_archive(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
    dist_root = tmp_path / "dist"
    package_dir = dist_root / "OcarinaArranger"
    package_dir.mkdir(parents=True)
    default_entries = {
        "OcarinaArranger.exe": b"payload",
        "_internal/python.exe": b"python",
    }
    entries = files or default_entries
    for relative, content in entries.items():
        path = package_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    archive_path = tmp_path / "OcarinaArranger-windows.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in package_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(dist_root))
    return archive_path


def _configure_install_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    install_root = tmp_path / "install"
    install_root.mkdir()
    monkeypatch.setenv(INSTALL_ROOT_ENV, str(install_root))
    return install_root


def test_update_service_installs_newer_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixed_now = datetime.datetime(2024, 1, 2, 3, 4, 5)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now

    monkeypatch.setattr("services.update.service.datetime.datetime", FixedDateTime)
    archive_path = _build_update_archive(tmp_path)
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

    install_root = _configure_install_root(monkeypatch, tmp_path)

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


def test_update_service_emits_progress_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="services.update")
    archive_path = _build_update_archive(tmp_path)
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

    _configure_install_root(monkeypatch, tmp_path)

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
    archive_path = _build_update_archive(tmp_path)
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
        _configure_install_root(monkeypatch, tmp_path)
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
    archive_path = _build_update_archive(
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

    install_root = _configure_install_root(monkeypatch, tmp_path)

    updated = service.check_for_updates()

    assert updated is True
    assert len(installer.installed) == 1
    plan, installed_version = installer.installed[0]
    assert installed_version == "1.2.5"
    assert "-ExecutablePath" in plan.command
    exe_index = plan.command.index("-ExecutablePath")
    assert plan.command[exe_index + 1].endswith("tools\\Helper.exe") or plan.command[exe_index + 1].endswith("tools/Helper.exe")
    install_index = plan.command.index("-InstallPath")
    assert Path(plan.command[install_index + 1]) == install_root


def test_update_service_errors_when_archive_missing_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_path = _build_update_archive(tmp_path, {"docs/readme.txt": b"info"})
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

    _configure_install_root(monkeypatch, tmp_path)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []

def test_update_service_skips_when_versions_match(tmp_path: Path) -> None:
    archive_path = _build_update_archive(tmp_path)
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
    archive_path = _build_update_archive(tmp_path)
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


def test_local_release_provider_reads_metadata(tmp_path: Path) -> None:
    archive_path = _build_update_archive(tmp_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    metadata = {
        "version": "3.1.4",
        "installer": archive_path.name,
        "sha256": digest,
        "release_notes": "  Lots of improvements.  ",
        "entry_point": "OcarinaArranger/OcarinaArranger.exe",
    }
    (tmp_path / "release.json").write_text(json.dumps(metadata), encoding="utf-8")

    provider = LocalFolderReleaseProvider(tmp_path)
    info = provider.fetch_latest()

    assert info is not None
    assert info.version == "3.1.4"
    assert info.asset_name == archive_path.name
    assert info.source_path == archive_path
    assert info.hash_value == digest
    assert info.release_notes == "Lots of improvements."
    assert info.entry_point == "OcarinaArranger/OcarinaArranger.exe"


def test_schedule_startup_update_check_noop_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: list[None] = []

    class FakeInstaller:
        def install(self, plan: InstallationPlan, version: str) -> None:  # pragma: no cover - defensive
            invoked.append(None)

    monkeypatch.setenv("OCARINA_APP_VERSION", "0.0.1")
    monkeypatch.setattr("sys.platform", "linux", raising=False)

    schedule_startup_update_check(installer=FakeInstaller())

    assert invoked == []


def test_update_service_rejects_archive_exceeding_limits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_TOTAL_BYTES", 16, raising=False)
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_FILE_SIZE", 1024, raising=False)
    archive_path = _build_update_archive(tmp_path, {"OcarinaArranger.exe": b"x" * 32})
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

    _configure_install_root(monkeypatch, tmp_path)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_update_service_rejects_archive_with_extreme_compression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_TOTAL_BYTES", 10_000, raising=False)
    monkeypatch.setattr("services.update.constants.MAX_ARCHIVE_FILE_SIZE", 10_000, raising=False)
    archive_path = _build_update_archive(tmp_path, {"OcarinaArranger.exe": b"a" * 2048})
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

    _configure_install_root(monkeypatch, tmp_path)

    with pytest.raises(UpdateError):
        service.check_for_updates()

    assert installer.installed == []


def test_schedule_startup_update_check_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCARINA_APP_VERSION", "0.0.1")
    monkeypatch.setattr("sys.platform", "win32", raising=False)

    started: list[str] = []

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - behaviour stub
            started.append("created")

        def start(self) -> None:  # pragma: no cover - behaviour stub
            started.append("started")

    monkeypatch.setattr("services.update.builder.threading.Thread", lambda *a, **k: FakeThread())

    schedule_startup_update_check(enabled=False)

    assert started == []


def test_get_available_release_returns_newer_version(tmp_path: Path) -> None:
    archive_path = _build_update_archive(tmp_path)
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
    archive_path = _build_update_archive(tmp_path)
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


def test_build_update_service_returns_none_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux", raising=False)

    service = build_update_service()

    assert service is None


def test_build_update_service_creates_service_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32", raising=False)
    monkeypatch.setattr(
        "services.update.builder._build_provider_from_env",
        lambda: StaticReleaseProvider(None),
    )
    monkeypatch.setattr("services.update.builder.get_app_version", lambda: "1.0.0")

    service = build_update_service(installer=RecordingInstaller())

    assert isinstance(service, UpdateService)
