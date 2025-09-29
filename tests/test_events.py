from __future__ import annotations

import xml.etree.ElementTree as ET

from ocarina_tools import get_note_events, get_time_signature

from helpers import make_linear_score


def test_get_note_events_returns_sorted_sequence():
    _, root = make_linear_score()
    events, ppq = get_note_events(root)
    assert ppq == 480
    assert events == [(0, 480, 60, 79), (960, 960, 62, 79)]


def test_get_note_events_uses_part_programs():
    tree, root = make_linear_score()
    part_list = root.find('part-list')
    assert part_list is not None
    score_part = part_list.find('score-part')
    assert score_part is not None
    midi_inst = ET.SubElement(score_part, 'midi-instrument', attrib={'id': 'P1-I1'})
    ET.SubElement(midi_inst, 'midi-program').text = '1'

    events, _ = get_note_events(root)

    assert events[0][-1] == 0


def test_get_time_signature_defaults_to_four_four():
    _, root = make_linear_score()
    assert get_time_signature(root) == (4, 4)
