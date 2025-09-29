from __future__ import annotations

from ocarina_tools import collect_used_pitches, favor_lower_register, transform_to_ocarina

from ..helpers import make_chord_score


def test_favor_lower_register_applies_octave_drop():
    tree, root = make_chord_score()
    transform_to_ocarina(tree, root, prefer_mode="auto", range_min="A4", range_max="F6")
    shifted = favor_lower_register(root, range_min="A4")
    assert shifted == 2
    part = root.findall("part")[0]
    first_note = part.findall("measure")[0].find("note")
    pitch = first_note.find("pitch")
    assert pitch.find("step").text == "A"
    assert pitch.find("octave").text == "4"
    second_measure_notes = part.findall("measure")[1].findall("note")
    pitched_notes = [n for n in second_measure_notes if n.find("rest") is None]
    assert len(pitched_notes) == 1
    pitch2 = pitched_notes[0].find("pitch")
    assert pitch2.find("step").text == "D"
    assert pitch2.find("octave").text == "5"


def test_favor_lower_register_respects_floor_threshold():
    tree, root = make_chord_score()
    transform_to_ocarina(tree, root, range_min="A4", range_max="F6")
    shifted = favor_lower_register(root, range_min="A5")
    assert shifted == 0
    first_note = root.findall("part")[0].findall("measure")[0].find("note")
    pitch = first_note.find("pitch")
    assert pitch.find("step").text == "A"
    assert pitch.find("octave").text == "5"


def test_collect_used_pitches_sorted_after_lowering():
    tree, root = make_chord_score()
    transform_to_ocarina(tree, root, prefer_mode="auto", range_min="A4", range_max="F6")
    favor_lower_register(root, range_min="A4")
    pitches = collect_used_pitches(root)
    assert pitches == ["A4", "D5"]
