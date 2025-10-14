from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _autouse_original_preview(ensure_original_preview):
    """Ensure each preview test initialises the original preview tab."""

    return ensure_original_preview
