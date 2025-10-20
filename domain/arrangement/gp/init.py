"""Initial population helpers for arrangement genetic programming."""

from __future__ import annotations

import math
import random
from typing import Iterable, Mapping, MutableMapping, Sequence

from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, SimplifyRhythm, SpanDescriptor
from .penalties import ScoringPenalties
from .recipes import curated_recipes
from .validation import ProgramValidationError, validate_program


def translate_salvage_trace(
    events: Sequence[ExplanationEvent],
    *,
    span: PhraseSpan,
    transposition: int = 0,
    span_limits: Mapping[str, int] | None = None,
    penalties: ScoringPenalties | None = None,
) -> list[GPPrimitive]:
    """Translate arranger v2 salvage events into GP primitives."""

    penalties = penalties or ScoringPenalties()
    allow_fidelity = penalties.allow_fidelity_edits()
    allow_simplify = allow_fidelity and penalties.allow_rhythm_simplify()
    allow_local = allow_fidelity and penalties.allow_melody_shift()

    program: list[GPPrimitive] = []
    if transposition:
        program.append(GlobalTranspose(semitones=int(transposition)))

    for event in events:
        primitive = None
        action = event.action.lower()
        reason_code = event.reason_code.lower()

        if allow_local and ("octave" in action or "range-edge" in reason_code):
            primitive = _translate_octave_event(event)
        elif allow_simplify and (
            "rhythm" in action or "rhythm" in reason_code or "ornamental" in reason_code
        ):
            primitive = _translate_rhythm_event(event)

        if primitive is None:
            continue
        program.append(primitive)

    if not program:
        return []

    if _program_is_valid(program, span, span_limits):
        return program

    filtered: list[GPPrimitive] = []
    for primitive in program:
        candidate = filtered + [primitive]
        if _program_is_valid(candidate, span, span_limits):
            filtered.append(primitive)
    return filtered


def seed_programs(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    salvage_events: Sequence[ExplanationEvent] | None = None,
    transposition: int = 0,
    random_count: int = 3,
    rng: random.Random | None = None,
    span_limits: Mapping[str, int] | None = None,
    penalties: ScoringPenalties | None = None,
) -> list[list[GPPrimitive]]:
    """Build an initial pool of GP programs from salvage data and heuristics."""

    penalties = penalties or ScoringPenalties()
    allow_fidelity = penalties.allow_fidelity_edits()
    allow_simplify = allow_fidelity and penalties.allow_rhythm_simplify()
    allow_local = allow_fidelity and penalties.allow_melody_shift()

    rng = rng or random.Random()
    programs: list[list[GPPrimitive]] = []
    seen: set[tuple[GPPrimitive, ...]] = set()

    def _try_add(candidate: Sequence[GPPrimitive]) -> None:
        key = tuple(candidate)
        if not key:
            return
        if key in seen:
            return
        if not _program_is_valid(candidate, span, span_limits):
            return
        if not allow_local and any(
            isinstance(operation, LocalOctave) for operation in candidate
        ):
            return
        if not allow_simplify and any(
            isinstance(operation, SimplifyRhythm) for operation in candidate
        ):
            return
        programs.append(list(candidate))
        seen.add(key)

    salvage_events = salvage_events or ()
    salvage_program = translate_salvage_trace(
        salvage_events,
        span=span,
        transposition=transposition,
        span_limits=span_limits,
        penalties=penalties,
    )
    _try_add(salvage_program)

    for recipe in curated_recipes(span, instrument, penalties=penalties):
        _try_add(recipe)

    for _ in range(max(0, random_count)):
        try:
            random_program = generate_random_program(
                span,
                instrument,
                rng=rng,
                max_length=3,
                span_limits=span_limits,
                penalties=penalties,
            )
        except RuntimeError:
            continue
        _try_add(random_program)

    return programs


def generate_random_program(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    rng: random.Random | None = None,
    max_length: int = 3,
    span_limits: Mapping[str, int] | None = None,
    max_attempts: int = 50,
    penalties: ScoringPenalties | None = None,
) -> list[GPPrimitive]:
    """Construct a short random program that passes validation."""

    penalties = penalties or ScoringPenalties()
    allow_fidelity = penalties.allow_fidelity_edits()
    allow_simplify = allow_fidelity and penalties.allow_rhythm_simplify()
    allow_local = allow_fidelity and penalties.allow_melody_shift()

    rng = rng or random.Random()
    if not span.notes:
        return []

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        length = max(1, min(max_length, rng.randint(1, max_length)))
        program: list[GPPrimitive] = []
        while len(program) < length:
            primitive = _random_primitive(
                span,
                instrument,
                rng,
                program,
                allow_simplify=allow_simplify,
                allow_local=allow_local,
            )
            if primitive is None:
                break
            program.append(primitive)

        if not program:
            continue

        if _program_is_valid(program, span, span_limits):
            return program

    raise RuntimeError("Unable to generate a valid GP program within the attempt budget")


def _program_is_valid(
    program: Sequence[GPPrimitive],
    span: PhraseSpan,
    span_limits: Mapping[str, int] | None,
) -> bool:
    try:
        validate_program(program, span, span_limits=span_limits or {})
    except ProgramValidationError:
        return False
    return True


