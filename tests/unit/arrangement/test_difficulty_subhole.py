from dataclasses import dataclass

from domain.arrangement.config import GraceSettings
from domain.arrangement.constraints import SubholeConstraintSettings, SubholePairLimit
from domain.arrangement.difficulty import difficulty_score, summarize_difficulty
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


@dataclass(frozen=True)
class InstrumentWithSubholes(InstrumentRange):
    subhole_settings: SubholeConstraintSettings | None = None


def _subhole_settings() -> SubholeConstraintSettings:
    pair = frozenset((60, 62))
    return SubholeConstraintSettings(
        pair_limits={pair: SubholePairLimit(max_hz=10.0, ease=0.2)}
    )


def test_subhole_transitions_increase_difficulty() -> None:
    pulses_per_quarter = 480
    sixteenth = pulses_per_quarter // 4
    notes = (
        PhraseNote(onset=0, duration=sixteenth, midi=60),
        PhraseNote(onset=sixteenth, duration=sixteenth, midi=62),
        PhraseNote(onset=sixteenth * 2, duration=sixteenth, midi=60),
        PhraseNote(onset=sixteenth * 3, duration=sixteenth, midi=62),
    )
    span = PhraseSpan(notes, pulses_per_quarter=pulses_per_quarter)

    instrument = InstrumentWithSubholes(
        min_midi=55,
        max_midi=72,
        subhole_settings=_subhole_settings(),
    )

    summary = summarize_difficulty(span, instrument)

    assert summary.subhole_transition_duration > 0.0
    assert summary.subhole_exposure > 0.0

    penalized = GraceSettings(
        subhole_exposure_weight=1.0,
        fast_windway_switch_weight=0.0,
        grace_bonus=0.0,
    )
    muted = GraceSettings(
        subhole_exposure_weight=0.0,
        fast_windway_switch_weight=0.0,
        grace_bonus=0.0,
    )

    penalized_score = difficulty_score(summary, penalized)
    muted_score = difficulty_score(summary, muted)

    assert penalized_score > muted_score
