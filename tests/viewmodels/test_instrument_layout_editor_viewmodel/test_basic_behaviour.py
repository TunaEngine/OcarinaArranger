"""Basic state and selection behaviours for the instrument layout editor view-model."""

from __future__ import annotations

import pytest

from viewmodels.instrument_layout_editor import (
    InstrumentLayoutEditorViewModel,
    SelectionKind,
)


def test_viewmodel_initializes_from_first_instrument(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    source = layout_editor_specs[0]
    assert state.instrument_id == source.instrument_id
    assert state.name == source.name
    assert state.canvas_width == source.canvas_size[0]
    assert state.canvas_height == source.canvas_size[1]
    assert len(state.holes) == len(source.holes)


def test_select_instrument_switches_state(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    target = layout_editor_specs[1]

    viewmodel.select_instrument(target.instrument_id)

    assert viewmodel.state.instrument_id == target.instrument_id


def test_move_hole_updates_state_and_marks_dirty(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    assert state.holes, "instrument should define at least one hole"
    viewmodel.select_element(SelectionKind.HOLE, 0)
    viewmodel.set_selected_position(100.0, 150.0)

    assert state.holes[0].x == 100.0
    assert state.holes[0].y == 150.0
    assert state.dirty is True


def test_adjust_radius_updates_selected_element(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    viewmodel.select_element(SelectionKind.HOLE, 0)
    original = state.holes[0].radius

    viewmodel.adjust_selected_radius(+2.5)
    assert state.holes[0].radius == pytest.approx(original + 2.5)

    viewmodel.adjust_selected_radius(-5.0)
    assert state.holes[0].radius == pytest.approx(original - 2.5)


def test_outline_point_can_be_moved_if_present(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    if not state.outline_points:
        pytest.skip("instrument has no outline defined")

    original_x = state.outline_points[0].x
    original_y = state.outline_points[0].y
    viewmodel.select_element(SelectionKind.OUTLINE, 0)
    viewmodel.set_selected_position(original_x + 10.0, original_y + 5.0)

    updated = state.outline_points[0]
    assert updated.x == pytest.approx(original_x + 10.0)
    assert updated.y == pytest.approx(original_y + 5.0)


def test_current_instrument_dict_reflects_changes(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)

    viewmodel.select_element(SelectionKind.HOLE, 0)
    viewmodel.set_selected_position(80.0, 60.0)

    data = viewmodel.current_instrument_dict()
    hole = data["holes"][0]
    assert hole["x"] == pytest.approx(80.0)
    assert hole["y"] == pytest.approx(60.0)
