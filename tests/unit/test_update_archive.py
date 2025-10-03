from __future__ import annotations

from pathlib import Path

import pytest

from services.update.archive import ArchiveExtraction


def _patch_path_resolve(monkeypatch: pytest.MonkeyPatch, path: Path, result: Path) -> None:
    """Force ``path.resolve(strict=True)`` to return ``result`` for the test duration."""

    path_cls = type(path)
    original_resolve = path_cls.resolve

    def fake_resolve(self: Path, strict: bool = False):  # type: ignore[override]
        if self == path:
            return result
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(path_cls, "resolve", fake_resolve)


def test_archive_extraction_relative_entry_handles_filesystem_alias(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    executable = archive_root / "OcarinaArranger.exe"
    executable.write_text("stub", encoding="utf-8")

    alias_root = tmp_path / "alias"
    try:
        alias_root.symlink_to(archive_root, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks not supported on this platform: {exc}")

    extraction = ArchiveExtraction(alias_root, executable)

    assert extraction.relative_entry == Path("OcarinaArranger.exe")


def test_archive_extraction_relative_entry_handles_alias_without_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    executable = archive_root / "OcarinaArranger.exe"
    executable.write_text("stub", encoding="utf-8")

    alias_root = tmp_path / "alias"
    try:
        alias_root.symlink_to(archive_root, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks not supported on this platform: {exc}")

    _patch_path_resolve(monkeypatch, alias_root, alias_root)

    extraction = ArchiveExtraction(alias_root, executable)

    assert extraction.relative_entry == Path("OcarinaArranger.exe")
