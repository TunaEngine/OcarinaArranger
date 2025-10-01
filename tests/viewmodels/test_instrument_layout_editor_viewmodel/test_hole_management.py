"""Tests for hole creation, removal, and reordering."""

from __future__ import annotations

import pytest

from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel, SelectionKind
from viewmodels.instrument_layout_editor.note_patterns import normalize_pattern

from .helpers import note_sort_key


def test_add_hole_extends_note_map_and_selects_new_hole(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    original_count = len(state.holes)
    original_maps = {note: list(pattern) for note, pattern in state.note_map.items()}

    new_hole = viewmodel.add_hole(identifier="new_hole")

    assert len(state.holes) == original_count + 1
    assert state.holes[-1].identifier == new_hole.identifier
    assert state.selection is not None
    assert state.selection.kind == SelectionKind.HOLE
    assert state.selection.index == len(state.holes) - 1
    windway_count = len(state.windways)
    for note, pattern in state.note_map.items():
        assert len(pattern) == len(state.holes) + windway_count
        original_pattern = original_maps.get(note)
        if original_pattern is not None:
            assert pattern[:original_count] == original_pattern[:original_count]
            if windway_count:
                assert pattern[-windway_count:] == original_pattern[-windway_count:]
        assert pattern[original_count] == 0
    assert state.dirty is True


def test_remove_hole_shortens_patterns_and_updates_selection(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    if len(state.holes) < 2:
        viewmodel.add_hole(identifier="temp_hole")
    state = viewmodel.state
    viewmodel.select_element(SelectionKind.HOLE, 0)
    original_maps = {note: list(pattern) for note, pattern in state.note_map.items()}
    removed_identifier = state.holes[0].identifier

    viewmodel.remove_hole(0)

    state = viewmodel.state
    assert removed_identifier not in [hole.identifier for hole in state.holes]
    windway_count = len(state.windways)
    for note, pattern in state.note_map.items():
        assert len(pattern) == len(state.holes) + windway_count
        if note in original_maps and original_maps[note]:
            original_pattern = original_maps[note]
            expected_holes = original_pattern[1 : len(state.holes) + 1]
            assert pattern[: len(state.holes)] == expected_holes
            if windway_count:
                assert pattern[-windway_count:] == original_pattern[-windway_count:]
    selection = state.selection
    if state.holes:
        assert selection is not None
        assert selection.kind == SelectionKind.HOLE
        assert 0 <= selection.index < len(state.holes)
    else:
        assert selection is None


def test_reorder_holes_updates_state_and_patterns(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    viewmodel.select_instrument(layout_editor_specs[1].instrument_id)
    state = viewmodel.state

    hole_count = len(state.holes)
    windway_count = len(state.windways)
    if hole_count < 2:
        pytest.skip("instrument must define at least two holes")

    original_identifiers = [hole.identifier for hole in state.holes]
    original_patterns = {note: list(pattern) for note, pattern in state.note_map.items()}

    selected_index = 0 if hole_count == 2 else 1
    viewmodel.select_element(SelectionKind.HOLE, selected_index)
    selected_identifier = original_identifiers[selected_index]

    new_order = list(range(1, hole_count)) + [0]
    viewmodel.reorder_holes(new_order)

    assert [hole.identifier for hole in state.holes] == [
        original_identifiers[index] for index in new_order
    ]

    for note, pattern in state.note_map.items():
        normalized = normalize_pattern(  # type: ignore[name-defined]
            original_patterns[note], hole_count, windway_count
        )
        expected_holes = [normalized[index] for index in new_order]
        expected = expected_holes + normalized[hole_count : hole_count + windway_count]
        assert pattern == expected

    selection = state.selection
    assert selection is not None
    assert selection.kind == SelectionKind.HOLE
    assert state.holes[selection.index].identifier == selected_identifier
    assert state.dirty is True


def test_update_hole_identifier_validates_uniqueness(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    viewmodel.update_hole_identifier(0, "Primary")
    assert state.holes[0].identifier == "Primary"

    with pytest.raises(ValueError):
        viewmodel.update_hole_identifier(0, "")

    if len(state.holes) > 1:
        duplicate = state.holes[1].identifier
        with pytest.raises(ValueError):
            viewmodel.update_hole_identifier(0, duplicate)


def test_note_pattern_helpers_normalize_and_copy(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    hole_count = len(state.holes)
    if hole_count == 0:
        viewmodel.add_hole(identifier="auto")
        state = viewmodel.state
        hole_count = len(state.holes)

    patterns = viewmodel.note_patterns()
    if patterns:
        note, values = next(iter(patterns.items()))
        values[0] = 99
        assert viewmodel.state.note_map[note][0] != 99

    viewmodel.set_note_pattern("Custom", [1] * (hole_count + 2))
    assert state.note_map["Custom"] == [1] * hole_count + [2] * len(state.windways)
    expected_order = sorted(state.note_map.keys(), key=note_sort_key)
    assert state.note_order == expected_order
    assert state.dirty is True
