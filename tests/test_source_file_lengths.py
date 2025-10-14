from __future__ import annotations

from pathlib import Path

import pytest


MAX_FILE_LENGTH = 500
REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIR_NAMES = {".git", ".venv", "__pycache__"}
ALLOWLIST = {
    Path("tests/ui/test_gui_preview_rendering.py"),
    Path("ui/main_window/menus/theme/palette.py"),
    Path("ocarina_gui/pdf_export/pages/staff.py"),
    Path("viewmodels/preview_playback_viewmodel.py"),
}


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def test_source_files_are_not_longer_than_500_lines() -> None:
    violations: list[str] = []

    for path in sorted(
        p.relative_to(REPO_ROOT)
        for p in REPO_ROOT.rglob("*.py")
        if not _should_skip(p.relative_to(REPO_ROOT)) and p.relative_to(REPO_ROOT) not in ALLOWLIST
    ):
        file_path = REPO_ROOT / path
        with file_path.open("r", encoding="utf-8") as file_handle:
            line_count = sum(1 for _ in file_handle)

        if line_count > MAX_FILE_LENGTH:
            violations.append(
                f"{path} has {line_count} lines which exceeds the {MAX_FILE_LENGTH}-line limit"
            )

    assert not violations, "\n".join(["Found files exceeding the maximum length:", *violations])
