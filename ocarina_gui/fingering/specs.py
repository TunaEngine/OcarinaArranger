"""Specifications and note helpers for ocarina fingering instruments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ocarina_tools.pitch import parse_note_name


__all__ = [
    "HoleSpec",
    "OutlineSpec",
    "StyleSpec",
    "InstrumentSpec",
    "InstrumentChoice",
    "collect_instrument_note_names",
    "preferred_note_window",
    "parse_note_name_safe",
]


@dataclass(frozen=True)
class HoleSpec:
    """Specification for a fingering hole."""

    identifier: str
    x: float
    y: float
    radius: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HoleSpec":
        return cls(
            identifier=str(data.get("id", "")),
            x=float(data["x"]),
            y=float(data["y"]),
            radius=float(data.get("radius", 8.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.identifier,
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
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
    outline_smooth: bool = False
    hole_outline_color: str = "#000000"
    covered_fill_color: str = "#000000"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "StyleSpec":
        data = data or {}
        return cls(
            background_color=str(data.get("background_color", "#ffffff")),
            outline_color=str(data.get("outline_color", "#000000")),
            outline_width=float(data.get("outline_width", 2.0)),
            outline_smooth=bool(data.get("outline_smooth", False)),
            hole_outline_color=str(data.get("hole_outline_color", "#000000")),
            covered_fill_color=str(data.get("covered_fill_color", "#000000")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "background_color": self.background_color,
            "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "outline_smooth": self.outline_smooth,
            "hole_outline_color": self.hole_outline_color,
            "covered_fill_color": self.covered_fill_color,
        }


@dataclass(frozen=True)
class InstrumentSpec:
    """Configuration for an ocarina fingering instrument."""

    instrument_id: str
    name: str
    title: str
    canvas_size: Tuple[int, int]
    style: StyleSpec
    outline: Optional[OutlineSpec]
    holes: List[HoleSpec]
    note_order: Sequence[str]
    note_map: Dict[str, List[int]]
    candidate_notes: Sequence[str] = ()
    preferred_range_min: str = ""
    preferred_range_max: str = ""
    _has_explicit_candidates: bool = field(default=False, repr=False)
    _has_explicit_range: bool = field(default=False, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstrumentSpec":
        instrument_id = str(data["id"])
        name = str(data.get("name", instrument_id))
        title = str(data.get("title", name))
        canvas_data = data.get("canvas", {})
        width = int(canvas_data.get("width", 72))
        height = int(canvas_data.get("height", 240))
        style = StyleSpec.from_dict(data.get("style"))
        outline = OutlineSpec.from_dict(data.get("outline"))
        holes = [HoleSpec.from_dict(entry) for entry in data.get("holes", [])]
        note_order = tuple(str(note) for note in data.get("note_order", ()))
        note_map_raw: Dict[str, Iterable[int]] = data.get("note_map", {})
        hole_count = len(holes)
        note_map: Dict[str, List[int]] = {}
        for note, pattern in note_map_raw.items():
            sequence = []
            for value in pattern:
                if isinstance(value, bool):
                    number = 2 if value else 0
                else:
                    number = int(value)
                if number < 0:
                    number = 0
                elif number > 2:
                    number = 2
                sequence.append(number)
            if hole_count:
                if len(sequence) < hole_count:
                    sequence.extend([0] * (hole_count - len(sequence)))
                elif len(sequence) > hole_count:
                    sequence = sequence[:hole_count]
            note_map[str(note)] = sequence

        has_explicit_candidates = "candidate_notes" in data
        candidate_source = [str(note) for note in data.get("candidate_notes", [])]
        combined_candidates = list(
            dict.fromkeys(candidate_source + list(note_order) + list(note_map.keys()))
        )

        preferred_range_data = data.get("preferred_range") or {}
        preferred_min = str(preferred_range_data.get("min", "")).strip()
        preferred_max = str(preferred_range_data.get("max", "")).strip()

        midi_pairs: List[Tuple[int, str]] = []
        for candidate in combined_candidates:
            midi = parse_note_name_safe(candidate)
            if midi is None:
                continue
            midi_pairs.append((midi, candidate))
        midi_pairs.sort(key=lambda pair: (pair[0], pair[1]))

        if midi_pairs:
            default_min = midi_pairs[0][1]
            default_max = midi_pairs[-1][1]
        elif combined_candidates:
            default_min = combined_candidates[0]
            default_max = combined_candidates[-1]
        else:
            default_min = ""
            default_max = ""

        if not preferred_min:
            preferred_min = default_min
        if not preferred_max:
            preferred_max = default_max

        min_midi = parse_note_name_safe(preferred_min)
        max_midi = parse_note_name_safe(preferred_max)
        if (
            min_midi is not None
            and max_midi is not None
            and default_min
            and default_max
            and min_midi > max_midi
        ):
            preferred_min = default_min
            preferred_max = default_max

        return cls(
            instrument_id=instrument_id,
            name=name,
            title=title,
            canvas_size=(width, height),
            style=style,
            outline=outline,
            holes=holes,
            note_order=note_order,
            note_map=note_map,
            candidate_notes=tuple(combined_candidates),
            _has_explicit_candidates=has_explicit_candidates,
            preferred_range_min=preferred_min,
            preferred_range_max=preferred_max,
            _has_explicit_range=bool(preferred_range_data),
        )

    def pattern_for(self, note_name: str, fallback_name: str) -> List[int]:
        """Return the fingering pattern for ``note_name`` or ``fallback_name``."""

        pattern = self.note_map.get(note_name) or self.note_map.get(fallback_name)
        if pattern is None:
            return [0] * len(self.holes)
        return list(pattern)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.instrument_id,
            "name": self.name,
            "title": self.title,
            "canvas": {
                "width": int(self.canvas_size[0]),
                "height": int(self.canvas_size[1]),
            },
            "style": self.style.to_dict(),
            "holes": [hole.to_dict() for hole in self.holes],
            "note_order": list(self.note_order),
            "note_map": {note: list(pattern) for note, pattern in self.note_map.items()},
        }
        if self._has_explicit_candidates:
            data["candidate_notes"] = list(self.candidate_notes)
        if self._has_explicit_range and (self.preferred_range_min or self.preferred_range_max):
            data["preferred_range"] = {
                "min": self.preferred_range_min,
                "max": self.preferred_range_max,
            }
        if self.outline is not None:
            data["outline"] = self.outline.to_dict()
        return data


@dataclass(frozen=True)
class InstrumentChoice:
    """Simple value/name pair for UI selections."""

    instrument_id: str
    name: str


def collect_instrument_note_names(instrument: InstrumentSpec) -> List[str]:
    """Return the instrument's configured note names in pitch order."""

    combined = list(
        dict.fromkeys(
            list(getattr(instrument, "candidate_notes", ()))
            + list(instrument.note_order)
            + list(instrument.note_map.keys())
        )
    )

    def _sort_key(note_name: str) -> tuple[float, str]:
        try:
            midi = float(parse_note_name(note_name))
        except Exception:
            return (float("inf"), note_name)
        return (midi, note_name)

    combined.sort(key=_sort_key)
    return combined


def preferred_note_window(instrument: InstrumentSpec) -> Tuple[str, str]:
    """Return a preferred note window for ``instrument``."""

    explicit_min = getattr(instrument, "preferred_range_min", "").strip()
    explicit_max = getattr(instrument, "preferred_range_max", "").strip()
    if explicit_min and explicit_max:
        return explicit_min, explicit_max

    ordered = collect_instrument_note_names(instrument)
    if not ordered:
        raise ValueError("Instrument must define at least one note.")

    midi_pairs: List[Tuple[int, str]] = []
    for name in ordered:
        midi = parse_note_name_safe(name)
        if midi is None:
            continue
        midi_pairs.append((midi, name))

    if not midi_pairs:
        return ordered[0], ordered[-1]

    midi_pairs.sort(key=lambda item: item[0])
    lowest_name = midi_pairs[0][1]
    highest_name = midi_pairs[-1][1]
    return lowest_name, highest_name


def parse_note_name_safe(note_name: str) -> Optional[int]:
    """Best-effort conversion of ``note_name`` to a MIDI integer."""

    try:
        return int(parse_note_name(note_name))
    except Exception:
        return None
