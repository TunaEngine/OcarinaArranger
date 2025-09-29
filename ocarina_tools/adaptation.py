"""Helpers for collapsing parts and constraining scores to the Alto C ocarina range."""

from __future__ import annotations

import copy
import math
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from .key_analysis import analyze_key, compute_transpose_semitones
from .musicxml import (
    PitchData,
    build_pitch_element,
    constrain_midi,
    get_pitch_data,
    is_voice_one,
    qname,
)
from .pitch import midi_to_name, parse_note_name


class _MeasureAdapter:
    """Apply transposition and range constraints to a single MusicXML measure."""

    def __init__(
        self,
        q,
        transpose_semitones: int,
        midi_min: int,
        midi_max: int,
        prefer_flats: bool,
        collapse_chords: bool,
    ) -> None:
        self.q = q
        self.transpose_semitones = transpose_semitones
        self.midi_min = midi_min
        self.midi_max = midi_max
        self.prefer_flats = prefer_flats
        self.collapse_chords = collapse_chords

    def adapt_measure(self, measure: ET.Element) -> None:
        notes = list(measure.findall(self.q('note')))
        if not notes:
            return
        new_children: List[ET.Element] = []
        chord_buffer: List[ET.Element] = []

        for note in notes:
            if not is_voice_one(note, self.q):
                continue
            if self.collapse_chords:
                if note.find(self.q('chord')) is None:
                    self._flush_buffer(chord_buffer, new_children)
                    chord_buffer.append(note)
                else:
                    chord_buffer.append(note)
            else:
                new_children.append(self._transpose_note_in_place(note))

        self._flush_buffer(chord_buffer, new_children)

        for note in notes:
            measure.remove(note)
        for note in new_children:
            measure.append(note)

    def _flush_buffer(self, buffer: List[ET.Element], new_children: List[ET.Element]) -> None:
        if not buffer:
            return
        pitched: List[Tuple[int, ET.Element]] = []
        for note in buffer:
            if note.find(self.q('rest')) is not None:
                continue
            pitch_data = get_pitch_data(note, self.q)
            if pitch_data is None:
                continue
            midi = constrain_midi(
                pitch_data.midi + self.transpose_semitones,
                self.midi_min,
                self.midi_max,
            )
            pitched.append((midi, note))

        if pitched:
            midi, source = max(pitched, key=lambda item: item[0])
            chosen = copy.deepcopy(source)
            chord_flag = chosen.find(self.q('chord'))
            if chord_flag is not None:
                chosen.remove(chord_flag)
            pitch_data = get_pitch_data(chosen, self.q)
            if pitch_data is not None:
                pitch_data.update_from_midi(midi, self.q, self.prefer_flats)
            else:
                chosen.append(build_pitch_element(self.q, midi, self.prefer_flats))
            new_children.append(chosen)
        else:
            new_children.append(copy.deepcopy(buffer[0]))
        buffer.clear()

    def _transpose_note_in_place(self, note: ET.Element) -> ET.Element:
        if note.find(self.q('rest')) is None:
            pitch_data = get_pitch_data(note, self.q)
            if pitch_data is not None:
                midi = constrain_midi(
                    pitch_data.midi + self.transpose_semitones,
                    self.midi_min,
                    self.midi_max,
                )
                pitch_data.update_from_midi(midi, self.q, self.prefer_flats)
        return note


def _should_use_minor_mode(prefer_mode: str, key_info: Dict) -> bool:
    if prefer_mode == 'minor':
        return True
    if prefer_mode == 'auto':
        mode = (key_info.get('mode') or '').lower()
        return mode.startswith('min')
    return False


def _select_primary_part(root: ET.Element, q) -> ET.Element:
    parts = root.findall(q('part'))
    if not parts:
        raise ValueError("No <part> in score.")
    melodic_part = parts[0]
    for extra in parts[1:]:
        root.remove(extra)
    return melodic_part


def _ensure_primary_attributes(part: ET.Element, q, prefer_mode: str, key_info: Dict) -> None:
    first_measure = part.find(q('measure'))
    if first_measure is None:
        return
    attrs = first_measure.find(q('attributes'))
    if attrs is None:
        attrs = ET.SubElement(first_measure, q('attributes'))

    key_el = attrs.find(q('key'))
    if key_el is None:
        key_el = ET.SubElement(attrs, q('key'))
    fifths_el = key_el.find(q('fifths'))
    if fifths_el is None:
        fifths_el = ET.SubElement(key_el, q('fifths'))
    fifths_el.text = "0"

    mode_el = key_el.find(q('mode'))
    if mode_el is None:
        mode_el = ET.SubElement(key_el, q('mode'))
    mode_el.text = 'minor' if _should_use_minor_mode(prefer_mode, key_info) else 'major'

    clef_el = attrs.find(q('clef'))
    if clef_el is None:
        clef_el = ET.SubElement(attrs, q('clef'))
    for child in list(clef_el):
        clef_el.remove(child)
    ET.SubElement(clef_el, q('sign')).text = 'G'
    ET.SubElement(clef_el, q('line')).text = '2'


def _update_part_list_metadata(root: ET.Element, q) -> None:
    part_list = root.find(q('part-list'))
    if part_list is None:
        return
    for idx, score_part in enumerate(part_list.findall(q('score-part')), start=1):
        part_name = score_part.find(q('part-name'))
        if part_name is None:
            part_name = ET.SubElement(score_part, q('part-name'))
        part_name.text = "Ocarina"

        midi_inst = score_part.find(q('midi-instrument'))
        if midi_inst is None:
            midi_inst = ET.SubElement(score_part, q('midi-instrument'), attrib={'id': f'P{idx}-I1'})
        program = midi_inst.find(q('midi-program'))
        if program is None:
            program = ET.SubElement(midi_inst, q('midi-program'))
        program.text = "80"


