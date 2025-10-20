"""Helpers for assembling GP program candidate lists."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, LocalOctave, SpanDescriptor
from .program_utils import auto_range_programs as _default_auto_range_programs


def _add_program(
    collection: list[tuple[GPPrimitive, ...]],
    program: Iterable[GPPrimitive],
    existing: set[tuple[GPPrimitive, ...]],
) -> None:
    program_tuple = tuple(program)
    if program_tuple in existing:
        return
    collection.append(program_tuple)
    existing.add(program_tuple)


def _extend_local_octave_variants(
    programs: Sequence[tuple[GPPrimitive, ...]],
    phrase: PhraseSpan,
) -> list[tuple[GPPrimitive, ...]]:
    variants: list[tuple[GPPrimitive, ...]] = []
    for program in programs:
        for index, operation in enumerate(program):
            if not isinstance(operation, LocalOctave) or not operation.octaves:
                continue
            start_onset = getattr(operation.span, "start_onset", None)
            end_onset = getattr(operation.span, "end_onset", None)
            label = getattr(operation.span, "label", "phrase")
            extended_span = None
            if start_onset not in (None, 0) and operation.octaves > 0:
                extended_span = SpanDescriptor(start_onset=0, end_onset=end_onset, label=label)
            elif (
                end_onset is not None
                and end_onset < phrase.total_duration
                and operation.octaves < 0
            ):
                extended_span = SpanDescriptor(start_onset=start_onset, end_onset=None, label=label)
            if extended_span is None:
                continue
            extended_program = list(program)
            extended_program[index] = LocalOctave(span=extended_span, octaves=operation.octaves)
            variants.append(tuple(extended_program))
    return variants


def generate_candidate_programs(
    base_programs: Sequence[Sequence[GPPrimitive]],
    *,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    beats_per_measure: int,
    manual_transposition: int,
    preferred_register_shift: int | None,
    auto_range_factory: Callable[
        ..., tuple[tuple[GPPrimitive, ...], ...]
    ] = _default_auto_range_programs,
) -> tuple[list[tuple[GPPrimitive, ...]], tuple[tuple[GPPrimitive, ...], ...]]:
    """Expand the supplied program list with prefixes, variants, and auto options."""

    candidate_programs: list[tuple[GPPrimitive, ...]] = [tuple(program) for program in base_programs]
    program_keys: set[tuple[GPPrimitive, ...]] = set(candidate_programs)

    for program in list(candidate_programs):
        if len(program) <= 1:
            continue
        for index in range(1, len(program)):
            _add_program(candidate_programs, program[:index], program_keys)

    for variant in _extend_local_octave_variants(candidate_programs, phrase):
        _add_program(candidate_programs, variant, program_keys)

    auto_programs: tuple[tuple[GPPrimitive, ...], ...] = ()
    if manual_transposition == 0:
        auto_programs = auto_range_factory(
            phrase,
            instrument,
            beats_per_measure=beats_per_measure,
            preferred_shift=preferred_register_shift,
        )

    for program in auto_programs:
        _add_program(candidate_programs, program, program_keys)

    return candidate_programs, auto_programs


__all__ = ["generate_candidate_programs"]

