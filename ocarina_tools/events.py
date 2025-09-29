"""Convenience views over MusicXML for note timelines and time signatures."""

from __future__ import annotations

from typing import List, Tuple
import xml.etree.ElementTree as ET

from .musicxml import first_divisions, get_pitch_data, qname
from .instruments import OCARINA_GM_PROGRAM, part_programs


def get_note_events(root: ET.Element) -> tuple[list[tuple[int, int, int, int]], int]:
    divisions = first_divisions(root)
    ppq = 480
    scale = ppq / max(1, divisions)
    q = lambda t: qname(root, t)
    programs = part_programs(root)
    events: List[Tuple[int, int, int, int]] = []
    for index, part in enumerate(root.findall(q('part'))):
        part_id = (part.get('id') or f'P{index + 1}').strip()
        if not part_id:
            part_id = f'P{index + 1}'
        program = programs.get(part_id, OCARINA_GM_PROGRAM)
        voice_pos: dict[str, int] = {}
        for measure in part.findall(q('measure')):
            for note in measure.findall(q('note')):
                voice_el = note.find(q('voice'))
                voice = (voice_el.text.strip() if (voice_el is not None and voice_el.text) else '1')
                pos = voice_pos.get(voice, 0)
                dur_el = note.find(q('duration'))
                dur_text = (dur_el.text or '').strip() if dur_el is not None and dur_el.text else ''
                dur_div = int(dur_text) if dur_text.isdigit() else 0
                is_chord = note.find(q('chord')) is not None
                is_rest = note.find(q('rest')) is not None
                if not is_rest:
                    pitch_data = get_pitch_data(note, q)
                    if pitch_data is not None:
                        onset_ticks = int(round(pos * scale))
                        dur_ticks = int(round(dur_div * scale))
                        events.append((onset_ticks, max(1, dur_ticks), pitch_data.midi, program))
                if not is_chord:
                    voice_pos[voice] = pos + dur_div
    return events, ppq


def get_time_signature(root: ET.Element) -> tuple[int, int]:
    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            attrs = measure.find(q('attributes'))
            if attrs is not None:
                ts = attrs.find(q('time'))
                if ts is not None:
                    beats_el = ts.find(q('beats'))
                    beat_type_el = ts.find(q('beat-type'))
                    try:
                        beats = int((beats_el.text or '4').strip()) if beats_el is not None else 4
                        beat_type = int((beat_type_el.text or '4').strip()) if beat_type_el is not None else 4
                        return beats, beat_type
                    except Exception:
                        pass
            break
        break
    return 4, 4


def detect_tempo_bpm(root: ET.Element, default_bpm: int = 120) -> int:
    """Return the first tempo marking found in ``root`` or ``default_bpm``."""

    def _parse_tempo(value: str | None) -> int | None:
        if not value:
            return None
        try:
            bpm = int(float(value))
        except (TypeError, ValueError):
            return None
        return max(20, min(300, bpm))

    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            for direction in measure.findall(q('direction')):
                sound = direction.find(q('sound'))
                tempo = _parse_tempo(sound.get('tempo') if sound is not None else None)
                if tempo is not None:
                    return tempo
            sound = measure.find(q('sound'))
            tempo = _parse_tempo(sound.get('tempo') if sound is not None else None)
            if tempo is not None:
                return tempo
    return max(20, min(300, int(default_bpm)))


__all__ = [
    'get_note_events',
    'get_time_signature',
    'detect_tempo_bpm',
]
