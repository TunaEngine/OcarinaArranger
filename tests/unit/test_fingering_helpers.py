from ocarina_gui.fingering import (
    calculate_grid_columns,
    InstrumentSpec,
    collect_instrument_note_names,
    parse_note_name_safe,
)


def build_instrument(**overrides):
    spec = {
        "id": "test",
        "name": "Test",
        "title": "Test",
        "canvas": {"width": 120, "height": 80},
        "holes": [
            {"id": "h1", "x": 10, "y": 10, "radius": 4},
            {"id": "h2", "x": 30, "y": 10, "radius": 4},
        ],
        "note_order": ["C4", "D4", "E4"],
        "note_map": {
            "Bb3": [2, 2],
            "C4": [2, 2],
            "Db4": [2, 1],
            "E4": [0, 0],
            "Invalid": [0, 0],
        },
        "candidate_range": {"min": "A#3", "max": "E4"},
    }
    spec.update(overrides)
    return InstrumentSpec.from_dict(spec)


def test_collect_instrument_note_names_sorted_unique():
    instrument = build_instrument()
    names = collect_instrument_note_names(instrument)
    assert names[:4] == ["A#3", "Bb3", "B3", "C4"]
    assert "D#4" in names
    assert "C#4" in names
    assert names[-1] == "Invalid"


def test_parse_note_name_safe_handles_invalid_entries():
    assert parse_note_name_safe("C4") == 60
    assert parse_note_name_safe("Invalid") is None
    assert parse_note_name_safe("Bb3") == 58


def test_calculate_grid_columns_uses_available_width():
    assert calculate_grid_columns(500, 100, 10) == 4


def test_calculate_grid_columns_never_returns_zero():
    assert calculate_grid_columns(0, 120, 8) == 1
    assert calculate_grid_columns(-50, 120, 8) == 1


def test_calculate_grid_columns_single_tile_when_width_small():
    assert calculate_grid_columns(90, 80, 8) == 1
