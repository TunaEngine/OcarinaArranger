"""Helpers for generating anti-aliased instrument outlines."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import tkinter as tk

Point = Tuple[float, float]

_RGB_CACHE: Dict[Tuple[int | None, str], Tuple[int, int, int]] = {}


def _points_signature(points: Sequence[Point]) -> Tuple[Point, ...]:
    """Return a hashable representation of the provided points."""

    return tuple((round(float(x), 5), round(float(y), 5)) for x, y in points)


def _quantize_float(value: float, *, digits: int = 5) -> float:
    return round(float(value), digits)


def _resolve_rgb(color: str, master: Optional[tk.Misc]) -> Tuple[int, int, int]:
    normalized = color.strip()
    cache_key = (id(master) if master is not None else None, normalized)
    cached = _RGB_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if master is not None:
        try:
            r16, g16, b16 = master.winfo_rgb(normalized)
            result = (r16 // 256, g16 // 256, b16 // 256)
            _RGB_CACHE[cache_key] = result
            return result
        except tk.TclError:
            pass

    if normalized.startswith("#"):
        hex_value = normalized[1:]
        if len(hex_value) == 3:
            r = int(hex_value[0] * 2, 16)
            g = int(hex_value[1] * 2, 16)
            b = int(hex_value[2] * 2, 16)
            result = (r, g, b)
            _RGB_CACHE[cache_key] = result
            return result
        if len(hex_value) == 6:
            r = int(hex_value[0:2], 16)
            g = int(hex_value[2:4], 16)
            b = int(hex_value[4:6], 16)
            result = (r, g, b)
            _RGB_CACHE[cache_key] = result
            return result
        if len(hex_value) == 8:
            r = int(hex_value[0:2], 16)
            g = int(hex_value[2:4], 16)
            b = int(hex_value[4:6], 16)
            result = (r, g, b)
            _RGB_CACHE[cache_key] = result
            return result
    raise ValueError(f"Unsupported color format: {color}")


def generate_outline_path(
    points: Sequence[Point],
    *,
    smooth: bool,
    closed: bool,
    spline_steps: int,
) -> List[Point]:
    signature = _points_signature(points)
    path = _generate_outline_path_cached(
        signature,
        bool(smooth),
        bool(closed),
        max(1, int(spline_steps)),
    )
    return [tuple(point) for point in path]


@lru_cache(maxsize=256)
def _generate_outline_path_cached(
    signature: Tuple[Point, ...],
    smooth: bool,
    closed: bool,
    steps: int,
) -> Tuple[Point, ...]:
    base_points: List[Point] = [(float(x), float(y)) for x, y in signature]
    if len(base_points) < 2:
        return tuple(base_points)
    if not smooth or len(base_points) < 3:
        if closed and base_points[0] != base_points[-1]:
            return tuple(base_points + [base_points[0]])
        return tuple(base_points)

    extended: List[Point]
    if closed:
        extended = (
            [base_points[-2], base_points[-1]]
            + base_points
            + [base_points[0], base_points[1]]
        )
    else:
        extended = [base_points[0]] * 2 + base_points + [base_points[-1]] * 2

    result: List[Point] = []

    def interpolate(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
        t2 = t * t
        t3 = t2 * t
        b0 = (-t3 + 3 * t2 - 3 * t + 1) / 6.0
        b1 = (3 * t3 - 6 * t2 + 4) / 6.0
        b2 = (-3 * t3 + 3 * t2 + 3 * t + 1) / 6.0
        b3 = t3 / 6.0
        x = b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0]
        y = b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]
        return (x, y)

    segment_count = len(extended) - 3
    for index in range(segment_count):
        p0, p1, p2, p3 = extended[index : index + 4]
        for step in range(steps):
            t = step / float(steps)
            result.append(interpolate(p0, p1, p2, p3, t))
    result.append(extended[-2])
    if closed:
        result.append(result[0])
    return tuple(result)


def _rasterize_outline(
    path: Sequence[Point],
    *,
    canvas_size: Tuple[int, int],
    stroke_width: float,
    supersample: int,
) -> List[List[int]]:
    width, height = canvas_size
    scale = max(1, int(supersample))
    hi_width = max(1, width * scale)
    hi_height = max(1, height * scale)
    coverage = [0] * (hi_width * hi_height)

    radius = max(0.5, float(stroke_width) / 2.0) * scale
    radius_sq = radius * radius

    for index in range(len(path) - 1):
        x0, y0 = path[index]
        x1, y1 = path[index + 1]
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        samples = max(1, int(math.ceil(length * scale * 2)))
        for step in range(samples + 1):
            t = step / float(samples)
            cx = (x0 + dx * t) * scale
            cy = (y0 + dy * t) * scale
            min_x = max(0, int(math.floor(cx - radius - 1)))
            max_x = min(hi_width - 1, int(math.ceil(cx + radius + 1)))
            min_y = max(0, int(math.floor(cy - radius - 1)))
            max_y = min(hi_height - 1, int(math.ceil(cy + radius + 1)))
            for py in range(min_y, max_y + 1):
                row = py * hi_width
                for px in range(min_x, max_x + 1):
                    dxp = (px + 0.5) - cx
                    dyp = (py + 0.5) - cy
                    if dxp * dxp + dyp * dyp <= radius_sq:
                        coverage[row + px] = 1

    alpha_map: List[List[int]] = []
    block_area = scale * scale
    for y in range(height):
        row: List[int] = []
        base_y = y * scale
        for x in range(width):
            base_x = x * scale
            total = 0
            for sy in range(scale):
                row_index = (base_y + sy) * hi_width
                for sx in range(scale):
                    total += coverage[row_index + base_x + sx]
            alpha = int(round(255 * total / block_area))
            row.append(alpha)
        alpha_map.append(row)
    return alpha_map


@lru_cache(maxsize=128)
def _compute_alpha_map(
    path: Tuple[Point, ...],
    canvas_size: Tuple[int, int],
    stroke_width: float,
    supersample: int,
) -> Tuple[Tuple[int, ...], ...]:
    alpha_rows = _rasterize_outline(
        path,
        canvas_size=canvas_size,
        stroke_width=stroke_width,
        supersample=supersample,
    )
    return tuple(tuple(row) for row in alpha_rows)


def _alpha_to_rgb_map(
    alpha_map: Sequence[Sequence[int]],
    stroke_rgb: Tuple[int, int, int],
    background_rgb: Tuple[int, int, int],
) -> List[List[Optional[Tuple[int, int, int]]]]:
    sr, sg, sb = stroke_rgb
    br, bg, bb = background_rgb

    def blend_channel(fg: int, bg_val: int, alpha: int) -> int:
        return int(round((fg * alpha + bg_val * (255 - alpha)) / 255.0))

    rows: List[List[Optional[Tuple[int, int, int]]]] = []
    for row in alpha_map:
        colors: List[Optional[Tuple[int, int, int]]] = []
        for alpha in row:
            if alpha <= 0:
                colors.append(None)
            elif alpha >= 255:
                colors.append((sr, sg, sb))
            else:
                colors.append(
                    (
                        blend_channel(sr, br, alpha),
                        blend_channel(sg, bg, alpha),
                        blend_channel(sb, bb, alpha),
                    )
                )
        rows.append(colors)
    return rows


@dataclass(frozen=True)
class OutlineImage:
    photo_image: tk.PhotoImage
    width: int
    height: int


def render_outline_photoimage(
    master: tk.Misc,
    points: Sequence[Point],
    *,
    canvas_size: Tuple[int, int],
    stroke_width: float,
    stroke_color: str,
    background_color: str | None = None,
    smooth: bool,
    closed: bool,
    spline_steps: int,
    supersample: int = 4,
) -> OutlineImage | None:
    path = generate_outline_path(
        points,
        smooth=smooth,
        closed=closed,
        spline_steps=spline_steps,
    )
    if len(path) < 2:
        return None
    alpha_map = _compute_alpha_map(
        tuple(path),
        canvas_size,
        _quantize_float(stroke_width),
        max(1, int(supersample)),
    )
    width, height = canvas_size
    photo = tk.PhotoImage(master=master, width=width, height=height)
    stroke_rgb = _resolve_rgb(stroke_color, master)
    if background_color:
        background_rgb = _resolve_rgb(background_color, master)
    else:
        try:
            default_bg = master.cget("background")  # type: ignore[no-untyped-call]
        except Exception:
            default_bg = "#ffffff"
        background_rgb = _resolve_rgb(default_bg, master)

    rgb_map = _alpha_to_rgb_map(alpha_map, stroke_rgb, background_rgb)

    for y, row in enumerate(rgb_map):
        current_color: Optional[Tuple[int, int, int]] = None
        run_start = 0
        for x, color in enumerate(row):
            if color != current_color:
                if current_color is not None:
                    photo.put(
                        f"#{current_color[0]:02x}{current_color[1]:02x}{current_color[2]:02x}",
                        to=(run_start, y, x, y + 1),
                    )
                current_color = color
                run_start = x
        if current_color is not None:
            photo.put(
                f"#{current_color[0]:02x}{current_color[1]:02x}{current_color[2]:02x}",
                to=(run_start, y, width, y + 1),
            )
    return OutlineImage(photo_image=photo, width=width, height=height)


__all__ = [
    "generate_outline_path",
    "render_outline_photoimage",
    "OutlineImage",
]
