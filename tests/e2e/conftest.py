from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.harness import E2EHarness, create_e2e_harness


@pytest.fixture
def e2e_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> E2EHarness:
    harness = create_e2e_harness(monkeypatch, tmp_path)
    yield harness
    harness.destroy()
