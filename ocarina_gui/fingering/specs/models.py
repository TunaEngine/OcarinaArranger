"""Data structures for ocarina fingering specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "HoleSpec",
    "WindwaySpec",
    "OutlineSpec",
    "StyleSpec",
    "InstrumentChoice",
]


@dataclass(frozen=True)
class HoleSpec:
    """Specification for a fingering hole."""

    identifier: str
    x: float
    y: float
    radius: float
    is_subhole: bool = False
    _has_explicit_subhole: bool = field(default=False, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HoleSpec":
        has_explicit_flag = False
        is_subhole = data.get("is_subhole")
        if is_subhole is None and "subhole" in data:
            is_subhole = data["subhole"]
        if is_subhole is not None:
            has_explicit_flag = True
        else:
            is_subhole = False

        return cls(
            identifier=str(data.get("id", "")),
            x=float(data["x"]),
            y=float(data["y"]),
            radius=float(data.get("radius", 8.0)),
            is_subhole=bool(is_subhole),
            _has_explicit_subhole=has_explicit_flag,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.identifier,
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
        }
        if self.is_subhole or getattr(self, "_has_explicit_subhole", False):
            data["is_subhole"] = self.is_subhole
        return data


@dataclass(frozen=True)
class WindwaySpec:
    """Specification for an instrument windway."""

    identifier: str
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WindwaySpec":
        return cls(
            identifier=str(data.get("id", "")),
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data.get("width", 14.0)),
            height=float(data.get("height", 10.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.identifier,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class OutlineSpec:
    """Outline configuration for the ocarina body."""

    points: List[Tuple[float, float]]
    closed: bool

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["OutlineSpec"]:
        if not data:
            return None
        points = [tuple(map(float, point)) for point in data.get("points", [])]
        if not points:
            return None
        closed = bool(data.get("closed", False))
        return cls(points=points, closed=closed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "points": [[x, y] for x, y in self.points],
            "closed": self.closed,
        }


@dataclass(frozen=True)
class StyleSpec:
    """Visual style settings for a fingering view."""

    background_color: str = "#ffffff"
    outline_color: str = "#000000"
    outline_width: float = 2.0
    outline_smooth: bool = True
    outline_spline_steps: int = 48
    hole_outline_color: str = "#000000"
    covered_fill_color: str = "#000000"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "StyleSpec":
        data = data or {}
        return cls(
            background_color=str(data.get("background_color", "#ffffff")),
            outline_color=str(data.get("outline_color", "#000000")),
            outline_width=float(data.get("outline_width", 2.0)),
            outline_smooth=bool(data.get("outline_smooth", True)),
            outline_spline_steps=max(1, int(data.get("outline_spline_steps", 48))),
            hole_outline_color=str(data.get("hole_outline_color", "#000000")),
            covered_fill_color=str(data.get("covered_fill_color", "#000000")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "background_color": self.background_color,
            "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "outline_smooth": self.outline_smooth,
            "outline_spline_steps": int(self.outline_spline_steps),
            "hole_outline_color": self.hole_outline_color,
            "covered_fill_color": self.covered_fill_color,
        }


@dataclass(frozen=True)
class InstrumentChoice:
    """Simple value/name pair for UI selections."""

    instrument_id: str
    name: str
