"""Data structures for the instrument layout editor view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ocarina_gui.fingering import InstrumentSpec, StyleSpec


@dataclass
class EditableHole:
    identifier: str
    x: float
    y: float
    radius: float


@dataclass
class OutlinePoint:
    x: float
    y: float


@dataclass
class EditableStyle:
    background_color: str
    outline_color: str
    outline_width: float
    outline_smooth: bool
    hole_outline_color: str
    covered_fill_color: str

    @classmethod
    def from_spec(cls, spec: StyleSpec) -> "EditableStyle":
        return cls(
            background_color=spec.background_color,
            outline_color=spec.outline_color,
            outline_width=spec.outline_width,
            outline_smooth=spec.outline_smooth,
            hole_outline_color=spec.hole_outline_color,
            covered_fill_color=spec.covered_fill_color,
        )

    def to_spec(self) -> StyleSpec:
        return StyleSpec(
            background_color=self.background_color,
            outline_color=self.outline_color,
            outline_width=self.outline_width,
            outline_smooth=self.outline_smooth,
            hole_outline_color=self.hole_outline_color,
            covered_fill_color=self.covered_fill_color,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "background_color": self.background_color,
            "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "outline_smooth": self.outline_smooth,
            "hole_outline_color": self.hole_outline_color,
            "covered_fill_color": self.covered_fill_color,
        }


class SelectionKind(str, Enum):
    NONE = "none"
    HOLE = "hole"
    OUTLINE = "outline"


@dataclass
class Selection:
    kind: SelectionKind
    index: int


@dataclass
class InstrumentLayoutState:
    instrument_id: str
    name: str
    title: str
    canvas_width: int
    canvas_height: int
    holes: List[EditableHole] = field(default_factory=list)
    outline_points: List[OutlinePoint] = field(default_factory=list)
    outline_closed: bool = False
    style: EditableStyle = field(default_factory=lambda: EditableStyle.from_spec(StyleSpec()))
    note_order: List[str] = field(default_factory=list)
    note_map: Dict[str, List[int]] = field(default_factory=dict)
    candidate_notes: List[str] = field(default_factory=list)
    preferred_range_min: str = ""
    preferred_range_max: str = ""
    dirty: bool = False
    selection: Optional[Selection] = None


def state_from_spec(instrument: InstrumentSpec) -> InstrumentLayoutState:
    """Build a layout editor state from a fingering instrument spec."""

    holes = [
        EditableHole(identifier=hole.identifier, x=hole.x, y=hole.y, radius=hole.radius)
        for hole in instrument.holes
    ]
    if instrument.outline is not None:
        outline_points = [OutlinePoint(x=point[0], y=point[1]) for point in instrument.outline.points]
        outline_closed = instrument.outline.closed
    else:
        outline_points = []
        outline_closed = False

    note_map = {note: list(pattern) for note, pattern in instrument.note_map.items()}
    candidate_sources = list(getattr(instrument, "candidate_notes", ()))
    candidate_notes = list(
        dict.fromkeys(
            candidate_sources
            + list(instrument.note_order)
            + list(instrument.note_map.keys())
        )
    )

    return InstrumentLayoutState(
        instrument_id=instrument.instrument_id,
        name=instrument.name,
        title=instrument.title,
        canvas_width=int(instrument.canvas_size[0]),
        canvas_height=int(instrument.canvas_size[1]),
        holes=holes,
        outline_points=outline_points,
        outline_closed=outline_closed,
        style=EditableStyle.from_spec(instrument.style),
        note_order=list(instrument.note_order),
        note_map=note_map,
        candidate_notes=candidate_notes,
        preferred_range_min=str(getattr(instrument, "preferred_range_min", "")),
        preferred_range_max=str(getattr(instrument, "preferred_range_max", "")),
    )


def clone_state(
    instrument_id: str,
    name: str,
    *,
    template: Optional[InstrumentLayoutState] = None,
    title: Optional[str] = None,
) -> InstrumentLayoutState:
    """Create a new state, optionally copying from a template state."""

    if template is None:
        canvas_width = 240
        canvas_height = 160
        holes: List[EditableHole] = []
        outline_points: List[OutlinePoint] = []
        outline_closed = False
        style = EditableStyle.from_spec(StyleSpec())
        note_order: List[str] = []
        note_map: Dict[str, List[int]] = {}
        candidate_notes: List[str] = []
        preferred_range_min = ""
        preferred_range_max = ""
    else:
        canvas_width = template.canvas_width
        canvas_height = template.canvas_height
        holes = [
            EditableHole(
                identifier=hole.identifier,
                x=hole.x,
                y=hole.y,
                radius=hole.radius,
            )
            for hole in template.holes
        ]
        outline_points = [OutlinePoint(x=point.x, y=point.y) for point in template.outline_points]
        outline_closed = template.outline_closed
        style = EditableStyle(
            background_color=template.style.background_color,
            outline_color=template.style.outline_color,
            outline_width=template.style.outline_width,
            outline_smooth=template.style.outline_smooth,
            hole_outline_color=template.style.hole_outline_color,
            covered_fill_color=template.style.covered_fill_color,
        )
        note_order = list(template.note_order)
        note_map = {note: list(pattern) for note, pattern in template.note_map.items()}
        candidate_notes = list(template.candidate_notes)
        preferred_range_min = template.preferred_range_min
        preferred_range_max = template.preferred_range_max

    return InstrumentLayoutState(
        instrument_id=instrument_id,
        name=name,
        title=str(title).strip() if title else name,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        holes=holes,
        outline_points=outline_points,
        outline_closed=outline_closed,
        style=style,
        note_order=note_order,
        note_map=note_map,
        candidate_notes=candidate_notes,
        preferred_range_min=preferred_range_min,
        preferred_range_max=preferred_range_max,
        dirty=True,
        selection=None,
    )


def state_to_dict(state: InstrumentLayoutState) -> Dict[str, object]:
    """Serialize a layout editor state into a config dictionary."""

    data: Dict[str, object] = {
        "id": state.instrument_id,
        "name": state.name,
        "title": state.title,
        "canvas": {"width": state.canvas_width, "height": state.canvas_height},
        "style": state.style.to_dict(),
        "holes": [
            {
                "id": hole.identifier,
                "x": hole.x,
                "y": hole.y,
                "radius": hole.radius,
            }
            for hole in state.holes
        ],
        "note_order": list(state.note_order),
        "note_map": {note: list(pattern) for note, pattern in state.note_map.items()},
        "candidate_notes": list(state.candidate_notes),
    }
    if state.preferred_range_min or state.preferred_range_max:
        data["preferred_range"] = {
            "min": state.preferred_range_min,
            "max": state.preferred_range_max,
        }
    if state.outline_points:
        data["outline"] = {
            "points": [[point.x, point.y] for point in state.outline_points],
            "closed": state.outline_closed,
        }
    return data


__all__ = [
    "EditableHole",
    "EditableStyle",
    "InstrumentLayoutState",
    "OutlinePoint",
    "Selection",
    "SelectionKind",
    "clone_state",
    "state_from_spec",
    "state_to_dict",
]
