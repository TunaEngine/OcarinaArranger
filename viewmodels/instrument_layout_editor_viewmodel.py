"""Backward-compatible shims for the instrument layout editor view-model."""

from .instrument_layout_editor import (
    EditableHole,
    EditableStyle,
    InstrumentLayoutEditorViewModel,
    InstrumentLayoutState,
    OutlinePoint,
    Selection,
    SelectionKind,
    clone_state,
    state_from_spec,
    state_to_dict,
)

__all__ = [
    "EditableHole",
    "EditableStyle",
    "InstrumentLayoutEditorViewModel",
    "InstrumentLayoutState",
    "OutlinePoint",
    "Selection",
    "SelectionKind",
    "clone_state",
    "state_from_spec",
    "state_to_dict",
]
