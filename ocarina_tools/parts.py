"""Helpers for inspecting and filtering MusicXML parts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Dict, List, Optional
import xml.etree.ElementTree as ET

from .instruments import part_programs
from .musicxml import get_pitch_data, qname
from .pitch import midi_to_name


@dataclass(slots=True)
class MusicXmlPartInfo:
    """Summary information about a MusicXML part."""

    part_id: str
    name: str
    midi_program: Optional[int]
    note_count: int
    min_midi: Optional[int]
    max_midi: Optional[int]
    min_pitch: Optional[str]
    max_pitch: Optional[str]


def _summarize_part_range(part: ET.Element, q) -> tuple[Dict[str, Optional[int]], Dict[str, Optional[str]]]:
    lowest = highest = None
    count = 0
    for measure in part.findall(q("measure")):
        for note in measure.findall(q("note")):
            if note.find(q("rest")) is not None:
                continue
            pitch_data = get_pitch_data(note, q)
            if pitch_data is None:
                continue
            midi = pitch_data.midi
            lowest = midi if lowest is None else min(lowest, midi)
            highest = midi if highest is None else max(highest, midi)
            count += 1
    range_midi = {"min": lowest, "max": highest, "count": count}
    range_names = {
        "min": midi_to_name(lowest) if lowest is not None else None,
        "max": midi_to_name(highest) if highest is not None else None,
    }
    return range_midi, range_names


def list_parts(root: ET.Element) -> List[MusicXmlPartInfo]:
    """Return summary information for all parts in a MusicXML score."""

    q = lambda tag: qname(root, tag)
    programs = part_programs(root)
    part_list = root.find(q("part-list"))

    part_names: Dict[str, str] = {}
    ordered_ids: List[str] = []
    if part_list is not None:
        for score_part in part_list.findall(q("score-part")):
            part_id = (score_part.get("id") or "").strip()
            if not part_id:
                continue
            ordered_ids.append(part_id)
            part_name_el = score_part.find(q("part-name"))
            name = (part_name_el.text or "").strip() if part_name_el is not None else ""
            part_names[part_id] = name

    parts_by_id: Dict[str, ET.Element] = {}
    for part in root.findall(q("part")):
        part_id = (part.get("id") or "").strip()
        if part_id:
            parts_by_id[part_id] = part

    infos: List[MusicXmlPartInfo] = []
    seen: set[str] = set()

    def _append_part(part_id: str, part_el: ET.Element) -> None:
        range_midi, range_names = _summarize_part_range(part_el, q)
        infos.append(
            MusicXmlPartInfo(
                part_id=part_id,
                name=part_names.get(part_id, ""),
                midi_program=programs.get(part_id),
                note_count=range_midi["count"] or 0,
                min_midi=range_midi["min"],
                max_midi=range_midi["max"],
                min_pitch=range_names["min"],
                max_pitch=range_names["max"],
            )
        )
        seen.add(part_id)

    for part_id in ordered_ids:
        part_el = parts_by_id.get(part_id)
        if part_el is None:
            continue
        _append_part(part_id, part_el)

    for part_id, part_el in parts_by_id.items():
        if part_id in seen:
            continue
        _append_part(part_id, part_el)

    return infos


def filter_parts(root: ET.Element, keep_ids: Collection[str]) -> None:
    """Keep only the parts listed in ``keep_ids`` and normalize ordering."""

    q = lambda tag: qname(root, tag)
    keep_order = []
    keep_set = set()
    for part_id in keep_ids:
        normalized = (part_id or "").strip()
        if not normalized or normalized in keep_set:
            continue
        keep_set.add(normalized)
        keep_order.append(normalized)

    part_elements: Dict[str, ET.Element] = {}
    for part in root.findall(q("part")):
        part_id = (part.get("id") or "").strip()
        if not part_id:
            continue
        part_elements[part_id] = part
        if part_id not in keep_set:
            root.remove(part)

    score_part_elements: Dict[str, ET.Element] = {}
    part_list = root.find(q("part-list"))
    if part_list is not None:
        for score_part in part_list.findall(q("score-part")):
            part_id = (score_part.get("id") or "").strip()
            if not part_id:
                part_list.remove(score_part)
                continue
            score_part_elements[part_id] = score_part
            if part_id not in keep_set:
                part_list.remove(score_part)

    ordered_ids = [part_id for part_id in keep_order if part_id in part_elements]

    if part_list is not None:
        for score_part in list(part_list.findall(q("score-part"))):
            part_list.remove(score_part)
        for part_id in ordered_ids:
            element = score_part_elements.get(part_id)
            if element is not None:
                part_list.append(element)

    kept_parts = [part_elements[part_id] for part_id in ordered_ids if part_id in part_elements]
    for part in list(root.findall(q("part"))):
        root.remove(part)
    for part in kept_parts:
        root.append(part)


__all__ = ["MusicXmlPartInfo", "list_parts", "filter_parts"]

