"""Coverage for the range guard helpers."""

from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.range_guard import enforce_instrument_range
from domain.arrangement.soft_key import InstrumentRange


def _make_span(*midis: int) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 120, duration=120, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes))


def test_high_notes_drop_by_octave_instead_of_clamping() -> None:
    """Notes above the range keep their pitch class after clamping."""

    instrument = InstrumentRange(min_midi=69, max_midi=89)
    original = _make_span(102)

    adjusted, event, _ = enforce_instrument_range(
        original,
        instrument,
        beats_per_measure=4,
    )

    assert event is not None
    assert adjusted.notes[0].midi == 78
    # Two octaves above the range should yield a downward ottava shift marker.
    assert adjusted.notes[0].ottava_shifts


def test_low_melody_voice_rises_by_octave() -> None:
    """Top-voice notes below range climb by octaves instead of flattening."""

    instrument = InstrumentRange(min_midi=69, max_midi=89)
    original = _make_span(59)

    adjusted, event, _ = enforce_instrument_range(
        original,
        instrument,
        beats_per_measure=4,
    )

    assert event is not None
    assert adjusted.notes[0].midi == 71
    assert adjusted.notes[0].ottava_shifts


def test_top_voice_near_floor_prefers_boundary_over_octave() -> None:
    """Melody notes barely below range clamp to the boundary to avoid leaps."""

    instrument = InstrumentRange(min_midi=69, max_midi=89)
    original = _make_span(65)

    adjusted, event, _ = enforce_instrument_range(
        original,
        instrument,
        beats_per_measure=4,
    )

    assert event is not None
    assert adjusted.notes[0].midi == instrument.min_midi
    assert not adjusted.notes[0].ottava_shifts


def test_boundary_clamp_skips_when_surrounded_by_floor_notes() -> None:
    """Notes squeezed between boundary tones keep the melodic contour."""

    instrument = InstrumentRange(min_midi=57, max_midi=89)
    original = _make_span(57, 56, 57)

    adjusted, event, _ = enforce_instrument_range(
        original,
        instrument,
        beats_per_measure=4,
    )

    assert event is not None
    adjusted_midis = [note.midi for note in adjusted.notes]
    assert adjusted_midis == [57, 68, 57]
    assert adjusted.notes[1].ottava_shifts


def test_low_inner_voice_still_clamps_to_floor() -> None:
    """Accompaniment voices stay anchored at the instrument boundary."""

    instrument = InstrumentRange(min_midi=69, max_midi=89)
    notes = (
        PhraseNote(onset=0, duration=240, midi=74),
        PhraseNote(onset=0, duration=240, midi=42),
    )
    original = PhraseSpan(notes)

    adjusted, event, _ = enforce_instrument_range(
        original,
        instrument,
        beats_per_measure=4,
    )

    assert event is not None
    assert [note.midi for note in adjusted.notes] == [instrument.min_midi, 74]
    assert not adjusted.notes[0].ottava_shifts
