from ocarina_gui.staff.rendering.geometry import (
    staff_pos,
    staff_y,
    tie_control_offsets,
)


def test_staff_pos_matches_expected_treble_positions() -> None:
    assert staff_pos(64) == 0
    assert staff_pos(60) == -2
    assert staff_pos(67) == 2
    assert staff_pos(72) == 5


def test_staff_y_uses_same_spacing_formula() -> None:
    assert staff_y(10.0, 0, 8.0) == 42.0
    assert staff_y(0.0, 8, 10.0) == 0.0


def test_tie_control_offsets_follow_staff_direction() -> None:
    base, curve = tie_control_offsets(8.0, 4)
    assert base > 0 and curve > base

    base, curve = tie_control_offsets(8.0, 8)
    assert base < 0 and curve < base
