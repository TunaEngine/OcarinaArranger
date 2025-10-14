from __future__ import annotations

import pytest

import ocarina_gui.fingering.library as fingering_library
from ocarina_gui.fingering.library import FingeringLibrary, update_library_from_config
from ocarina_gui.fingering.specs import InstrumentSpec


def _spec(
    instrument_id: str,
    *,
    name: str,
    min_note: str,
    max_note: str,
    candidate_min: str | None = None,
    preferred_min: str | None = None,
) -> InstrumentSpec:
    candidate_min_note = candidate_min if candidate_min is not None else min_note
    preferred_min_note = preferred_min if preferred_min is not None else min_note
    low_notes = list(
        dict.fromkeys([candidate_min_note, preferred_min_note, min_note])
    )
    note_sequence = list(dict.fromkeys(low_notes + [max_note]))
    note_map = {note: [2, 2] for note in low_notes}
    note_map[max_note] = [0, 0]
    return InstrumentSpec.from_dict(
        {
            "id": instrument_id,
            "name": name,
            "title": name,
            "canvas": {"width": 100, "height": 40},
            "holes": [
                {"id": "hole_1", "x": 10, "y": 10, "radius": 5},
                {"id": "hole_2", "x": 25, "y": 20, "radius": 5},
            ],
            "windways": [],
            "note_order": note_sequence,
            "note_map": note_map,
            "candidate_notes": note_sequence,
            "candidate_range": {"min": candidate_min_note, "max": max_note},
            "preferred_range": {"min": preferred_min_note, "max": max_note},
        }
    )


def _choices(library: FingeringLibrary) -> list[str]:
    return [choice.instrument_id for choice in library.choices()]


def test_library_orders_instruments_by_highest_low_note() -> None:
    lower = _spec("low", name="Low", min_note="C4", max_note="E5")
    higher = _spec("high", name="High", min_note="G4", max_note="G6")

    library = FingeringLibrary([lower, higher])

    assert _choices(library) == ["high", "low"]


def test_library_reorders_after_instrument_update() -> None:
    higher = _spec("high", name="High", min_note="G4", max_note="G6")
    lower = _spec("low", name="Low", min_note="C4", max_note="E5")
    library = FingeringLibrary([higher, lower])

    updated_low = _spec("low", name="Low", min_note="A4", max_note="C7")
    library.update_instrument(updated_low)

    assert _choices(library) == ["low", "high"]


def test_library_prefers_candidate_range_minimum() -> None:
    alto = _spec(
        "alto",
        name="Alto",
        min_note="C4",
        max_note="E6",
        candidate_min="A3",
    )
    soprano = _spec("soprano", name="Soprano", min_note="G4", max_note="G6")

    library = FingeringLibrary([alto, soprano])

    assert _choices(library) == ["soprano", "alto"]


def test_library_breaks_ties_by_name_then_identifier() -> None:
    first = _spec("b", name="Bravo", min_note="C4", max_note="E5")
    second = _spec("a", name="Alpha", min_note="C4", max_note="E5")
    third = _spec("c", name="Alpha", min_note="C4", max_note="E5")

    library = FingeringLibrary([first, second, third])

    assert _choices(library) == ["a", "c", "b"]


def test_update_library_from_config_uses_defaults_for_missing_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _spec("existing", name="Existing", min_note="C4", max_note="E5")
    fallback = _spec("fallback", name="Fallback", min_note="D4", max_note="F5")

    original_library = fingering_library._LIBRARY
    fingering_library._LIBRARY = FingeringLibrary([existing])
    monkeypatch.setattr(
        "ocarina_gui.fingering.library._load_default_spec_map",
        lambda: {fallback.instrument_id: fallback},
    )
    monkeypatch.setattr(
        "ocarina_gui.fingering.library.save_fingering_config",
        lambda config: None,
    )

    captured_fallback: set[str] = set()

    def _capture_fallback(config, *, fallback_specs):  # type: ignore[no-untyped-def]
        nonlocal captured_fallback
        if isinstance(fallback_specs, dict):
            captured_fallback = set(fallback_specs.keys())
        else:
            captured_fallback = {
                spec.instrument_id for spec in fallback_specs
            }
        return [existing]

    monkeypatch.setattr(
        "ocarina_gui.fingering.library._instrument_specs_from_config",
        _capture_fallback,
    )

    try:
        update_library_from_config({"instruments": []}, current_instrument_id=None)
    finally:
        fingering_library._LIBRARY = original_library

    assert captured_fallback == {existing.instrument_id, fallback.instrument_id}
