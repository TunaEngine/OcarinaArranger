"""Tests for fingering configuration persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocarina_gui.fingering import config as fingering_config


def _force_write_failure(monkeypatch, target_path: Path) -> None:
    original_write_text = Path.write_text

    def _fail_write(self: Path, *args, **kwargs):
        if self == target_path:
            raise OSError(28, "No space left on device")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _fail_write)


def test_save_fingering_config_raises_actionable_error(tmp_path, monkeypatch):
    target = tmp_path / fingering_config._DEFAULT_CONFIG_FILENAME  # type: ignore[attr-defined]
    monkeypatch.setenv(fingering_config._CONFIG_ENV_VAR, str(target))  # type: ignore[attr-defined]
    _force_write_failure(monkeypatch, target)

    with pytest.raises(fingering_config.FingeringConfigPersistenceError) as excinfo:
        fingering_config.save_fingering_config({"instruments": []})

    message = str(excinfo.value)
    assert "Free up some disk space" in message
    assert str(target) in message


def test_invalid_user_config_is_backed_up_and_reset(tmp_path, monkeypatch):
    target = tmp_path / fingering_config._DEFAULT_CONFIG_FILENAME  # type: ignore[attr-defined]
    monkeypatch.setenv(fingering_config._CONFIG_ENV_VAR, str(target))  # type: ignore[attr-defined]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    existing_backup = target.with_name(target.name + ".bk")
    existing_backup.write_text("{}", encoding="utf-8")

    data = fingering_config.load_fingering_config()

    assert isinstance(data, dict)

    backup_path = target.with_name(target.name + ".bk1")
    assert backup_path.exists(), "Expected invalid config to be moved to indexed backup"
    assert backup_path.read_text(encoding="utf-8") == ""

    assert target.exists()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == {}

    # Ensure the reset file is readable on subsequent loads.
    subsequent = fingering_config.load_fingering_config()
    assert isinstance(subsequent, dict)

    monkeypatch.delenv(fingering_config._CONFIG_ENV_VAR)  # type: ignore[attr-defined], raises on failure
