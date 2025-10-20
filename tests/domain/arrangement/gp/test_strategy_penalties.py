"""Focused tests for penalty gating behaviour in the GP strategy."""

from __future__ import annotations

from domain.arrangement.config import clear_instrument_registry, register_instrument_range
from domain.arrangement.gp import GPSessionConfig
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.penalties import ScoringPenalties
from domain.arrangement.gp.strategy import _score_instrument
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def _make_span(midis: list[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def test_range_clamp_penalty_blocks_clamped_candidates() -> None:
    clear_instrument_registry()
    instrument = InstrumentRange(min_midi=72, max_midi=96, comfort_center=84)
    register_instrument_range("ocarina", instrument)

    phrase = _make_span([60, 74, 67])
    fitness_config = GPSessionConfig().fitness_config
    programs = ((), (GlobalTranspose(12),))

    allowed_candidate, _, _ = _score_instrument(
        instrument_id="ocarina",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(range_clamp_penalty=4.0),
    )
    bias_candidate, _, _ = _score_instrument(
        instrument_id="ocarina",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(range_clamp_melody_bias=5.0),
    )
    blocked_candidate, _, _ = _score_instrument(
        instrument_id="ocarina",
        instrument=instrument,
        phrase=phrase,
        programs=programs,
        fitness_config=fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(range_clamp_penalty=5.0),
    )

    assert allowed_candidate.program in {(), (GlobalTranspose(12),)}
    assert blocked_candidate.program and isinstance(blocked_candidate.program[0], GlobalTranspose)
    assert blocked_candidate.program[0].semitones == 12
    assert all(
        getattr(event, "reason", "") != "range-clamp"
        for event in blocked_candidate.explanations
    )
    assert bias_candidate.program and isinstance(bias_candidate.program[0], GlobalTranspose)
    assert bias_candidate.program[0].semitones == 12


def test_range_clamp_disable_keeps_out_of_range_notes() -> None:
    clear_instrument_registry()
    instrument = InstrumentRange(min_midi=69, max_midi=89, comfort_center=80)
    register_instrument_range("ocarina", instrument)

    # Phrase spans notes both below and above the playable window so clamping would
    # normally adjust it on both ends.
    phrase = _make_span([60, 72, 90])
    fitness_config = GPSessionConfig().fitness_config

    candidate, _, _ = _score_instrument(
        instrument_id="ocarina",
        instrument=instrument,
        phrase=phrase,
        programs=((),),
        fitness_config=fitness_config,
        beats_per_measure=4,
        penalties=ScoringPenalties(
            range_clamp_penalty=5.0,
            range_clamp_melody_bias=5.0,
        ),
    )

    span_midis = [note.midi for note in candidate.span.notes]
    assert min(span_midis) < instrument.min_midi
    assert max(span_midis) > instrument.max_midi
    reason_codes = [event.reason_code for event in candidate.explanations]
    assert "range-clamp" not in reason_codes
    assert "range-clamp-disabled" in reason_codes
