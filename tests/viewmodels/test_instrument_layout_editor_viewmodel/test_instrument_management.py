"""Tests covering instrument-level management operations."""

from __future__ import annotations

import pytest

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name, parse_note_name

from ocarina_gui.fingering import InstrumentSpec
from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel


def _range_names(minimum: str, maximum: str) -> list[str]:
    start = parse_note_name(minimum)
    end = parse_note_name(maximum)
    return [pitch_midi_to_name(midi, flats=False) for midi in range(start, end + 1)]


def _build_spec(
    identifier: str,
    name: str,
    *,
    hole_count: int,
    windway_count: int,
    notes: list[str],
    candidate_min: str,
    candidate_max: str,
) -> InstrumentSpec:
    holes = [
        {"id": f"H{index + 1}", "x": 60.0 + index * 20.0, "y": 60.0, "radius": 7.0}
        for index in range(hole_count)
    ]
    windways = [
        {"id": f"W{index + 1}", "x": 40.0 + index * 18.0, "y": 28.0, "width": 18.0, "height": 10.0}
        for index in range(windway_count)
    ]

    note_map: dict[str, list[int]] = {}
    total = hole_count + windway_count
    for idx, note in enumerate(notes):
        pattern = []
        for hole_index in range(hole_count):
            pattern.append(1 if idx % 2 == hole_index % 2 else 0)
        pattern.extend([2] * windway_count)
        # Normalise to the expected length in case counts are zero.
        if len(pattern) < total:
            pattern.extend([0] * (total - len(pattern)))
        elif len(pattern) > total:
            pattern = pattern[:total]
        note_map[note] = pattern

    data = {
        "id": identifier,
        "name": name,
        "title": name,
        "canvas": {"width": 240, "height": 140},
        "holes": holes,
        "windways": windways,
        "note_order": notes,
        "note_map": note_map,
        "preferred_range": {"min": candidate_min, "max": candidate_max},
        "candidate_range": {"min": candidate_min, "max": candidate_max},
    }
    return InstrumentSpec.from_dict(data)


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


