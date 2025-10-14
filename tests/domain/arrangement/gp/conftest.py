from __future__ import annotations

import pytest

from domain.arrangement.config import clear_instrument_registry


@pytest.fixture(autouse=True)
def _reset_instrument_registry() -> None:
    """Ensure each test starts with a clean instrument registry."""

    clear_instrument_registry()

