from domain.arrangement.difficulty import difficulty_score, summarize_difficulty
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentWindwayRange


def _note(onset: int, midi: int, duration: int) -> PhraseNote:
    return PhraseNote(onset=onset, duration=duration, midi=midi)


def test_fast_windway_switch_penalty_increases_difficulty() -> None:
    pulses_per_quarter = 480
    sixteenth = pulses_per_quarter // 4
    notes = (
        _note(0, 60, sixteenth),
        _note(sixteenth, 62, sixteenth),
        _note(sixteenth * 2, 60, sixteenth),
        _note(sixteenth * 3, 62, sixteenth),
    )
    span = PhraseSpan(notes, pulses_per_quarter=pulses_per_quarter)

    same_chamber = InstrumentWindwayRange(
        min_midi=55,
        max_midi=72,
        windway_ids=("primary", "secondary"),
        windway_map={60: (0,), 62: (0,)},
    )
    switching = InstrumentWindwayRange(
        min_midi=55,
        max_midi=72,
        windway_ids=("primary", "secondary"),
        windway_map={60: (0,), 62: (1,)},
    )

    baseline_summary = summarize_difficulty(span, same_chamber)
    switching_summary = summarize_difficulty(span, switching)

    assert baseline_summary.fast_windway_switch_exposure == 0.0
    assert switching_summary.fast_windway_switch_exposure > 0.0
    assert difficulty_score(switching_summary) > difficulty_score(baseline_summary)


def test_fast_windway_switch_penalty_counts_longer_transitions() -> None:
    pulses_per_quarter = 480
    eighth = pulses_per_quarter // 2
    notes = (
        _note(0, 60, eighth),
        _note(eighth, 62, eighth),
    )
    span = PhraseSpan(notes, pulses_per_quarter=pulses_per_quarter)

    switching = InstrumentWindwayRange(
        min_midi=55,
        max_midi=72,
        windway_ids=("primary", "secondary"),
        windway_map={60: (0,), 62: (1,)},
    )

    summary = summarize_difficulty(span, switching)

    assert summary.fast_windway_switch_exposure > 0.0