def test_load_config_preserves_explicit_range(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    instrument_id = layout_editor_specs[0].instrument_id

    viewmodel.set_candidate_range("C5", "E5")
    config = viewmodel.build_config()

    reloaded = InstrumentLayoutEditorViewModel(layout_editor_specs)
    reloaded.load_config(config, current_instrument_id=instrument_id)
    reloaded.select_instrument(instrument_id)

    state = reloaded.state
    assert state.candidate_range_min == "C5"
    assert state.candidate_range_max == "E5"


def test_load_config_preserves_trimmed_candidate_notes(layout_editor_specs) -> None:
    viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
    instrument_id = layout_editor_specs[0].instrument_id

    viewmodel.set_candidate_range("C5", "C5")
    config = viewmodel.build_config()

    reloaded = InstrumentLayoutEditorViewModel(layout_editor_specs)
    reloaded.load_config(config, current_instrument_id=instrument_id)
    reloaded.select_instrument(instrument_id)

    state = reloaded.state
    assert list(state.candidate_notes) == ["C5"]
    assert list(state.note_map.keys()) == ["C5"]


def test_copyable_instrument_choices_filters_by_geometry() -> None:
    donor = _build_spec(
        "donor",
        "Donor",
        hole_count=3,
        windway_count=1,
        notes=["C4", "D4", "E4"],
        candidate_min="C4",
        candidate_max="E4",
    )
    recipient = _build_spec(
        "recipient",
        "Recipient",
        hole_count=3,
        windway_count=1,
        notes=["C5"],
        candidate_min="C5",
        candidate_max="E5",
    )
    incompatible = _build_spec(
        "incompatible",
        "Incompatible",
        hole_count=4,
        windway_count=1,
        notes=["C4"],
        candidate_min="C4",
        candidate_max="F4",
    )

    viewmodel = InstrumentLayoutEditorViewModel([donor, recipient, incompatible])
    viewmodel.select_instrument(recipient.instrument_id)

    choices = viewmodel.copyable_instrument_choices()

    assert choices == [(donor.instrument_id, donor.name)]


def test_copy_fingerings_trims_to_target_range() -> None:
    donor = _build_spec(
        "donor",
        "Donor",
        hole_count=3,
        windway_count=1,
        notes=[
            "C4",
            "D4",
            "E4",
            "F4",
            "G4",
            "A4",
            "B4",
            "C5",
            "D5",
            "E5",
        ],
        candidate_min="C4",
        candidate_max="E5",
    )
    recipient = _build_spec(
        "recipient",
        "Recipient",
        hole_count=3,
        windway_count=1,
        notes=["G4"],
        candidate_min="G4",
        candidate_max="D5",
    )

    viewmodel = InstrumentLayoutEditorViewModel([donor, recipient])
    viewmodel.select_instrument(recipient.instrument_id)

    viewmodel.copy_fingerings_from(donor.instrument_id)

    state = viewmodel.state
    assert list(state.note_map.keys()) == ["G4", "A4", "B4", "C5", "D5"]
    assert state.candidate_range_min == "G4"
    assert state.candidate_range_max == "D5"
    assert state.preferred_range_min == "G4"
    assert state.preferred_range_max == "D5"
    assert state.dirty is True
    assert all(note not in state.note_map for note in ("C4", "E5"))
    assert state.candidate_notes[0] == "G4"
    assert state.candidate_notes[-1] == "D5"


def test_copy_fingerings_transposes_to_target_range() -> None:
    donor_notes = _range_names("A4", "F6")
    donor = _build_spec(
        "donor",
        "Donor",
        hole_count=4,
        windway_count=1,
        notes=donor_notes,
        candidate_min="A4",
        candidate_max="F6",
    )
    recipient = _build_spec(
        "recipient",
        "Recipient",
        hole_count=4,
        windway_count=1,
        notes=["A3"],
        candidate_min="A3",
        candidate_max="F5",
    )

    viewmodel = InstrumentLayoutEditorViewModel([donor, recipient])
    viewmodel.select_instrument(recipient.instrument_id)

    viewmodel.copy_fingerings_from(donor.instrument_id)

    expected = _range_names("A3", "F5")
    state = viewmodel.state
    assert list(state.note_map.keys()) == expected
    assert state.note_order == expected
    assert state.candidate_notes[: len(expected)] == expected
    assert state.candidate_range_min == "A3"
    assert state.candidate_range_max == "F5"
    assert state.preferred_range_min == "A3"
    assert state.preferred_range_max == "F5"
    assert state.dirty is True


def test_copy_fingerings_prefers_note_bounds_over_candidate_range() -> None:
    donor_notes = _range_names("C5", "F6")
    donor = _build_spec(
        "donor",
        "Donor",
        hole_count=6,
        windway_count=0,
        notes=donor_notes,
        candidate_min="A4",
        candidate_max="F6",
    )
    recipient = _build_spec(
        "recipient",
        "Recipient",
        hole_count=6,
        windway_count=0,
        notes=["F5"],
        candidate_min="F5",
        candidate_max="A6",
    )

    viewmodel = InstrumentLayoutEditorViewModel([donor, recipient])
    viewmodel.select_instrument(recipient.instrument_id)

    viewmodel.copy_fingerings_from(donor.instrument_id)

    expected = _range_names("F5", "A6")
    state = viewmodel.state
    assert list(state.note_map.keys()) == expected
    assert state.note_order == expected
    assert state.candidate_notes[: len(expected)] == expected
    assert state.candidate_range_min == "F5"
    assert state.candidate_range_max == "A6"
    assert state.preferred_range_min == "F5"
    assert state.preferred_range_max == "A6"
    assert state.dirty is True


def test_copy_fingerings_rejects_incompatible_layout() -> None:
    donor = _build_spec(
        "donor",
        "Donor",
        hole_count=3,
        windway_count=1,
        notes=["C4", "D4"],
        candidate_min="C4",
        candidate_max="D4",
    )
    recipient = _build_spec(
        "recipient",
        "Recipient",
        hole_count=2,
        windway_count=1,
        notes=["C5"],
        candidate_min="C5",
        candidate_max="D5",
    )

    viewmodel = InstrumentLayoutEditorViewModel([donor, recipient])
    viewmodel.select_instrument(recipient.instrument_id)

    with pytest.raises(ValueError):
        viewmodel.copy_fingerings_from(donor.instrument_id)
