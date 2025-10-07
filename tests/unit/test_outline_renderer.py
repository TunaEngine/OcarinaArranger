import pytest

from ocarina_gui.fingering import outline_renderer
from ocarina_gui.fingering.outline_renderer import generate_outline_path


@pytest.mark.parametrize("smooth", [False, True])
def test_generate_outline_path_returns_at_least_original_points(smooth: bool) -> None:
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    path = generate_outline_path(points, smooth=smooth, closed=False, spline_steps=8)
    assert len(path) >= len(points)
    assert pytest.approx(path[0][0]) == points[0][0]
    assert pytest.approx(path[0][1]) == points[0][1]
    assert pytest.approx(path[-1][0]) == points[-1][0]
    assert pytest.approx(path[-1][1]) == points[-1][1]


def test_generate_outline_path_with_smoothing_adds_intermediate_points() -> None:
    points = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)]
    path = generate_outline_path(points, smooth=True, closed=False, spline_steps=12)
    assert len(path) > len(points)
    mid_index = len(path) // 2
    mid_point = path[mid_index]
    assert mid_point[0] < 20.0
    assert mid_point[1] > 0.0


def test_rasterize_outline_creates_non_zero_alpha() -> None:
    points = [(0.0, 0.0), (50.0, 50.0)]
    path = generate_outline_path(points, smooth=True, closed=False, spline_steps=24)
    alpha_map = outline_renderer._rasterize_outline(
        path,
        canvas_size=(60, 60),
        stroke_width=3.0,
        supersample=4,
    )
    assert len(alpha_map) == 60
    assert len(alpha_map[0]) == 60
    assert any(alpha > 0 for row in alpha_map for alpha in row)


def test_alpha_to_rgb_map_blends_with_background() -> None:
    alpha_map = [[0, 64, 128, 255]]
    stroke = (200, 100, 0)
    background = (0, 0, 0)

    result = outline_renderer._alpha_to_rgb_map(alpha_map, stroke, background)

    assert result[0][0] is None
    assert result[0][3] == stroke
    assert result[0][1] == (
        int(round((stroke[0] * 64 + background[0] * 191) / 255)),
        int(round((stroke[1] * 64 + background[1] * 191) / 255)),
        int(round((stroke[2] * 64 + background[2] * 191) / 255)),
    )
    assert result[0][2] == (
        int(round((stroke[0] * 128 + background[0] * 127) / 255)),
        int(round((stroke[1] * 128 + background[1] * 127) / 255)),
        int(round((stroke[2] * 128 + background[2] * 127) / 255)),
    )
