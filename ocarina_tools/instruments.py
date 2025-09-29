"""Instrument helpers shared across MusicXML and preview rendering."""

from __future__ import annotations

from typing import Dict
import xml.etree.ElementTree as ET

from .musicxml import qname


OCARINA_GM_PROGRAM = 79


def parse_midi_program(value: str | None) -> int | None:
    """Convert a MusicXML ``midi-program`` value to a zero-based GM number."""

    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        program = int(float(text))
    except (TypeError, ValueError):
        return None
    if program <= 0:
        return 0
    return max(0, min(127, program - 1))


def part_programs(root: ET.Element) -> Dict[str, int]:
    """Return a mapping of MusicXML part IDs to their MIDI program numbers."""

    q = lambda tag: qname(root, tag)
    part_list = root.find(q("part-list"))
    if part_list is None:
        return {}

    programs: Dict[str, int] = {}
    for score_part in part_list.findall(q("score-part")):
        part_id = (score_part.get("id") or "").strip()
        if not part_id:
            continue
        for midi_inst in score_part.findall(q("midi-instrument")):
            program_el = midi_inst.find(q("midi-program"))
            parsed = parse_midi_program(program_el.text if program_el is not None else None)
            if parsed is None:
                continue
            programs[part_id] = parsed
            break
    return programs


__all__ = ["OCARINA_GM_PROGRAM", "parse_midi_program", "part_programs"]

