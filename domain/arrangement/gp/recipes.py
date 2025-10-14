"""Curated program recipes for GP seeding.

The recipes are intentionally simple: they encode the most common repair
actions we observe in the v2 arranger pipeline so that the genetic
programme starts with musically sensible candidates.
"""

from __future__ import annotations

from typing import Callable, Sequence, Tuple

from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor

Recipe = Callable[[PhraseSpan, InstrumentRange], Sequence[GPPrimitive]]


def _entire_span_descriptor(span: PhraseSpan) -> SpanDescriptor:
    end = span.total_duration or 0
    return SpanDescriptor(start_onset=span.first_onset, end_onset=end)


def _global_center_recipe(span: PhraseSpan, instrument: InstrumentRange) -> Sequence[GPPrimitive]:
    if not span.notes:
        return ()

    lowest = min(note.midi for note in span.notes)
    highest = max(note.midi for note in span.notes)
    min_shift = instrument.min_midi - lowest
    max_shift = instrument.max_midi - highest
    if min_shift > max_shift:
        return ()

    comfort = instrument.comfort_center or (instrument.min_midi + instrument.max_midi) / 2.0
    average = sum(note.midi for note in span.notes) / len(span.notes)
    shift = int(round(comfort - average))
    shift = max(min_shift, min(max_shift, shift))
    shift = max(-12, min(12, shift))
    if shift == 0:
        return ()
    return (GlobalTranspose(semitones=shift),)


def _octave_correction_recipe(span: PhraseSpan, instrument: InstrumentRange) -> Sequence[GPPrimitive]:
    if not span.notes:
        return ()

    descriptor = _entire_span_descriptor(span)
    lowest = min(note.midi for note in span.notes)
    highest = max(note.midi for note in span.notes)

    if highest > instrument.max_midi:
        excess = highest - instrument.max_midi
        octaves = -max(1, min(2, (excess + 11) // 12))
        return (LocalOctave(span=descriptor, octaves=octaves),)

    if lowest < instrument.min_midi:
        deficit = instrument.min_midi - lowest
        octaves = max(1, min(2, (deficit + 11) // 12))
        return (LocalOctave(span=descriptor, octaves=octaves),)

    return ()


def _simplify_density_recipe(span: PhraseSpan, instrument: InstrumentRange) -> Sequence[GPPrimitive]:
    del instrument  # Instrument range does not affect rhythmic simplification.
    if not span.notes:
        return ()

    eighth = span.eighth_duration()
    short_notes = sum(1 for note in span.notes if note.duration <= eighth)
    if short_notes < max(1, len(span.notes) // 2):
        return ()

    descriptor = _entire_span_descriptor(span)
    return (SimplifyRhythm(span=descriptor, subdivisions=2),)


_RECIPES: Tuple[Recipe, ...] = (
    _global_center_recipe,
    _octave_correction_recipe,
    _simplify_density_recipe,
)


def curated_recipes(span: PhraseSpan, instrument: InstrumentRange) -> Tuple[Tuple[GPPrimitive, ...], ...]:
    """Return a tuple of curated program candidates for ``span``.

    Each recipe returns a sequence of primitives; empty recipes are filtered
    out to avoid cluttering the initial population with no-op programs.
    """

    programs: list[Tuple[GPPrimitive, ...]] = []
    for recipe in _RECIPES:
        program = tuple(recipe(span, instrument))
        if not program:
            continue
        if program not in programs:
            programs.append(program)
    return tuple(programs)


__all__ = ["curated_recipes"]

