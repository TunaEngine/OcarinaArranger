from __future__ import annotations

import copy

import pytest

from ocarina_gui import fingering


_BASE_INSTRUMENT_ENTRY: dict[str, object] = {
    "id": "concert_c",
    "name": "Concert C",
    "title": "Concert C",
    "canvas": {"width": 180, "height": 120},
    "style": {
        "background_color": "#0a0a0a",
        "outline_color": "#fafafa",
        "outline_width": 2.5,
        "outline_smooth": True,
        "outline_spline_steps": 36,
        "hole_outline_color": "#cccccc",
        "covered_fill_color": "#333333",
    },
    "outline": {
        "points": [[0.0, 0.0], [120.0, 10.0], [140.0, 60.0]],
        "closed": True,
    },
    "holes": [
        {"id": "thumb", "x": 16.5, "y": 24.0, "radius": 8.0},
        {"id": "index", "x": 44.0, "y": 32.5, "radius": 7.5},
        {"id": "middle", "x": 74.5, "y": 39.0, "radius": 7.0},
    ],
    "windways": [
        {"id": "primary", "x": 22.0, "y": 12.0, "width": 18.0, "height": 9.0},
        {"id": "secondary", "x": 42.0, "y": 14.0, "width": 16.0, "height": 8.0},
    ],
    "note_order": ["C5", "D5", "E5"],
    "note_map": {
        "C5": [2, 2, 2, 2, 2],
        "D5": [2, 2, 0, 2, 2],
        "E5": [2, 1, 0, 2, 2],
    },
    "candidate_notes": ["B4", "C5", "D5", "E5"],
    "candidate_range": {"min": "B4", "max": "F6"},
}


def _instrument_entry(**overrides: object) -> dict[str, object]:
    entry = copy.deepcopy(_BASE_INSTRUMENT_ENTRY)
    entry.update(overrides)
    return entry


@pytest.fixture
def sample_library(monkeypatch):
    from ocarina_gui.fingering import library as library_module

    entry = _instrument_entry()
    spec = fingering.InstrumentSpec.from_dict(copy.deepcopy(entry))
    library = library_module.FingeringLibrary([spec])

    saved_configs: list[dict[str, object]] = []

    def _capture(config: dict[str, object]) -> None:
        saved_configs.append(copy.deepcopy(config))

    monkeypatch.setattr(library_module, "_LIBRARY", library)
    monkeypatch.setattr(fingering, "_LIBRARY", library)
    monkeypatch.setattr(library_module, "save_fingering_config", _capture)

    return {
        "spec": spec,
        "saved_configs": saved_configs,
    }


def test_hole_spec_round_trip_preserves_fields():
    sample = {"id": "hole_a", "x": 12.5, "y": 44.0, "radius": 9.25}
    spec = fingering.HoleSpec.from_dict(sample)
    assert spec.to_dict() == sample
def test_outline_spec_round_trip_preserves_points():
    sample = {"points": [[0, 0], [10, 5], [6, 18]], "closed": True}
    spec = fingering.OutlineSpec.from_dict(sample)
    assert spec is not None
    assert spec.to_dict() == sample


def test_windway_spec_round_trip_preserves_fields():
    sample = {"id": "windway", "x": 10.0, "y": 15.0, "width": 12.0, "height": 6.5}
    spec = fingering.WindwaySpec.from_dict(sample)
    assert spec.to_dict() == sample


def test_style_spec_round_trip_preserves_colors():
    sample = {
        "background_color": "#112233",
        "outline_color": "#445566",
        "outline_width": 2.5,
        "outline_smooth": True,
        "outline_spline_steps": 30,
        "hole_outline_color": "#223344",
        "covered_fill_color": "#556677",
    }
    spec = fingering.StyleSpec.from_dict(sample)
    assert spec.to_dict() == sample


def test_style_spec_defaults_enable_smoothing():
    spec = fingering.StyleSpec.from_dict({})
    assert spec.outline_smooth is True
    assert spec.to_dict()["outline_smooth"] is True


def test_instrument_spec_round_trip_matches_source_config():
    original = _instrument_entry()

    spec = fingering.InstrumentSpec.from_dict(copy.deepcopy(original))

    assert spec.to_dict() == original


def test_instrument_spec_preserves_hole_order():
    sample = {
        "id": "order_spec",
        "name": "Order Spec",
        "title": "Order Spec",
        "canvas": {"width": 180, "height": 120},
        "holes": [
            {"id": "thumb", "x": 10, "y": 15, "radius": 7},
            {"id": "index", "x": 22, "y": 18, "radius": 6.5},
            {"id": "middle", "x": 34, "y": 22, "radius": 6},
        ],
        "windways": [
            {"id": "primary", "x": 12, "y": 8, "width": 16, "height": 8},
        ],
        "note_order": ["A4"],
        "note_map": {"A4": [2, 2, 0, 2]},
    }

    spec = fingering.InstrumentSpec.from_dict(sample)

    assert [hole.identifier for hole in spec.holes] == [hole["id"] for hole in sample["holes"]]

    rebuilt = spec.to_dict()
    assert [hole["id"] for hole in rebuilt["holes"]] == [hole["id"] for hole in sample["holes"]]


def test_instrument_spec_preserves_explicit_candidate_notes():
    sample = {
        "id": "test_range",
        "name": "Test Range",
        "title": "Test Range",
        "canvas": {"width": 200, "height": 120},
        "holes": [],
        "windways": [
            {"id": "primary", "x": 18, "y": 10, "width": 14, "height": 6}
        ],
        "note_order": ["A4"],
        "note_map": {"A4": [2]},
        "candidate_notes": ["G4", "A4", "B4"],
    }

    spec = fingering.InstrumentSpec.from_dict(sample)

    assert tuple(sample["candidate_notes"]) == spec.candidate_notes
    rebuilt = spec.to_dict()
    assert rebuilt.get("candidate_notes") == sample["candidate_notes"]


