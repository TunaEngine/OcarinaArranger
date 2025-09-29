"""Helper script to package PyInstaller output into a versioned zip archive."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def ensure_project_root_on_sys_path() -> Path:
    """Ensure the project root is importable when the script runs standalone."""

    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root


ensure_project_root_on_sys_path()

from app.version import get_app_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archive_name",
        help="Base name for the generated archive (without extension).",
    )
    parser.add_argument(
        "--dist-dir",
        default=Path("dist") / "OcarinaArranger",
        type=Path,
        help="Path to the PyInstaller distribution directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dist_dir = args.dist_dir
    if not dist_dir.exists():
        raise SystemExit(f"Distribution directory not found: {dist_dir}")

    version = get_app_version()
    archive_root = Path(args.archive_name).with_suffix("")
    archive_name = f"{archive_root.name}-v{version}"
    output = archive_root.with_name(archive_name)

    versioned_archive = shutil.make_archive(
        str(output),
        "zip",
        root_dir=dist_dir.parent,
        base_dir=dist_dir.name,
    )

    unversioned_archive = archive_root.with_suffix(".zip")
    shutil.copy2(versioned_archive, unversioned_archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
