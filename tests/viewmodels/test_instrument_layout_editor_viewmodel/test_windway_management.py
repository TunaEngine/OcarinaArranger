from __future__ import annotations

import pytest

from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel, SelectionKind


def test_add_windway_extends_patterns(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    original_windways = len(state.windways)
    original_patterns = {note: list(pattern) for note, pattern in state.note_map.items()}

    new_windway = viewmodel.add_windway(identifier="new_windway")

    assert len(state.windways) == original_windways + 1
    assert state.windways[-1].identifier == new_windway.identifier
    assert state.selection is not None
    assert state.selection.kind == SelectionKind.WINDWAY
    assert state.selection.index == len(state.windways) - 1

    hole_count = len(state.holes)
    windway_count = len(state.windways)
    for note, pattern in state.note_map.items():
        assert len(pattern) == hole_count + windway_count
        original = original_patterns.get(note, [])
        assert pattern[:hole_count] == original[:hole_count]
        if original_windways:
            assert pattern[-windway_count:-1] == original[-original_windways:]
        assert pattern[-1] == 0


def test_remove_windway_updates_patterns_and_selection(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    if not state.windways:
        viewmodel.add_windway(identifier="temp_windway")
    state = viewmodel.state
    viewmodel.select_element(SelectionKind.WINDWAY, 0)

    original_patterns = {note: list(pattern) for note, pattern in state.note_map.items()}
    removed_identifier = state.windways[0].identifier

    viewmodel.remove_windway(0)
    state = viewmodel.state

    assert removed_identifier not in [windway.identifier for windway in state.windways]
    hole_count = len(state.holes)
    windway_count = len(state.windways)
    for note, pattern in state.note_map.items():
        assert len(pattern) == hole_count + windway_count
        original = original_patterns.get(note, [])
        if original:
            assert pattern[:hole_count] == original[:hole_count]
            if windway_count:
                assert pattern[-windway_count:] == original[-windway_count - 1 : -1]

    selection = state.selection
    if state.windways:
        assert selection is not None
        assert selection.kind == SelectionKind.WINDWAY
        assert 0 <= selection.index < len(state.windways)
    else:
        assert selection is None


def test_update_and_resize_windway(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    if not state.windways:
        viewmodel.add_windway(identifier="temp")
        state = viewmodel.state

    viewmodel.update_windway_identifier(0, "Primary Chamber")
    assert state.windways[0].identifier == "Primary Chamber"

    with pytest.raises(ValueError):
        viewmodel.update_windway_identifier(0, "")

    original_width = state.windways[0].width
    original_height = state.windways[0].height
    viewmodel.set_windway_size(0, original_width + 5.0, original_height + 3.0)
    assert state.windways[0].width == pytest.approx(original_width + 5.0)
    assert state.windways[0].height == pytest.approx(original_height + 3.0)
