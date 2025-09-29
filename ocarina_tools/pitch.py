"""Pitch conversion tables and helpers shared across the ocarina toolkit."""

from __future__ import annotations

import re
from typing import Tuple

STEP_TO_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
PC_TO_STEP_SHARP = {
    0: ('C', 0),
    1: ('C', 1),
    2: ('D', 0),
    3: ('D', 1),
    4: ('E', 0),
    5: ('F', 0),
    6: ('F', 1),
    7: ('G', 0),
    8: ('G', 1),
    9: ('A', 0),
    10: ('A', 1),
    11: ('B', 0),
}
PC_TO_STEP_FLAT = {
    0: ('C', 0),
    1: ('D', -1),
    2: ('D', 0),
    3: ('E', -1),
    4: ('E', 0),
    5: ('F', 0),
    6: ('G', -1),
    7: ('G', 0),
    8: ('A', -1),
    9: ('A', 0),
    10: ('B', -1),
    11: ('B', 0),
}

NAME_TO_PC = {
    'C': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'Fb': 4,
    'E#': 5,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11,
    'Cb': 11,
}
PC_TO_NAME_SHARP = {value: key for key, value in NAME_TO_PC.items() if len(key) == 1 or '#' in key}
PC_TO_NAME_FLAT = {0: 'C', 1: 'Db', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F', 6: 'Gb', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'}
NAME_TO_PC_TONIC = {
    'C': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11,
    'Cb': 11,
}


def pitch_to_midi(step: str, alter: int, octave: int) -> int:
    """Convert MusicXML pitch data (C4=60)."""
    pc = STEP_TO_PC[step] + (alter or 0)
    return (octave + 1) * 12 + pc


def midi_to_pitch(midi: int, prefer_flats: bool = True) -> Tuple[str, int, int]:
    octave = midi // 12 - 1
    pc = midi % 12
    step, alter = (PC_TO_STEP_FLAT if prefer_flats else PC_TO_STEP_SHARP)[pc]
    return step, alter, octave


def parse_note_name(name: str) -> int:
    """Parse forms like 'A4', 'F#5', 'Bb4' into a MIDI integer."""
    m = re.match(r'^([A-Ga-g])(#{1}|b{1})?(\d+)$', name.strip())
    if not m:
        raise ValueError(f"Bad note name: {name}")
    step = m.group(1).upper()
    acc = m.group(2) or ''
    octv = int(m.group(3))
    key = step + ('#' if acc == '#' else 'b' if acc == 'b' else '')
    pc = NAME_TO_PC[key]
    return (octv + 1) * 12 + pc


def midi_to_name(midi: int, flats: bool = True) -> str:
    pc = midi % 12
    octave = midi // 12 - 1
    base = PC_TO_NAME_FLAT[pc] if flats else PC_TO_NAME_SHARP[pc]
    return f"{base}{octave}"


__all__ = [
    'STEP_TO_PC',
    'PC_TO_STEP_SHARP',
    'PC_TO_STEP_FLAT',
    'NAME_TO_PC',
    'PC_TO_NAME_SHARP',
    'PC_TO_NAME_FLAT',
    'NAME_TO_PC_TONIC',
    'pitch_to_midi',
    'midi_to_pitch',
    'parse_note_name',
    'midi_to_name',
]