def _summarize_part_range(part: ET.Element, q) -> Tuple[Dict[str, Optional[int]], Dict[str, Optional[str]]]:
    lowest = highest = None
    count = 0
    for measure in part.findall(q('measure')):
        for note in measure.findall(q('note')):
            if note.find(q('rest')) is not None:
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


def _collect_primary_voice_midis(part: ET.Element, q) -> List[int]:
    """Return MIDI values for voice-one pitched notes in ``part``."""

    midis: List[int] = []
    for measure in part.findall(q("measure")):
        for note in measure.findall(q("note")):
            if note.find(q("rest")) is not None:
                continue
            if not is_voice_one(note, q):
                continue
            pitch_data = get_pitch_data(note, q)
            if pitch_data is None:
                continue
            midis.append(pitch_data.midi)
    return midis


def _clamp_to_register_window(
    note_midis: Iterable[int],
    transpose_semitones: int,
    midi_min: int,
    midi_max: int,
) -> int:
    """Return an octave shift that keeps the melody in a lower register.

    The returned shift is always a multiple of 12 semitones (an octave) so the
    tonal centre established by ``transpose_semitones`` is preserved.  Among the
    feasible octave shifts we choose the one that keeps the arranged notes close
    to the middle-lower portion of the instrument range.
    """

    midis = list(note_midis)
    if not midis:
        return 0

    lowest = min(midis)
    if lowest == max(midis):
        base_average = lowest + transpose_semitones
    else:
        base_average = mean(midis) + transpose_semitones

    # Determine the allowable shift range for the full melody so we do not push
    # any note outside of the requested register window.
    shift_min = max(midi_min - (midi + transpose_semitones) for midi in midis)
    shift_max = min(midi_max - (midi + transpose_semitones) for midi in midis)
    if shift_min > shift_max:
        return 0

    lower_octave = math.ceil(shift_min / 12)
    upper_octave = math.floor(shift_max / 12)
    if lower_octave > upper_octave:
        return 0

    candidates = [octave * 12 for octave in range(lower_octave, upper_octave + 1)]
    if not candidates:
        return 0

    register_midpoint = midi_min + 0.4 * (midi_max - midi_min)

    def _score(shift: int) -> tuple[float, int]:
        average_with_shift = base_average + shift
        distance = abs(average_with_shift - register_midpoint)
        return (distance, shift)

    return min((_score(candidate) for candidate in candidates), default=(0.0, 0))[1]


def transform_to_ocarina(
    tree: ET.ElementTree,
    root: ET.Element,
    prefer_mode: str = 'auto',
    range_min: str = 'A4',
    range_max: str = 'F6',
    prefer_flats: bool = True,
    collapse_chords: bool = True,
    transpose_offset: int = 0,
) -> Dict:
    q = lambda t: qname(root, t)
    key_info = analyze_key(root)
    auto_transpose = compute_transpose_semitones(key_info.get('tonic') or 'C', prefer_mode)
    transpose_semitones = auto_transpose + transpose_offset

    melodic_part = _select_primary_part(root, q)
    _ensure_primary_attributes(melodic_part, q, prefer_mode, key_info)
    _update_part_list_metadata(root, q)

    midi_min = parse_note_name(range_min)
    midi_max = parse_note_name(range_max)
    if midi_min > midi_max:
        raise ValueError("range_min must be less than or equal to range_max")
    note_midis = _collect_primary_voice_midis(melodic_part, q)
    register_shift = _clamp_to_register_window(
        note_midis,
        transpose_semitones=transpose_semitones,
        midi_min=midi_min,
        midi_max=midi_max,
    )
    transpose_semitones += register_shift
    adapter = _MeasureAdapter(
        q,
        transpose_semitones,
        midi_min,
        midi_max,
        prefer_flats,
        collapse_chords,
    )

    for measure in melodic_part.findall(q('measure')):
        adapter.adapt_measure(measure)

    range_midi, range_names = _summarize_part_range(melodic_part, q)
    return {
        "orig_key": key_info,
        "transpose_semitones": transpose_semitones,
        "auto_transpose_semitones": auto_transpose,
        "manual_transpose_offset": transpose_offset,
        "register_shift_semitones": register_shift,
        "range_midi": range_midi,
        "range_names": range_names,
    }


def favor_lower_register(root: ET.Element, range_min: str = "A4") -> int:
    q = lambda t: qname(root, t)
    midi_min = parse_note_name(range_min)
    shifted = 0

    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                if note.find(q('rest')) is not None:
                    continue
                pitch_data = get_pitch_data(note, q)
                if pitch_data is None:
                    continue
                lowered = pitch_data.midi - 12
                if lowered >= midi_min:
                    pitch_data.update_from_midi(lowered, q, prefer_flats=True)
                    shifted += 1
    return shifted


def collect_used_pitches(root: ET.Element, flats: bool = True) -> List[str]:
    q = lambda t: qname(root, t)
    names: set[str] = set()
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                if note.find(q('rest')) is not None:
                    continue
                pitch_data = get_pitch_data(note, q)
                if pitch_data is None:
                    continue
                names.add(midi_to_name(pitch_data.midi, flats=flats))
    return sorted(names, key=lambda nm: parse_note_name(nm))


__all__ = [
    'collect_used_pitches',
    'favor_lower_register',
    'transform_to_ocarina',
]
