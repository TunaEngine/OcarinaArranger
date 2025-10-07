"""Unit tests for license loading in the about menu."""

from __future__ import annotations

from pathlib import Path

import pytest

from ui.main_window.menus import about


def test_load_license_text_reads_first_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    primary = tmp_path / "missing"
    fallback = tmp_path / "THIRD-PARTY-LICENSES"
    fallback.write_text("hello licenses", encoding="utf-8")

    monkeypatch.setattr(
        about, "_license_file_candidates", lambda: [primary, fallback]
    )

    assert about._load_license_text() == "hello licenses"


def test_load_license_text_raises_when_all_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(about, "_license_file_candidates", lambda: [missing])

    with pytest.raises(FileNotFoundError):
        about._load_license_text()


def test_load_license_text_propagates_os_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    directory = tmp_path / "dir"
    directory.mkdir()
    monkeypatch.setattr(about, "_license_file_candidates", lambda: [directory])

    with pytest.raises(OSError):
        about._load_license_text()
