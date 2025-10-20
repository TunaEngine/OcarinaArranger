from __future__ import annotations

from typing import Iterable, Sequence

from domain.arrangement.config import clear_instrument_registry, register_instrument_range
from domain.arrangement.gp import GPSessionConfig, ProgramConstraints
from domain.arrangement.gp.penalties import ScoringPenalties
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def clear_registry() -> None:
    clear_instrument_registry()


def _make_span(midis: Sequence[int]) -> PhraseSpan:
    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _make_poly_span(top: Sequence[int], bottom: Sequence[int]) -> PhraseSpan:
    notes: list[PhraseNote] = []
    for index, melody_midi in enumerate(top):
        onset = index * 240
        notes.append(PhraseNote(onset=onset, duration=240, midi=melody_midi))
        if index < len(bottom):
            notes.append(PhraseNote(onset=onset, duration=240, midi=bottom[index]))
    return PhraseSpan(tuple(notes), pulses_per_quarter=480)


def _register_instruments(mapping: Iterable[tuple[str, InstrumentRange]]) -> None:
    for instrument_id, instrument in mapping:
        register_instrument_range(instrument_id, instrument)


def _gp_config() -> GPSessionConfig:
    return GPSessionConfig(
        generations=1,
        population_size=4,
        archive_size=4,
        random_seed=11,
        random_program_count=2,
        crossover_rate=0.0,
        mutation_rate=1.0,
        log_best_programs=1,
        constraints=ProgramConstraints(max_operations=3),
        scoring_penalties=ScoringPenalties(
            range_clamp_penalty=4.0,
            range_clamp_melody_bias=4.0,
        ),
    )


__all__ = [
    "clear_registry",
    "_gp_config",
    "_make_poly_span",
    "_make_span",
    "_register_instruments",
]

