"""Helpers for preparing PyInstaller bundle metadata."""

from __future__ import annotations

from pathlib import Path


def list_arranged_preview_asset_datas(project_dir: Path) -> list[tuple[str, str]]:
    """Return data tuples for all arranged preview icon assets."""

    asset_dir = project_dir / "ocarina_gui" / "ui_builders" / "assets"
    return [
        (str(path), "ocarina_gui/ui_builders/assets")
        for path in sorted(asset_dir.glob("*.png"))
    ]
