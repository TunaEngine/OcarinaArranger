"""Tests for the create_release_archive helper script."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from zipfile import ZipFile


def _remove_app_modules() -> dict[str, object]:
    removed: dict[str, object] = {}
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            removed[name] = sys.modules.pop(name)
    return removed


def _restore_app_modules(modules: dict[str, object]) -> None:
    sys.modules.update(modules)


def _load_release_script(script_path: Path) -> object:
    spec = importlib.util.spec_from_file_location("create_release_archive_test", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to create module spec for create_release_archive script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_script_adds_project_root_to_sys_path(monkeypatch):
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "create_release_archive.py"

    removed_modules = _remove_app_modules()
    monkeypatch.setattr(sys, "path", [str(script_path.parent)])

    try:
        module = _load_release_script(script_path)
        assert str(project_root) in sys.path
        resolved_root = module.ensure_project_root_on_sys_path()
        assert resolved_root == project_root
    finally:
        _restore_app_modules(removed_modules)


def test_main_creates_versioned_and_unversioned_archives(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "create_release_archive.py"

    removed_modules = _remove_app_modules()
    try:
        module = _load_release_script(script_path)

        dist_dir = tmp_path / "dist" / "OcarinaArranger"
        dist_dir.mkdir(parents=True)
        (dist_dir / "dummy.txt").write_text("payload", encoding="utf-8")

        archive_base = tmp_path / "OcarinaArranger-windows"
        args = argparse.Namespace(archive_name=str(archive_base), dist_dir=dist_dir)
        monkeypatch.setattr(module, "parse_args", lambda: args)
        monkeypatch.setattr(module, "get_app_version", lambda: "1.2.3")

        exit_code = module.main()
        assert exit_code == 0

        versioned = archive_base.with_name("OcarinaArranger-windows-v1.2.3.zip")
        unversioned = archive_base.with_suffix(".zip")
        assert versioned.exists(), "Expected versioned archive to be created"
        assert unversioned.exists(), "Expected unversioned archive to be created"

        with ZipFile(versioned) as versioned_zip, ZipFile(unversioned) as unversioned_zip:
            assert sorted(versioned_zip.namelist()) == sorted(unversioned_zip.namelist())
    finally:
        _restore_app_modules(removed_modules)
