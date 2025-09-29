from __future__ import annotations

from ocarina_tools import analyze_key, compute_transpose_semitones

from helpers import make_chord_score


def test_compute_transpose_semitones_respects_mode():
    assert compute_transpose_semitones("D", "major") == 10
    assert compute_transpose_semitones("Em", "auto") == 5
    assert compute_transpose_semitones("C", "minor") == 9


def test_compute_transpose_semitones_wraps_over_octave():
    assert compute_transpose_semitones("B", "major") == 1
    assert compute_transpose_semitones("G#m", "auto") == 1


def test_analyze_key_reads_fifths():
    _, root = make_chord_score()
    info = analyze_key(root)
    assert info["fifths"] == 2
    assert info["tonic"] == "D"
    assert info["mode"] == "major"
