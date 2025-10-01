from __future__ import annotations

from ocarina_gui.fingering import (
    InstrumentSpec,
    StyleSpec,
    collect_instrument_note_names,
    preferred_note_window,
)


def test_preferred_note_window_defaults_to_full_range() -> None:
    spec = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test",
            "title": "Test",
            "canvas": {"width": 10, "height": 10},
            "holes": [],
            "note_order": ["C5", "D5", "E5"],
            "note_map": {"C5": [], "D5": [], "E5": []},
        }
    )
    low, high = preferred_note_window(spec)
    notes = collect_instrument_note_names(spec)
    assert notes == ["C5", "C#5", "D5", "D#5", "E5"]
    assert low == "C5"
    assert high == "E5"


def test_preferred_note_window_uses_explicit_range() -> None:
    spec = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test",
            "title": "Test",
            "canvas": {"width": 10, "height": 10},
            "holes": [],
            "note_order": ["C5", "D5", "E5"],
            "note_map": {"C5": [], "D5": [], "E5": []},
            "preferred_range": {"min": "D5", "max": "E5"},
        }
    )
    assert preferred_note_window(spec) == ("D5", "E5")


def test_preferred_note_window_handles_single_note() -> None:
    spec = InstrumentSpec(
        instrument_id="test",
        name="Test",
        title="Test",
        canvas_size=(10, 10),
        style=StyleSpec(),
        outline=None,
        holes=[],
        windways=[],
        note_order=("C5",),
        note_map={},
    )
    low, high = preferred_note_window(spec)
    assert low == "C5"
    assert high == "C5"
