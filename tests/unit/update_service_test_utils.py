from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from services.update import ReleaseInfo
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


def build_update_archive(tmp_path: Path, files: dict[str, bytes] | None = None) -> Path:
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


def configure_install_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env_var: str) -> Path:
    install_root = tmp_path / "install"
    install_root.mkdir()
    monkeypatch.setenv(env_var, str(install_root))
    return install_root


__all__ = [
    "RecordingInstaller",
    "StaticReleaseProvider",
    "build_update_archive",
    "configure_install_root",
]
