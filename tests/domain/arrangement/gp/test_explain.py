from domain.arrangement.gp.explain import explain_program
from domain.arrangement.gp.ops import (
    GlobalTranspose,
    LocalOctave,
    SimplifyRhythm,
    SpanDescriptor,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def _phrase() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=480, midi=84),
        PhraseNote(onset=480, duration=480, midi=76),
        PhraseNote(onset=960, duration=480, midi=74),
        PhraseNote(onset=1440, duration=480, midi=72),
        PhraseNote(onset=1920, duration=180, midi=71),
        PhraseNote(onset=2100, duration=180, midi=69),
        PhraseNote(onset=2280, duration=240, midi=67),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_explain_program_orders_events_chronologically() -> None:
    phrase = _phrase()
    instrument = InstrumentRange(min_midi=60, max_midi=72, comfort_center=66)

    early = LocalOctave(
        span=SpanDescriptor(start_onset=0, end_onset=960, label="intro"),
        octaves=-1,
    )
    late = SimplifyRhythm(
        span=SpanDescriptor(start_onset=1920, end_onset=2520, label="closing"),
        subdivisions=2,
    )

    events = explain_program((late, early), phrase, instrument)

    assert [event.reason_code for event in events] == ["range-edge", "rhythm-simplify"]
    assert [event.bar for event in events] == [1, 2]
    assert all(event.span for event in events)


def test_explain_program_reports_transposition_reason() -> None:
    phrase = _phrase()
    instrument = InstrumentRange(min_midi=60, max_midi=80, comfort_center=68)

    events = explain_program((GlobalTranspose(semitones=3),), phrase, instrument)

    assert len(events) == 1
    event = events[0]
    assert event.reason_code == "global-transpose"
    assert "Transposed" in event.reason
    assert event.span is not None
