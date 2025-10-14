"""Shared helpers for GP arrangement regression tests."""

from __future__ import annotations

from typing import Sequence

from domain.arrangement.gp import GPSessionConfig, ProgramConstraints
from domain.arrangement.phrase import PhraseNote, PhraseSpan


def gp_config() -> GPSessionConfig:
    """Return a deterministic GP session configuration for tests."""

    return GPSessionConfig(
        generations=1,
        population_size=4,
        archive_size=4,
        random_seed=7,
        random_program_count=2,
        crossover_rate=0.0,
        mutation_rate=1.0,
        log_best_programs=1,
        constraints=ProgramConstraints(max_operations=3),
    )


def make_span(midis: Sequence[int], *, pulses_per_quarter: int = 480) -> PhraseSpan:
    """Create a phrase whose notes follow ``midis`` using eighth-note spacing."""

    notes = [
        PhraseNote(onset=index * 240, duration=240, midi=midi)
        for index, midi in enumerate(midis)
    ]
    return PhraseSpan(tuple(notes), pulses_per_quarter=pulses_per_quarter)


def bass_phrase(
    *,
    pulses_per_quarter: int = 480,
    intro_eighths: int = 0,
    extra_upper_midi: int | None = None,
) -> PhraseSpan:
    """Return the Bass C regression phrase used across multiple tests."""

    melody = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]
    pad_notes = [
        (48, 52),
        (50, 53),
        (50, 53),
        (52, 55),
        (53, 57),
        (55, 59),
        (53, 57),
        (52, 55),
        (53, 57),
        (52, 55),
    ]
    sustained_bass = [
        (0, 40, 4),
        (2, 45, 4),
        (4, 43, 4),
        (6, 45, 4),
        (9, 47, 6),
    ]

    eighth = pulses_per_quarter // 2
    notes: list[PhraseNote] = []

    if intro_eighths > 0:
        duration = intro_eighths * eighth
        notes.append(PhraseNote(onset=0, duration=duration, midi=40))

    for index, melody_midi in enumerate(melody):
        onset = (intro_eighths + index) * eighth
        notes.append(PhraseNote(onset=onset, duration=eighth, midi=melody_midi))
        top_pad, lower_pad = pad_notes[index]
        notes.append(PhraseNote(onset=onset, duration=eighth, midi=top_pad))
        notes.append(PhraseNote(onset=onset, duration=eighth, midi=lower_pad))
        if extra_upper_midi is not None:
            notes.append(PhraseNote(onset=onset, duration=eighth, midi=extra_upper_midi))

    for start_index, midi, length in sustained_bass:
        onset = (intro_eighths + start_index) * eighth
        duration = length * eighth
        notes.append(PhraseNote(onset=onset, duration=duration, midi=midi))

    return PhraseSpan(tuple(notes), pulses_per_quarter=pulses_per_quarter)


__all__ = ["bass_phrase", "gp_config", "make_span"]

