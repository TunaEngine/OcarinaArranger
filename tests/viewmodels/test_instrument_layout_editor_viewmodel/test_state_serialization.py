"""Tests covering serialization of instrument layout state."""

from viewmodels.instrument_layout_editor import (
    InstrumentLayoutEditorViewModel,
    state_from_spec,
)
from ocarina_gui.fingering import InstrumentSpec


def test_subhole_flag_round_trips(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    assert state.holes, "fixture should provide at least one hole"

    original_flag = state.holes[0].is_subhole
    toggled_flag = not original_flag
    viewmodel.set_hole_subhole(0, toggled_flag)

    serialized = viewmodel.current_instrument_dict()
    hole_data = serialized["holes"][0]
    assert hole_data["is_subhole"] == toggled_flag

    spec = InstrumentSpec.from_dict(serialized)
    assert spec.holes[0].is_subhole == toggled_flag

    restored_state = state_from_spec(spec)
    assert restored_state.holes[0].is_subhole == toggled_flag