def test_instrument_spec_preserves_candidate_range():
    sample = _instrument_entry(
        id="with_range",
        candidate_range={"min": "A4", "max": "G6"},
    )

    spec = fingering.InstrumentSpec.from_dict(sample)

    assert spec.candidate_range_min == "A4"
    assert spec.candidate_range_max == "G6"
    rebuilt = spec.to_dict()
    assert rebuilt.get("candidate_range") == sample["candidate_range"]


def test_instrument_specs_use_fallback_candidates_when_missing():
    source = _instrument_entry()
    fallback_spec = fingering.InstrumentSpec.from_dict(copy.deepcopy(source))

    trimmed = copy.deepcopy(source)
    trimmed.pop("candidate_notes", None)
    trimmed.pop("candidate_range", None)
    retained_note = fallback_spec.note_order[0]
    trimmed["note_order"] = [retained_note]
    trimmed["note_map"] = {retained_note: fallback_spec.note_map[retained_note]}

    rebuilt = fingering._instrument_specs_from_config(  # type: ignore[attr-defined]
        {"instruments": [trimmed]},
        fallback_specs=[fallback_spec],
    )

    assert rebuilt[0].candidate_notes == fallback_spec.candidate_notes
    assert rebuilt[0].candidate_range_min == fallback_spec.candidate_range_min
    assert rebuilt[0].candidate_range_max == fallback_spec.candidate_range_max


def test_instrument_specs_merge_fallback_candidates_when_partial():
    source = _instrument_entry()
    fallback_spec = fingering.InstrumentSpec.from_dict(copy.deepcopy(source))

    trimmed = copy.deepcopy(source)
    retained_note = fallback_spec.note_order[0]
    trimmed_candidates = [retained_note]
    trimmed["candidate_notes"] = trimmed_candidates
    trimmed["candidate_range"] = {"min": retained_note, "max": retained_note}
    trimmed["note_order"] = [retained_note]
    trimmed["note_map"] = {retained_note: fallback_spec.note_map[retained_note]}

    rebuilt = fingering._instrument_specs_from_config(  # type: ignore[attr-defined]
        {"instruments": [trimmed]},
        fallback_specs=[fallback_spec],
    )

    assert list(rebuilt[0].candidate_notes[: len(trimmed_candidates)]) == trimmed_candidates
    assert set(rebuilt[0].candidate_notes) == set(fallback_spec.candidate_notes)
    assert rebuilt[0].candidate_range_min == fallback_spec.candidate_range_min
    assert rebuilt[0].candidate_range_max == fallback_spec.candidate_range_max


def test_update_library_from_config_replaces_instruments(sample_library):
    entry = _instrument_entry(id="test_custom", name="Test Custom", title="Test Custom")
    new_config = {"instruments": [entry]}

    fingering.update_library_from_config(new_config, current_instrument_id="test_custom")

    current = fingering.get_current_instrument()
    assert current.instrument_id == "test_custom"
    assert current.name == "Test Custom"
    choices = fingering.get_available_instruments()
    assert any(choice.instrument_id == "test_custom" for choice in choices)


def test_update_library_preserves_note_map_values(sample_library):
    entry = _instrument_entry()
    instrument_id = entry["id"]
    had_true = False
    for note, pattern in list(entry.get("note_map", {}).items()):
        boolean_pattern = []
        for value in pattern:
            flag = bool(value)
            had_true = had_true or flag
            boolean_pattern.append(flag)
        entry["note_map"][note] = boolean_pattern

    fingering.update_library_from_config({"instruments": [entry]}, current_instrument_id=instrument_id)
    current = fingering.get_instrument(instrument_id)
    seen_true = False
    for values in current.note_map.values():
        assert all(value in (0, 2) for value in values)
        seen_true = seen_true or any(value == 2 for value in values)
    if had_true:
        assert seen_true, "expected boolean True values to map to fully covered"


def test_update_library_preserves_hole_order(sample_library):
    entry = _instrument_entry(
        holes=[
            {"id": "alpha", "x": 10.0, "y": 12.0, "radius": 7.0},
            {"id": "beta", "x": 20.0, "y": 18.0, "radius": 6.0},
            {"id": "gamma", "x": 30.0, "y": 24.0, "radius": 5.0},
        ],
        note_order=["C5"],
        note_map={"C5": [2, 1, 0]},
    )
    instrument_id = entry["id"]

    fingering.update_library_from_config({"instruments": [entry]}, current_instrument_id=instrument_id)
    current = fingering.get_instrument(instrument_id)

    assert [hole.identifier for hole in current.holes] == [hole["id"] for hole in entry["holes"]]


def test_update_library_persists_to_user_override(sample_library):
    entry = _instrument_entry(id="persist_test", name="Persist Test", title="Persist Test")
    updated = {"instruments": [entry]}

    fingering.update_library_from_config(updated, current_instrument_id="persist_test")

    assert sample_library["saved_configs"], "configuration should be persisted"
    assert sample_library["saved_configs"][-1] == updated


def test_update_instrument_spec_refreshes_library_without_persist(sample_library):
    original = sample_library["spec"]
    updated = original.to_dict()
    first_note = next(iter(updated["note_map"]))
    updated_pattern = [0 if value >= 2 else 2 for value in updated["note_map"][first_note]]
    updated["note_map"][first_note] = updated_pattern

    spec = fingering.InstrumentSpec.from_dict(updated)

    fingering.update_instrument_spec(spec)

    current = fingering.get_instrument(spec.instrument_id)
    assert current.note_map[first_note] == updated_pattern
    assert sample_library["saved_configs"] == []
