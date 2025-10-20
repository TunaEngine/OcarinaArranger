from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.project_service_gp import (
    GPSettingsPresetError,
    PRESET_FILE_TYPE,
    export_gp_preset,
    import_gp_preset,
)
from viewmodels.arranger_models import ArrangerGPSettings


def test_export_gp_preset_writes_payload(tmp_path: Path) -> None:
    destination = tmp_path / "preset.gp.json"
    settings = ArrangerGPSettings(generations=12, population_size=18)

    saved = export_gp_preset(settings, destination)

    assert saved == destination
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["type"] == PRESET_FILE_TYPE
    assert payload["version"] == 1
    assert payload["settings"]["generations"] == 12
    assert payload["settings"]["population_size"] == 18


def test_import_gp_preset_round_trip(tmp_path: Path) -> None:
    destination = tmp_path / "preset.gp.json"
    settings = ArrangerGPSettings(generations=25, population_size=40)
    export_gp_preset(settings, destination)

    loaded = import_gp_preset(destination, ArrangerGPSettings())

    assert loaded.generations == 25
    assert loaded.population_size == 40


def test_import_gp_preset_rejects_bad_type(tmp_path: Path) -> None:
    destination = tmp_path / "preset.gp.json"
    destination.write_text(
        json.dumps({"type": "other", "version": 1, "settings": {}}),
        encoding="utf-8",
    )

    with pytest.raises(GPSettingsPresetError):
        import_gp_preset(destination, ArrangerGPSettings())
