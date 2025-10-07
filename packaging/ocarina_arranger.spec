# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the Ocarina Arranger desktop binary."""

from __future__ import annotations

import sys
from pathlib import Path

block_cipher = None

try:
    spec_path = Path(__file__).resolve()
except NameError:
    spec_arg = next((arg for arg in sys.argv[1:] if arg.endswith(".spec")), None)
    if spec_arg is not None:
        spec_path = Path(spec_arg).resolve()
    else:
        spec_path = Path.cwd() / "packaging" / "ocarina_arranger.spec"

project_dir = spec_path.parent.parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from pyinstaller_helpers.assets import list_arranged_preview_asset_datas

import ttkbootstrap

bootstrap_package = Path(ttkbootstrap.__file__).resolve().parent
bootstrap_themes = bootstrap_package / "themes"
_BOOTSTRAP_DATAS: list[tuple[str, str]] = []
if bootstrap_themes.exists():
    _BOOTSTRAP_DATAS = [(str(bootstrap_themes), "ttkbootstrap/themes")]

arranged_asset_datas = list_arranged_preview_asset_datas(project_dir)

analysis = Analysis(
    [str(project_dir / "ocarina_gui" / "app.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        (str(project_dir / "ocarina_gui" / "config" / "themes.json"), "ocarina_gui/config"),
        (
            str(project_dir / "ocarina_gui" / "fingering" / "config" / "fingering_config.json"),
            "ocarina_gui/fingering/config",
        ),
        (str(project_dir / "app" / "VERSION"), "app"),
        (
            str(project_dir / "ui" / "main_window" / "resources" / "app_icon.png"),
            "ui/main_window/resources",
        ),
        (
            str(project_dir / "ui" / "main_window" / "resources" / "app_icon.ico"),
            "ui/main_window/resources",
        ),
        (str(project_dir / "THIRD-PARTY-LICENSES"), "."),
        *arranged_asset_datas,
        *_BOOTSTRAP_DATAS,
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="OcarinaArranger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    icon=str(project_dir / "ui" / "main_window" / "resources" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OcarinaArranger",
)
