"""Tests for layout editor config helpers."""

from __future__ import annotations

from ocarina_gui.layout_editor.window import config


def test_resolve_instrument_entry_finds_match_in_list() -> None:
    instrument = {"id": "triple", "name": "Triple", "holes": []}
    data = {"instruments": [instrument]}

    result = config._resolve_instrument_entry(data, "triple")

    assert result == instrument
    assert result is not instrument, "expected a defensive copy of the entry"


def test_resolve_instrument_entry_accepts_mapping_payload() -> None:
    instrument = {"id": "double", "name": "Double", "holes": []}
    data = {"instruments": {"double": instrument}}

    result = config._resolve_instrument_entry(data, "double")

    assert result == instrument
    assert result is not instrument


def test_resolve_instrument_entry_returns_none_when_missing() -> None:
    data = {"instruments": [{"id": "alpha", "name": "Alpha", "holes": []}]}

    assert config._resolve_instrument_entry(data, "beta") is None
