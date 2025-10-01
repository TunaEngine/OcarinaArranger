from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.update import INSTALL_ROOT_ENV
from services.update.recovery import (
    consume_update_failure_notice,
    get_failure_marker_path,
)


def test_consume_update_failure_notice_handles_utf8_bom(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install_root = tmp_path / "install"
    install_root.mkdir()
    monkeypatch.setenv(INSTALL_ROOT_ENV, str(install_root))

    marker_path = get_failure_marker_path(install_root)
    marker_path.write_text(
        json.dumps({"reason": "Locked", "advice": "Close Explorer."}),
        encoding="utf-8-sig",
    )

    notice = consume_update_failure_notice()

    assert notice == ("Locked", "Close Explorer.")
    assert not marker_path.exists()
