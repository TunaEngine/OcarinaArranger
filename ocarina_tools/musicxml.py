"""Shared MusicXML helpers for reading, writing, and iterating over pitch data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterator, Optional
import xml.etree.ElementTree as ET

from .pitch import midi_to_pitch, pitch_to_midi


def qname(root: ET.Element, tag: str) -> str:
    match = re.match(r'\{(.+)\}', root.tag or '')
    xmlns = match.group(1) if match else None
    return f"{{{xmlns}}}{tag}" if xmlns else tag


@dataclass
class PitchData:
    """Cached view of a MusicXML <pitch> element with MIDI helpers."""

    element: ET.Element
    step: str
    alter: int
    octave: int

    @property
    def midi(self) -> int:
        return pitch_to_midi(self.step, self.alter, self.octave)

    def update_from_midi(self, midi: int, q, prefer_flats: bool) -> None:
        step, alter, octave = midi_to_pitch(midi, prefer_flats=prefer_flats)
        write_pitch(self.element, q, step, alter, octave)
        self.step = step
        self.alter = alter
        self.octave = octave


def write_pitch(pitch_el: ET.Element, q, step: str, alter: int, octave: int) -> None:
    step_el = pitch_el.find(q('step'))
    if step_el is None:
        step_el = ET.SubElement(pitch_el, q('step'))
    step_el.text = step

    alter_el = pitch_el.find(q('alter'))
    if alter != 0:
        if alter_el is None:
            alter_el = ET.SubElement(pitch_el, q('alter'))
        alter_el.text = str(alter)
    elif alter_el is not None:
        pitch_el.remove(alter_el)

    octave_el = pitch_el.find(q('octave'))
    if octave_el is None:
        octave_el = ET.SubElement(pitch_el, q('octave'))
    octave_el.text = str(octave)


def get_pitch_data(note: ET.Element, q) -> Optional[PitchData]:
    pitch_el = note.find(q('pitch'))
    if pitch_el is None:
        return None
    step_el = pitch_el.find(q('step'))
    octave_el = pitch_el.find(q('octave'))
    if step_el is None or octave_el is None or step_el.text is None or octave_el.text is None:
        return None
    alter_el = pitch_el.find(q('alter'))
    alter_text = (alter_el.text or '').strip() if alter_el is not None and alter_el.text else ''
    alter = int(alter_text) if alter_text else 0
    return PitchData(pitch_el, step_el.text.strip(), alter, int(octave_el.text.strip()))


def build_pitch_element(q, midi: int, prefer_flats: bool) -> ET.Element:
    pitch_el = ET.Element(q('pitch'))
    step, alter, octave = midi_to_pitch(midi, prefer_flats=prefer_flats)
    ET.SubElement(pitch_el, q('step')).text = step
    if alter != 0:
        ET.SubElement(pitch_el, q('alter')).text = str(alter)
    ET.SubElement(pitch_el, q('octave')).text = str(octave)
    return pitch_el


def constrain_midi(midi: int, midi_min: int, midi_max: int) -> int:
    if midi_min > midi_max:
        raise ValueError("midi_min must be less than or equal to midi_max")

    while midi < midi_min:
        midi += 12
    while midi > midi_max:
        midi -= 12
    return midi


def is_voice_one(note: ET.Element, q) -> bool:
    voice_el = note.find(q('voice'))
    if voice_el is None or not (voice_el.text or '').strip():
        return True
    return (voice_el.text or '').strip() == '1'


def first_divisions(root: ET.Element) -> int:
    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            attrs = measure.find(q('attributes'))
            if attrs is not None:
                div = attrs.find(q('divisions'))
                if div is not None and div.text and div.text.strip().isdigit():
                    return int(div.text.strip())
    return 1


def iter_pitched_notes_first_part(root: ET.Element) -> Iterator[Dict[str, int]]:
    q = lambda t: qname(root, t)
    parts = root.findall(q('part'))
    if not parts:
        return iter(())
    part = parts[0]

    def generator() -> Iterator[Dict[str, int]]:
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                dur_el = note.find(q('duration'))
                dur_text = (dur_el.text or '').strip() if dur_el is not None and dur_el.text else ''
                duration = int(dur_text) if dur_text.isdigit() else 0
                if note.find(q('rest')) is not None:
                    yield {"rest": True, "duration": duration}
                    continue
                pitch_data = get_pitch_data(note, q)
                if pitch_data is None:
                    continue
                yield {"rest": False, "midi": pitch_data.midi, "duration": duration}

    return generator()


__all__ = [
    'PitchData',
    'build_pitch_element',
    'constrain_midi',
    'first_divisions',
    'get_pitch_data',
    'is_voice_one',
    'iter_pitched_notes_first_part',
    'qname',
    'write_pitch',
]
