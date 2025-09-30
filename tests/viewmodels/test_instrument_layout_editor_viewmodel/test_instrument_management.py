"""Tests covering instrument-level management operations."""

from __future__ import annotations

import pytest

from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel


def test_add_instrument_clones_current_layout(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    original = viewmodel.state

    viewmodel.add_instrument("custom", "Custom")

    new_state = viewmodel.state
    assert new_state.instrument_id == "custom"
    assert new_state.name == "Custom"
    assert new_state.canvas_width == original.canvas_width
    assert new_state.canvas_height == original.canvas_height
    assert new_state.dirty is True
    assert not new_state.note_map
    assert not new_state.note_order
    assert not new_state.candidate_notes

    if original.holes:
        assert new_state.holes is not original.holes
        assert new_state.holes[0].identifier == original.holes[0].identifier


def test_update_instrument_metadata_renames_identifier_and_name(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    original_id = state.instrument_id

    viewmodel.update_instrument_metadata(instrument_id="custom_id", name="Custom Name")

    updated_state = viewmodel.state
    assert updated_state.instrument_id == "custom_id"
    assert updated_state.name == "Custom Name"
    assert updated_state.dirty is True

    choices = dict(viewmodel.choices())
    assert "custom_id" in choices
    assert original_id not in choices


def test_remove_current_instrument_switches_to_previous(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    viewmodel.select_instrument(layout_editor_specs[1].instrument_id)
    removed_id = viewmodel.state.instrument_id

    viewmodel.remove_current_instrument()

    assert removed_id not in dict(viewmodel.choices())
    assert viewmodel.state.instrument_id != removed_id
    assert viewmodel.state.dirty is True


def test_remove_only_instrument_is_rejected(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel([layout_editor_specs[0]])
    with pytest.raises(ValueError):
        viewmodel.remove_current_instrument()
