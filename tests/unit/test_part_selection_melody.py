from __future__ import annotations

from ocarina_tools.parts import MusicXmlPartInfo

from shared.melody_part import select_melody_candidate


def _make_part(
    part_id: str,
    *,
    name: str = "",
    note_count: int = 0,
    min_midi: int | None = None,
    max_midi: int | None = None,
) -> MusicXmlPartInfo:
    return MusicXmlPartInfo(
        part_id=part_id,
        name=name,
        midi_program=None,
        note_count=note_count,
        min_midi=min_midi,
        max_midi=max_midi,
        min_pitch=None,
        max_pitch=None,
    )


def test_selects_part_with_melody_name_hint() -> None:
    parts = [
        _make_part("P1", name="Piano RH", note_count=120, min_midi=52, max_midi=90),
        _make_part("P2", name="Lead Vocal", note_count=80, min_midi=60, max_midi=88),
        _make_part("P3", name="Piano LH", note_count=120, min_midi=36, max_midi=60),
    ]

    assert select_melody_candidate(parts) == "P2"


def test_prefers_highest_range_when_names_inconclusive() -> None:
    parts = [
        _make_part(
            "P1", name="Clarinet", note_count=90, min_midi=55, max_midi=92
        ),
        _make_part("P2", name="Violin", note_count=40, min_midi=62, max_midi=96),
        _make_part("P3", name="Bassoon", note_count=110, min_midi=34, max_midi=70),
    ]

    assert select_melody_candidate(parts) == "P2"


def test_falls_back_to_first_part_when_all_data_missing() -> None:
    parts = [
        _make_part("P1"),
        _make_part("P2"),
    ]

    assert select_melody_candidate(parts) == "P1"


def test_prefers_higher_register_over_dense_lower_voice() -> None:
    parts = [
        _make_part(
            "P2",
            name="Part 2",
            note_count=210,
            min_midi=64,
            max_midi=88,
        ),
        _make_part(
            "P12",
            name="Part 12",
            note_count=860,
            min_midi=40,
            max_midi=96,
        ),
        _make_part(
            "P5",
            name="Part 5",
            note_count=120,
            min_midi=48,
            max_midi=84,
        ),
    ]

    assert select_melody_candidate(parts) == "P2"


def test_prefers_higher_top_note_when_one_part_lacks_low_pitch() -> None:
    parts = [
        _make_part(
            "P2",
            name="Part 2",
            note_count=210,
            min_midi=None,
            max_midi=88,
        ),
        _make_part(
            "P12",
            name="Part 12",
            note_count=860,
            min_midi=40,
            max_midi=96,
        ),
    ]

    assert select_melody_candidate(parts) == "P2"


def test_does_not_select_sparse_high_part_over_active_melody() -> None:
    parts = [
        _make_part(
            "P2",
            name="Part 2",
            note_count=180,
            min_midi=60,
            max_midi=86,
        ),
        _make_part(
            "P12",
            name="Part 12",
            note_count=13,
            min_midi=76,
            max_midi=101,
        ),
        _make_part(
            "P5",
            name="Part 5",
            note_count=64,
            min_midi=48,
            max_midi=84,
        ),
    ]

    assert select_melody_candidate(parts) == "P2"


def test_breaks_ties_on_pitch_center_with_higher_top_note() -> None:
    parts = [
        _make_part(
            "P1",
            name="Part 1",
            note_count=120,
            min_midi=60,
            max_midi=80,
        ),
        _make_part(
            "P2",
            name="Part 2",
            note_count=120,
            min_midi=64,
            max_midi=76,
        ),
    ]

    assert select_melody_candidate(parts) == "P1"
