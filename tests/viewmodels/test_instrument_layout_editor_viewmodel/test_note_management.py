"""Tests for note name handling and instrument import/export."""

from __future__ import annotations

import pytest

from ocarina_gui.fingering import InstrumentSpec
from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name, parse_note_name

from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel


def test_candidate_note_names_include_accidentals(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)

    candidates = viewmodel.candidate_note_names()

    midi_values = []
    for name in viewmodel.state.note_map.keys():
        try:
            midi_values.append(parse_note_name(name))
        except ValueError:
            continue

    assert midi_values, "expected at least one parseable fingering"

    target = next(
        (
            midi
            for midi in sorted(set(midi_values))
            if pitch_midi_to_name(midi, flats=True) != pitch_midi_to_name(midi, flats=False)
        ),
        None,
    )

    if target is None:
        pytest.skip("instrument defines only natural notes")

    flat_name = pitch_midi_to_name(target, flats=True)
    sharp_name = pitch_midi_to_name(target, flats=False)

    assert flat_name in candidates
    assert sharp_name in candidates
    assert flat_name != sharp_name


def test_candidate_note_names_available_after_clearing(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    original = set(viewmodel.candidate_note_names())

    for note in list(viewmodel.state.note_order):
        viewmodel.remove_note(note)

    assert not viewmodel.state.note_map
    assert set(viewmodel.candidate_note_names()) == original


def test_candidate_note_names_available_after_rebuilding(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    original = set(viewmodel.candidate_note_names())

    assert viewmodel.state.note_order
    restored_note = viewmodel.state.note_order[0]
    restored_pattern = list(viewmodel.state.note_map[restored_note])

    for note in list(viewmodel.state.note_order):
        viewmodel.remove_note(note)

    viewmodel.set_note_pattern(restored_note, restored_pattern)

    assert set(viewmodel.candidate_note_names()) == original


def test_candidate_note_range_survives_round_trip(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    viewmodel.select_instrument(layout_editor_specs[1].instrument_id)

    original_candidates = set(viewmodel.candidate_note_names())
    hole_count = len(viewmodel.state.holes)

    for note in list(viewmodel.state.note_order):
        viewmodel.remove_note(note)

    viewmodel.set_note_pattern("A4", [0] * hole_count)

    config = viewmodel.build_config()
    round_tripped_specs = [
        InstrumentSpec.from_dict(entry) for entry in config.get("instruments", [])
    ]

    reloaded = InstrumentLayoutEditorViewModel(round_tripped_specs)
    reloaded.select_instrument(layout_editor_specs[1].instrument_id)

    assert set(reloaded.candidate_note_names()) == original_candidates


def test_import_instrument_preserves_hole_order(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    state = viewmodel.state

    while len(state.holes) < 3:
        viewmodel.add_hole(identifier=f"extra_{len(state.holes)}")
        state = viewmodel.state

    hole_order = list(range(len(state.holes)))
    if len(hole_order) > 1:
        reordered = list(reversed(hole_order))
        if reordered == hole_order:
            reordered = hole_order[1:] + hole_order[:1]
        viewmodel.reorder_holes(reordered)
        state = viewmodel.state

    original_ids = [hole.identifier for hole in state.holes]
    exported = viewmodel.current_instrument_dict()

    imported = viewmodel.import_instrument(exported, conflict_strategy="copy")

    assert [hole.identifier for hole in imported.holes] == original_ids
    for note, pattern in state.note_map.items():
        assert imported.note_map[note] == pattern
