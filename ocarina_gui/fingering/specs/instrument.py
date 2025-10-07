"""Instrument specification model and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ocarina_tools.pitch import midi_to_name as pitch_midi_to_name

from .models import HoleSpec, OutlineSpec, StyleSpec, WindwaySpec
from .pitch import parse_note_name_safe

__all__ = ["InstrumentSpec"]

_DEFAULT_HALF_HOLE_INSTRUMENT_IDS: frozenset[str] = frozenset({"alto_c_6"})


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
    windways: List[WindwaySpec]
    note_order: Sequence[str]
    note_map: Dict[str, List[int]]
    allow_half_holes: bool = False
    candidate_notes: Sequence[str] = ()
    candidate_range_min: str = ""
    candidate_range_max: str = ""
    preferred_range_min: str = ""
    preferred_range_max: str = ""
    _has_explicit_candidates: bool = field(default=False, repr=False)
    _has_explicit_candidate_range: bool = field(default=False, repr=False)
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
        windways = [WindwaySpec.from_dict(entry) for entry in data.get("windways", [])]
        note_order = tuple(str(note) for note in data.get("note_order", ()))
        note_map_raw: Dict[str, Iterable[int]] = data.get("note_map", {})
        hole_count = len(holes)
        windway_count = len(windways)
        total_elements = hole_count + windway_count
        note_map: Dict[str, List[int]] = {}
        for note, pattern in note_map_raw.items():
            sequence: List[int] = []
            for value in pattern:
                if isinstance(value, bool):
                    number = 2 if value else 0
                else:
                    number = int(value)
                position = len(sequence)
                if position < hole_count:
                    if number < 0:
                        number = 0
                    elif number > 2:
                        number = 2
                else:
                    number = 0 if number <= 0 else 2
                sequence.append(number)
            if total_elements:
                if len(sequence) < total_elements:
                    sequence.extend([0] * (total_elements - len(sequence)))
                elif len(sequence) > total_elements:
                    sequence = sequence[:total_elements]
            note_map[str(note)] = sequence

        has_explicit_candidates = "candidate_notes" in data
        candidate_source = [str(note) for note in data.get("candidate_notes", [])]
        combined_candidates = list(
            dict.fromkeys(candidate_source + list(note_order) + list(note_map.keys()))
        )

        candidate_range_data = data.get("candidate_range") or {}
        candidate_range_min = str(candidate_range_data.get("min", "")).strip()
        candidate_range_max = str(candidate_range_data.get("max", "")).strip()
        explicit_candidate_range = bool(candidate_range_min and candidate_range_max)
        if candidate_range_data and not explicit_candidate_range:
            raise ValueError("Candidate range must define both minimum and maximum notes")

        range_min_midi = parse_note_name_safe(candidate_range_min) if candidate_range_min else None
        range_max_midi = parse_note_name_safe(candidate_range_max) if candidate_range_max else None
        if candidate_range_data:
            if range_min_midi is None or range_max_midi is None:
                raise ValueError("Candidate range notes must be valid pitch names")
            if range_min_midi > range_max_midi:
                raise ValueError("Candidate range minimum must be lower than maximum")

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

        if range_min_midi is None or range_max_midi is None:
            if midi_pairs:
                range_min_midi = midi_pairs[0][0]
                range_max_midi = midi_pairs[-1][0]
                candidate_range_min = midi_pairs[0][1]
                candidate_range_max = midi_pairs[-1][1]
            elif combined_candidates:
                candidate_range_min = combined_candidates[0]
                candidate_range_max = combined_candidates[-1]
                range_min_midi = parse_note_name_safe(candidate_range_min)
                range_max_midi = parse_note_name_safe(candidate_range_max)
            else:
                candidate_range_min = ""
                candidate_range_max = ""

        if candidate_range_min and range_min_midi is not None:
            candidate_range_min = pitch_midi_to_name(range_min_midi, flats=False)
        if candidate_range_max and range_max_midi is not None:
            candidate_range_max = pitch_midi_to_name(range_max_midi, flats=False)

        if candidate_range_min and candidate_range_max:
            default_min = candidate_range_min
            default_max = candidate_range_max
        elif midi_pairs:
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

        allow_half_setting = data.get("allow_half_holes")
        allow_half_holes = (
            bool(allow_half_setting)
            if allow_half_setting is not None
            else instrument_id in _DEFAULT_HALF_HOLE_INSTRUMENT_IDS
        )

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
            windways=windways,
            note_order=note_order,
            note_map=note_map,
            allow_half_holes=allow_half_holes,
            candidate_notes=tuple(combined_candidates),
            candidate_range_min=candidate_range_min,
            candidate_range_max=candidate_range_max,
            _has_explicit_candidates=has_explicit_candidates,
            _has_explicit_candidate_range=explicit_candidate_range,
            preferred_range_min=preferred_min,
            preferred_range_max=preferred_max,
            _has_explicit_range=bool(preferred_range_data),
        )

    def pattern_for(self, note_name: str, fallback_name: str) -> List[int]:
        """Return the fingering pattern for ``note_name`` or ``fallback_name``."""

        pattern = self.note_map.get(note_name) or self.note_map.get(fallback_name)
        total = len(self.holes) + len(self.windways)
        if pattern is None:
            return [0] * total
        sequence = list(pattern)
        if len(sequence) < total:
            sequence.extend([0] * (total - len(sequence)))
        elif len(sequence) > total:
            sequence = sequence[:total]
        return sequence

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
        if self.windways:
            data["windways"] = [windway.to_dict() for windway in self.windways]
        if self._has_explicit_candidates:
            data["candidate_notes"] = list(self.candidate_notes)
        if (
            self._has_explicit_candidate_range
            and (self.candidate_range_min or self.candidate_range_max)
        ):
            data["candidate_range"] = {
                "min": self.candidate_range_min,
                "max": self.candidate_range_max,
            }
        if self._has_explicit_range and (self.preferred_range_min or self.preferred_range_max):
            data["preferred_range"] = {
                "min": self.preferred_range_min,
                "max": self.preferred_range_max,
            }
        if self.outline is not None:
            data["outline"] = self.outline.to_dict()
        if self.allow_half_holes != (
            self.instrument_id in _DEFAULT_HALF_HOLE_INSTRUMENT_IDS
        ):
            data["allow_half_holes"] = self.allow_half_holes
        return data
