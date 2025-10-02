from __future__ import annotations

import json

import pytest

from ocarina_gui.fingering import _CONFIG_ENV_VAR
from ocarina_gui.fingering.half_holes import (
    instrument_allows_half_holes,
    set_instrument_half_holes,
)


def test_default_six_hole_allows_half_holes() -> None:
    assert instrument_allows_half_holes("alto_c_6") is True


def test_half_hole_support_is_persisted(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config_path = tmp_path / "fingering_config.json"
    monkeypatch.setenv(_CONFIG_ENV_VAR, str(config_path))

    from ocarina_gui import fingering as fingering_pkg
    from ocarina_gui.fingering import library as fingering_library

    original_library = fingering_library._LIBRARY
    original_module_library = fingering_pkg._LIBRARY

    instrument_id = "alto_c_12"
    try:
        assert instrument_allows_half_holes(instrument_id) is False

        set_instrument_half_holes(instrument_id, True)
        assert instrument_allows_half_holes(instrument_id) is True

        data = json.loads(config_path.read_text(encoding="utf-8"))
        entry = next(item for item in data["instruments"] if item["id"] == instrument_id)
        assert entry["allow_half_holes"] is True

        set_instrument_half_holes(instrument_id, False)
        assert instrument_allows_half_holes(instrument_id) is False

        data = json.loads(config_path.read_text(encoding="utf-8"))
        entry = next(item for item in data["instruments"] if item["id"] == instrument_id)
        assert entry["allow_half_holes"] is False
    finally:
        fingering_library._LIBRARY = original_library
        fingering_pkg._LIBRARY = original_module_library
