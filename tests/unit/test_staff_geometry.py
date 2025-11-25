import pytest

from ocarina_gui.staff.rendering.geometry import staff_pos


@pytest.mark.parametrize(
    "midi, expected",
    [
        (64, 0),  # E4 baseline
        (69, 3),  # A4
        (70, 3),  # A#4 shares A's staff slot
        (71, 4),  # B4
        (66, 1),  # F#4 maps to F line
        (73, 5),  # C#5 maps to C space above the staff
        (58, -4),  # A#3 matches A3 ledger line
    ],
)
def test_staff_positions_align_accidentals_with_natural_slots(midi: int, expected: int) -> None:
    assert staff_pos(midi) == expected