def _translate_octave_event(event: ExplanationEvent) -> LocalOctave | None:
    matches = _match_shifted_notes(event.before, event.after)
    if not matches:
        return None

    start = min(before.onset for before, _ in matches)
    end = max(before.onset + before.duration for before, _ in matches)
    label = event.span or "phrase"
    descriptor = SpanDescriptor(start_onset=start, end_onset=end, label=label)

    deltas = {
        (after.midi - before.midi) // 12
        for before, after in matches
        if after.midi != before.midi and (after.midi - before.midi) % 12 == 0
    }
    deltas.discard(0)
    if not deltas:
        if "down" in event.action.lower():
            deltas.add(-1)
        elif "up" in event.action.lower():
            deltas.add(1)

    if len(deltas) != 1:
        return None

    return LocalOctave(span=descriptor, octaves=deltas.pop())


def _translate_rhythm_event(event: ExplanationEvent) -> SimplifyRhythm | None:
    if not event.after.notes:
        return None

    start = min(note.onset for note in event.after.notes)
    end = max(note.onset + note.duration for note in event.after.notes)
    label = event.span or "phrase"
    descriptor = SpanDescriptor(start_onset=start, end_onset=end, label=label)

    reason = event.reason.lower()
    if "triplet" in reason:
        subdivisions = 3
    elif "sixteenth" in reason:
        subdivisions = 4
    else:
        subdivisions = 2

    return SimplifyRhythm(span=descriptor, subdivisions=subdivisions)


def _match_shifted_notes(
    before: PhraseSpan, after: PhraseSpan
) -> list[tuple[PhraseNote, PhraseNote]]:
    after_map: MutableMapping[tuple[int, int], list[PhraseNote]] = {}
    for note in after.notes:
        after_map.setdefault((note.onset, note.duration), []).append(note)

    matches: list[tuple[PhraseNote, PhraseNote]] = []
    for note in before.notes:
        key = (note.onset, note.duration)
        candidates = after_map.get(key)
        if not candidates:
            continue
        index = None
        for idx, candidate in enumerate(candidates):
            diff = candidate.midi - note.midi
            if diff % 12 == 0:
                index = idx
                break
        if index is None:
            continue
        candidate = candidates.pop(index)
        matches.append((note, candidate))
    return matches


def _random_primitive(
    span: PhraseSpan,
    instrument: InstrumentRange,
    rng: random.Random,
    current: Sequence[GPPrimitive],
    *,
    allow_simplify: bool,
    allow_local: bool,
) -> GPPrimitive | None:
    choices: list[str] = []
    if allow_local:
        choices.append("local")
    if allow_simplify:
        choices.append("rhythm")
    if not any(isinstance(op, GlobalTranspose) for op in current):
        if _global_transpose_candidates(span, instrument):
            choices.append("global")
    else:
        # Still consider a global transpose when it is the only available option.
        if not choices and _global_transpose_candidates(span, instrument):
            choices.append("global")

    if not choices:
        return None

    kind = rng.choice(choices)
    if kind == "global":
        semitone = rng.choice(_global_transpose_candidates(span, instrument))
        return GlobalTranspose(semitones=semitone)

    descriptor = _random_span_descriptor(span, rng)
    if descriptor is None:
        return None

    if kind == "local":
        return _random_local_octave(descriptor, span, instrument, current, rng)

    return SimplifyRhythm(span=descriptor, subdivisions=rng.choice([2, 3, 4]))


def _global_transpose_candidates(
    span: PhraseSpan, instrument: InstrumentRange
) -> list[int]:
    if not span.notes:
        return [0]

    lowest = min(note.midi for note in span.notes)
    highest = max(note.midi for note in span.notes)
    min_shift = max(-12, instrument.min_midi - lowest)
    max_shift = min(12, instrument.max_midi - highest)
    candidates = [shift for shift in range(min_shift, max_shift + 1) if shift != 0]
    return candidates or [0]


def _random_span_descriptor(span: PhraseSpan, rng: random.Random) -> SpanDescriptor | None:
    total = span.total_duration
    if total <= 0:
        return None

    onsets = sorted({note.onset for note in span.notes} | {0})
    ends = sorted({note.onset + note.duration for note in span.notes} | {total})

    start = rng.choice(onsets)
    valid_ends = [end for end in ends if end > start]
    if not valid_ends:
        return None
    end = rng.choice(valid_ends)
    return SpanDescriptor(start_onset=start, end_onset=end, label="phrase")


def _random_local_octave(
    descriptor: SpanDescriptor,
    span: PhraseSpan,
    instrument: InstrumentRange,
    current: Sequence[GPPrimitive],
    rng: random.Random,
) -> LocalOctave | None:
    try:
        start, end = descriptor.resolve(span)
    except ValueError:
        return None

    notes = [note for note in span.notes if start <= note.onset < end]
    if not notes:
        return None

    global_shift = sum(
        op.semitones for op in current if isinstance(op, GlobalTranspose)
    )
    lowest = min(note.midi for note in notes) + global_shift
    highest = max(note.midi for note in notes) + global_shift

    min_octaves = math.ceil((instrument.min_midi - lowest) / 12)
    max_octaves = math.floor((instrument.max_midi - highest) / 12)
    min_octaves = max(min_octaves, -2)
    max_octaves = min(max_octaves, 2)

    options = [octave for octave in range(min_octaves, max_octaves + 1) if octave != 0]
    if not options:
        return None

    return LocalOctave(span=descriptor, octaves=rng.choice(options))


__all__ = [
    "generate_random_program",
    "seed_programs",
    "translate_salvage_trace",
]

