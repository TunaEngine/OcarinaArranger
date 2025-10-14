from __future__ import annotations

from domain.arrangement.melody import isolate_melody
from domain.arrangement.phrase import PhraseNote, PhraseSpan


def _note(onset: int, duration: int, midi: int) -> PhraseNote:
    return PhraseNote(onset=onset, duration=duration, midi=midi)


def test_isolate_melody_prefers_voice_continuity_over_high_harmony() -> None:
    span = PhraseSpan(
        (
            _note(0, 480, 74),
            _note(480, 480, 86),
            _note(480, 240, 74),
        )
    )

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == [74, 74]

    assert result.actions
    assert "voice_continuity" in result.actions[0].reason


def test_isolate_melody_prefers_anchor_register_when_octaves_overlap() -> None:
    span = PhraseSpan(
        (
            _note(0, 360, 74),
            _note(0, 480, 86),
            _note(480, 360, 76),
            _note(480, 480, 88),
            _note(960, 360, 78),
            _note(960, 480, 90),
        )
    )

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == [74, 76, 78]

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_chooses_lower_octave_on_initial_duplicate() -> None:
    span = PhraseSpan(
        (
            _note(0, 480, 74),
            _note(0, 960, 86),
            _note(480, 480, 76),
            _note(480, 960, 88),
            _note(960, 480, 78),
            _note(960, 960, 90),
            _note(1440, 480, 80),
            _note(1440, 960, 92),
        )
    )

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == [74, 76, 78, 80]

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_prefers_lower_register_when_high_voice_sustains() -> None:
    span = PhraseSpan(
        (
            _note(0, 480, 88),
            _note(480, 120, 74),
            _note(480, 480, 86),
        )
    )

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == [88, 74]

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_resists_high_octave_pivot_pressure() -> None:
    """High voices dominating the pivot should not force the melody up an octave."""

    sustaining_high_voice = tuple(
        _note(index * 240, 960, 86) for index in range(8)
    )
    melody_voice = (
        _note(0, 240, 74),
        _note(240, 240, 76),
        _note(480, 240, 78),
        _note(720, 240, 81),
    )

    span = PhraseSpan(sustaining_high_voice + melody_voice)

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes[: len(melody_voice)]]
    assert kept_midis == [74, 76, 78, 81]

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_tracks_polyphonic_shire_excerpt() -> None:
    """Ensure the Shire polyphonic sample keeps the lower register melody."""

    melody_midis = [
        74,
        76,
        78,
        81,
        78,
        78,
        76,
        78,
        76,
        74,
        78,
        81,
        83,
        86,
        85,
        81,
        78,
        79,
        78,
        76,
    ]

    notes = []
    for idx, midi in enumerate(melody_midis):
        onset = idx * 240
        notes.append(_note(onset, 240, midi))
        # The arrangement also contains sustained accompaniment voices an octave
        # above the melody.  They begin on the same onset but hold at least
        # twice as long, which previously fooled the isolation heuristics into
        # promoting the higher octave and ultimately erased measures 5–6.
        notes.append(_note(onset, 720, midi + 12))

    span = PhraseSpan(tuple(notes))

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == melody_midis

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_shire_excerpt_without_low_pedal() -> None:
    """Regression: lose melody when high duplicates dominate and sustain."""

    melody_midis = [
        74,
        76,
        78,
        81,
        78,
        78,
        76,
        78,
        76,
        74,
        78,
        81,
        83,
        86,
        85,
        81,
        78,
        79,
        78,
        76,
    ]

    notes = []
    for idx, midi in enumerate(melody_midis):
        onset = idx * 240
        notes.append(_note(onset, 240, midi))

        if idx < 10:
            # Multiple ensemble voices echo the melody an octave above using the
            # same rhythm.  They outweigh the single lower-octave melody and
            # bias the register pivot upward.
            for _ in range(4):
                notes.append(_note(onset, 240, midi + 12))
        else:
            # Later measures hold harmony tones around D6.  When the melody was
            # already promoted an octave above, the continuity heuristic latched
            # onto these sustained notes and dropped the real melody entirely.
            sustain = 960 if idx % 2 == 0 else 720
            harmony_midi = 86 if idx % 3 else 88
            notes.append(_note(onset, sustain, harmony_midi))

    span = PhraseSpan(tuple(notes))

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes]
    assert kept_midis == melody_midis

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)


def test_isolate_melody_prefers_anchor_over_lower_octave_duplicates() -> None:
    """When three octaves share a pitch class, keep the anchored register."""

    span = PhraseSpan(
        (
            _note(0, 240, 74),
            _note(0, 960, 62),
            _note(0, 960, 86),
            _note(480, 240, 76),
            _note(480, 960, 74),
            _note(480, 960, 88),
        )
    )

    result = isolate_melody(span)

    kept_midis = [note.midi for note in result.span.notes[:2]]
    assert kept_midis == [74, 76]

    assert result.actions
    assert any("register_anchor" in action.reason for action in result.actions)
