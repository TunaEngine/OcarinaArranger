"""Key detection utilities that guide Alto C transposition decisions."""

from __future__ import annotations

from typing import Dict
import xml.etree.ElementTree as ET

from .musicxml import qname
from .pitch import NAME_TO_PC_TONIC

CIRCLE_MAJOR = {
    -7: 'Cb',
    -6: 'Gb',
    -5: 'Db',
    -4: 'Ab',
    -3: 'Eb',
    -2: 'Bb',
    -1: 'F',
    0: 'C',
    1: 'G',
    2: 'D',
    3: 'A',
    4: 'E',
    5: 'B',
    6: 'F#',
    7: 'C#',
}
RELATIVE_MINOR = {
    -7: 'Abm',
    -6: 'Ebm',
    -5: 'Bbm',
    -4: 'Fm',
    -3: 'Cm',
    -2: 'Gm',
    -1: 'Dm',
    0: 'Am',
    1: 'Em',
    2: 'Bm',
    3: 'F#m',
    4: 'C#m',
    5: 'G#m',
    6: 'D#m',
    7: 'A#m',
}


def analyze_key(root: ET.Element) -> Dict:
    q = lambda t: qname(root, t)
    for part in root.findall(q('part')):
        for measure in part.findall(q('measure')):
            attrs = measure.find(q('attributes'))
            if attrs is not None:
                key = attrs.find(q('key'))
                if key is not None:
                    fifths = key.find(q('fifths'))
                    mode_el = key.find(q('mode'))
                    if fifths is not None:
                        fifths_val = int((fifths.text or '0').strip())
                        mode = (mode_el.text.strip() if mode_el is not None and mode_el.text else None)
                        tonic = (
                            RELATIVE_MINOR.get(fifths_val)
                            if (mode or '').lower().startswith('min')
                            else CIRCLE_MAJOR.get(fifths_val)
                        )
                        return {"fifths": fifths_val, "mode": mode, "tonic": tonic}
    return {"fifths": 0, "mode": "major", "tonic": "C"}


def compute_transpose_semitones(orig_tonic: str, prefer_mode: str) -> int:
    """Return semitone shift needed to move music into C major or A minor."""
    is_minor = orig_tonic.endswith('m')
    if prefer_mode == 'minor' or (prefer_mode == 'auto' and is_minor):
        target_tonic = 'Am'
    else:
        target_tonic = 'C'

    def tonic_pc(name: str) -> int:
        return NAME_TO_PC_TONIC[name.rstrip('m')]

    orig_pc = tonic_pc(orig_tonic)
    target_pc = tonic_pc(target_tonic)
    return (target_pc - orig_pc) % 12


__all__ = [
    'CIRCLE_MAJOR',
    'RELATIVE_MINOR',
    'analyze_key',
    'compute_transpose_semitones',
]
