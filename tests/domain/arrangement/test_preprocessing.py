from domain.arrangement.config import GraceSettings
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.preprocessing import apply_grace_realization
from domain.arrangement.soft_key import InstrumentRange


def _grace_note(onset: int, duration: int, midi: int) -> PhraseNote:
    return PhraseNote(
        onset=onset,
        duration=duration,
        midi=midi,
        tags=frozenset({"grace", "ornamental"}),
    )


def test_apply_grace_realization_drops_fast_chain_and_extends_anchor() -> None:
    span = PhraseSpan(
        (
            _grace_note(0, 10, 62),
            _grace_note(10, 10, 64),
            PhraseNote(onset=20, duration=40, midi=65, tags=frozenset()),
            PhraseNote(onset=60, duration=20, midi=67, tags=frozenset()),
        ),
        pulses_per_quarter=120,
    )
    instrument = InstrumentRange(min_midi=55, max_midi=80, comfort_center=67)
    settings = GraceSettings(fast_tempo_bpm=100.0, slow_tempo_bpm=60.0)

    updated_span, events = apply_grace_realization(
        span,
        instrument,
        tempo_bpm=140.0,
        settings=settings,
    )

    assert events, "expected grace normalization explanation"
    anchor, follower = updated_span.notes
    assert "grace" not in anchor.tags
    assert anchor.onset == 0
    assert anchor.duration == 60
    assert follower.onset == 60


def test_apply_grace_realization_trailing_graces_removed() -> None:
    span = PhraseSpan(
        (
            PhraseNote(onset=0, duration=40, midi=60, tags=frozenset()),
            _grace_note(40, 10, 62),
            _grace_note(50, 10, 64),
        ),
        pulses_per_quarter=120,
    )
    instrument = InstrumentRange(min_midi=55, max_midi=80, comfort_center=67)

    updated_span, events = apply_grace_realization(
        span,
        instrument,
        tempo_bpm=None,
    )

    assert updated_span.notes[0].duration == 40
    assert updated_span.notes[0].onset == 0
    assert len(updated_span.notes) == 1
    assert events, "expected trailing grace explanation"
