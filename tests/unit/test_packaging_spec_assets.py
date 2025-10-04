"""Verify that the PyInstaller spec bundles required preview icon assets."""

from __future__ import annotations

from pathlib import Path

from pyinstaller_helpers.assets import list_arranged_preview_asset_datas


def test_spec_lists_preview_png_assets() -> None:
    project_root = Path(__file__).resolve().parents[2]

    datas = list_arranged_preview_asset_datas(project_root)
    asset_dir = project_root / "ocarina_gui" / "ui_builders" / "assets"
    asset_paths = sorted(str(path) for path in asset_dir.glob("*.png"))

    bundled_paths = sorted(source for source, _dest in datas)

    assert bundled_paths == asset_paths
