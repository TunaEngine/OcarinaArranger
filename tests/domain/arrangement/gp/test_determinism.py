import json

from domain.arrangement.gp import GPSessionConfig, ProgramConstraints, run_gp_session
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def _make_phrase() -> PhraseSpan:
    notes = (
        PhraseNote(onset=0, duration=240, midi=64, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=240, duration=240, midi=67, tags=frozenset({"pivotal"})),
        PhraseNote(onset=480, duration=240, midi=69, tags=frozenset({"octave-shiftable"})),
        PhraseNote(onset=720, duration=240, midi=72, tags=frozenset()),
    )
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_gp_session_is_deterministic_with_seed() -> None:
    phrase = _make_phrase()
    instrument = InstrumentRange(60, 84)

    config = GPSessionConfig(
        generations=3,
        population_size=6,
        archive_size=4,
        random_seed=17,
        random_program_count=5,
        crossover_rate=0.7,
        mutation_rate=0.6,
        log_best_programs=2,
        span_limits={"phrase": 2},
        constraints=ProgramConstraints(max_operations=4),
    )

    first = run_gp_session(phrase, instrument, config=config)
    second = run_gp_session(phrase, instrument, config=config)

    assert first.winner.program == second.winner.program
    assert first.winner.fitness == second.winner.fitness
    assert first.log.to_dict() == second.log.to_dict()
    assert first.generations == config.generations
    assert first.termination_reason == "generation_limit"

    # JSON serialization guard for debugging payloads
    json.dumps(first.log.to_dict())
