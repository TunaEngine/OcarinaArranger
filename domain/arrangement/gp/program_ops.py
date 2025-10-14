"""Helpers for applying GP programs to musical phrases."""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Sequence

from shared.ottava import OttavaShift

from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm


def apply_program(program: Sequence[GPPrimitive], span: PhraseSpan) -> PhraseSpan:
    """Apply each primitive in *program* to *span* sequentially."""

    current = span
    for operation in program:
        current = apply_primitive(operation, current)
    return current


def apply_primitive(operation: GPPrimitive, span: PhraseSpan) -> PhraseSpan:
    """Apply a single GP primitive to *span*."""

    if isinstance(operation, GlobalTranspose):
        return span.transpose(operation.semitones)
    if isinstance(operation, LocalOctave):
        return _apply_local_octave(operation, span)
    if isinstance(operation, SimplifyRhythm):
        return _apply_simplify_rhythm(operation, span)
    return span


def _apply_local_octave(operation: LocalOctave, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    if operation.octaves == 0:
        return span

    semitones = operation.octaves * 12
    direction = "up" if semitones > 0 else "down"
    shift = OttavaShift(
        source="octave-shift",
        direction=direction,
        size=8 * abs(operation.octaves),
    )

    updated: list[PhraseNote] = []
    for note in span.notes:
        if start <= note.onset < end:
            updated.append(note.with_midi(note.midi + semitones).add_ottava_shift(shift))
            continue
        updated.append(note)
    return span.with_notes(updated)


def _apply_simplify_rhythm(operation: SimplifyRhythm, span: PhraseSpan) -> PhraseSpan:
    try:
        start, end = operation.span.resolve(span)
    except ValueError:
        return span

    subdivisions = max(1, int(operation.subdivisions))
    unit = max(1, span.pulses_per_quarter // subdivisions)
    updated: list[PhraseNote] = []

    for note in span.notes:
        if not (start <= note.onset < end):
            updated.append(note)
            continue

        quantized = max(unit, round(note.duration / unit) * unit)
        max_duration = max(1, end - note.onset)
        updated_duration = min(quantized, max_duration)
        updated.append(note.with_duration(updated_duration))

    return span.with_notes(updated)


def primitive_sampler(
    rng,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    span_limits: Mapping[str, int] | None,
) -> Callable[[], GPPrimitive]:
    """Return a callable that samples valid primitives for mutation."""

    from .init import generate_random_program  # Imported lazily to avoid cycles.

    def _generator() -> GPPrimitive:
        attempts = 0
        while True:
            attempts += 1
            try:
                program = generate_random_program(
                    phrase,
                    instrument,
                    rng=rng,
                    max_length=1,
                    span_limits=span_limits,
                )
            except RuntimeError:
                program = []
            if program:
                return program[0]
            if attempts >= 5:
                raise RuntimeError("Unable to generate primitive for mutation")

    return _generator


def ensure_population(
    programs: Iterable[Sequence[GPPrimitive]],
    *,
    required: int,
    phrase: PhraseSpan,
    instrument: InstrumentRange,
    rng,
    span_limits: Mapping[str, int] | None,
) -> list[list[GPPrimitive]]:
    """Ensure the GP population has at least *required* unique programs."""

    from .init import generate_random_program  # Imported lazily to avoid cycles.

    pool = [list(program) for program in programs][:required]
    seen = {tuple(program) for program in pool}

    attempts = 0
    max_attempts = max(10, required * 5)
    while len(pool) < required and attempts < max_attempts:
        attempts += 1
        try:
            candidate = generate_random_program(
                phrase,
                instrument,
                rng=rng,
                max_length=3,
                span_limits=span_limits,
            )
        except RuntimeError:
            continue

        key = tuple(candidate)
        if not candidate or key in seen:
            continue
        pool.append(candidate)
        seen.add(key)

    if len(pool) < required:
        raise RuntimeError("Unable to seed initial GP population with the requested size")

    return pool


__all__ = [
    "apply_primitive",
    "apply_program",
    "ensure_population",
    "primitive_sampler",
]

