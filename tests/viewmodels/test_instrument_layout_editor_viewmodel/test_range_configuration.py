"""Tests focused on preferred range settings and validation."""

from __future__ import annotations

import pytest

from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel


def test_set_preferred_range_updates_state(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state
    notes = viewmodel.candidate_note_names()
    assert len(notes) >= 2

    viewmodel.set_preferred_range(notes[1], notes[-1])

    assert state.preferred_range_min == notes[1]
    assert state.preferred_range_max == notes[-1]
    assert state.dirty is True


def test_set_preferred_range_validates_inputs(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    notes = viewmodel.candidate_note_names()
    with pytest.raises(ValueError):
        viewmodel.set_preferred_range(notes[-1], notes[0])
