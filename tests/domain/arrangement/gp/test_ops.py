from domain.arrangement.gp.ops import (
    GlobalTranspose,
    LocalOctave,
    RangeDomain,
    SimplifyRhythm,
    SpanDescriptor,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan


def _make_phrase() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=240, midi=60),
        PhraseNote(onset=240, duration=240, midi=62),
        PhraseNote(onset=480, duration=480, midi=64),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_span_descriptor_resolve_and_clamp() -> None:
    phrase = _make_phrase()
    descriptor = SpanDescriptor()
    assert descriptor.resolve(phrase) == (0, phrase.total_duration)

    trimmed = SpanDescriptor(start_onset=-120, end_onset=2000, label="riff").clamp(phrase)
    assert trimmed == SpanDescriptor(start_onset=0, end_onset=phrase.total_duration, label="riff")


def test_span_descriptor_rejects_invalid_regions() -> None:
    phrase = _make_phrase()
    descriptor = SpanDescriptor(start_onset=phrase.total_duration + 1, end_onset=phrase.total_duration + 10)
    try:
        descriptor.resolve(phrase)
    except ValueError:
        pass
    else:  # pragma: no cover - fail fast if validation does not trigger
        raise AssertionError("Expected descriptor to reject out-of-bounds span")


def test_parameter_domains_enforced_on_primitives() -> None:
    transpose = GlobalTranspose(semitones=3)
    octave = LocalOctave(span=SpanDescriptor(start_onset=0, end_onset=480), octaves=-1)
    rhythm = SimplifyRhythm(span=SpanDescriptor(start_onset=0, end_onset=480), subdivisions=2)

    assert transpose.parameter_domains()["semitones"].contains(transpose.semitones)
    assert octave.parameter_domains()["octaves"].contains(octave.octaves)
    assert rhythm.parameter_domains()["subdivisions"].contains(rhythm.subdivisions)


def test_range_domain_clamp_respects_bounds() -> None:
    domain = RangeDomain(-4, 4, step=2)
    assert not domain.contains(3)
    assert domain.clamp(3) == 2
    assert domain.clamp(-6) == -4
