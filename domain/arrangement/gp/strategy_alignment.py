"""Helpers for aligning GP candidates across instruments and octaves."""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .ops import GPPrimitive, GlobalTranspose, LocalOctave
from .strategy_scoring import _top_voice_notes
from .strategy_types import GPInstrumentCandidate


def _targets_full_span(operation: GPPrimitive, phrase: PhraseSpan) -> bool:
    """Return ``True`` when ``operation`` covers the entire phrase span."""

    descriptor = getattr(operation, "span", None)
    if descriptor is None or not hasattr(descriptor, "resolve"):
        return False
    try:
        start, end = descriptor.resolve(phrase)
    except ValueError:
        return False
    return start == 0 and end == phrase.total_duration


def _uniform_octave_shift(
    program: Tuple[GPPrimitive, ...], phrase: PhraseSpan
) -> int | None:
    """Return the uniform octave shift in semitones when applicable."""

    if not program:
        return None
    if all(isinstance(operation, GlobalTranspose) for operation in program):
        total_shift = 0
        for operation in program:
            semitones = getattr(operation, "semitones", 0)
            try:
                shift_value = int(semitones)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return None
            if shift_value % 12 != 0:
                return None
            if not _targets_full_span(operation, phrase):
                return None
            total_shift += shift_value
        return total_shift or None
    if len(program) == 1 and isinstance(program[0], LocalOctave):
        try:
            octaves = int(program[0].octaves)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None
        if octaves == 0:
            return None
        if not _targets_full_span(program[0], phrase):
            return None
        return octaves * 12
    return None


def _align_uniform_octave_span(
    candidate_span: PhraseSpan,
    *,
    reference_span: PhraseSpan,
    instrument: InstrumentRange,
    uniform_shift: int | None,
) -> PhraseSpan:
    """Align uniformly shifted spans toward a consistent octave offset."""

    if not candidate_span.notes or not reference_span.notes:
        return candidate_span
    if uniform_shift is None:
        return candidate_span

    original_top: Dict[int, int] = {}
    for note in reference_span.notes:
        current = original_top.get(note.onset)
        if current is None or note.midi > current:
            original_top[note.onset] = note.midi

    candidate_notes = list(candidate_span.notes)
    top_indices: Dict[int, int] = {}
    for index, note in enumerate(candidate_notes):
        existing = top_indices.get(note.onset)
        if existing is None or note.midi >= candidate_notes[existing].midi:
            top_indices[note.onset] = index

    changed = False
    for onset, index in top_indices.items():
        original_midi = original_top.get(onset)
        if original_midi is None:
            continue
        desired = original_midi + uniform_shift
        options: List[Tuple[float, float, float, int, int]] = []
        comfort_center = getattr(instrument, "comfort_center", None)
        for octave_delta in range(-4, 5):
            candidate_midi = int(desired + octave_delta * 12)
            if instrument.min_midi <= candidate_midi <= instrument.max_midi:
                distance = abs(candidate_midi - desired)
                if comfort_center is None:
                    comfort_metric = 0.0
                else:
                    comfort_metric = abs(candidate_midi - comfort_center)
                original_distance = abs(candidate_midi - original_midi)
                options.append(
                    (
                        comfort_metric,
                        distance,
                        original_distance,
                        abs(octave_delta),
                        candidate_midi,
                    )
                )
        if not options:
            continue
        if uniform_shift > 0:
            non_descending = [option for option in options if option[4] >= original_midi]
            if non_descending:
                options = non_descending
        elif uniform_shift < 0:
            non_ascending = [option for option in options if option[4] <= original_midi]
            if non_ascending:
                options = non_ascending
        if uniform_shift > 0:
            options.sort(key=lambda item: (item[0], item[2], item[1], item[3], item[4]))
        elif uniform_shift < 0:
            options.sort(key=lambda item: (item[1], item[2], item[0], item[3], item[4]))
        else:
            options.sort(key=lambda item: (item[2], item[0], item[1], item[3], item[4]))
        best_midi = options[0][4]
        if best_midi != candidate_notes[index].midi:
            candidate_notes[index] = candidate_notes[index].with_midi(best_midi)
            changed = True

    if not changed:
        return candidate_span

    return candidate_span.with_notes(tuple(candidate_notes))


def _align_top_voice_to_baseline(
    candidate_span: PhraseSpan,
    *,
    baseline_top_voice: Sequence[PhraseNote],
    instrument: InstrumentRange,
    expected_offset: int,
) -> PhraseSpan:
    """Align *candidate_span*'s top voice toward ``baseline_top_voice`` plus an offset."""

    if not candidate_span.notes or not baseline_top_voice:
        return candidate_span

    baseline_targets: Dict[int, int] = {
        note.onset: note.midi + expected_offset for note in baseline_top_voice
    }
    candidate_notes = list(candidate_span.notes)
    top_indices: Dict[int, int] = {}
    for index, note in enumerate(candidate_notes):
        existing = top_indices.get(note.onset)
        if existing is None or note.midi >= candidate_notes[existing].midi:
            top_indices[note.onset] = index

    if not top_indices:
        return candidate_span

    comfort_center = getattr(instrument, "comfort_center", None)
    changed = False
    for onset, index in top_indices.items():
        desired = baseline_targets.get(onset)
        if desired is None:
            continue
        current = candidate_notes[index]
        options: List[Tuple[int, float, float, int, int]] = []
        for octave_delta in range(-4, 5):
            candidate_midi = int(desired + octave_delta * 12)
            if not (instrument.min_midi <= candidate_midi <= instrument.max_midi):
                continue
            pitch_class_mismatch = 0 if (candidate_midi - desired) % 12 == 0 else 1
            distance = abs(candidate_midi - desired)
            comfort_metric = (
                abs(candidate_midi - comfort_center)
                if comfort_center is not None
                else 0.0
            )
            original_distance = abs(candidate_midi - current.midi)
            options.append(
                (
                    pitch_class_mismatch,
                    distance,
                    comfort_metric,
                    original_distance,
                    candidate_midi,
                )
            )
        if not options:
            continue
        options.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
        best_midi = options[0][4]
        if best_midi != current.midi:
            candidate_notes[index] = current.with_midi(best_midi)
            changed = True

    if not changed:
        return candidate_span

    return candidate_span.with_notes(tuple(candidate_notes))


def _align_top_voice_to_target(
    candidate: GPInstrumentCandidate,
    *,
    target: GPInstrumentCandidate,
    instrument: InstrumentRange,
    phrase: PhraseSpan,
    beats_per_measure: int,
    fitness_config,
) -> GPInstrumentCandidate:
    """Return ``target``'s span when the winner drifts from the ranked best."""

    if not candidate.span.notes or not target.span.notes:
        return candidate

    candidate_top = _top_voice_notes(candidate.span)
    target_top = _top_voice_notes(target.span)
    if len(candidate_top) == len(target_top) and all(
        cand.midi == tgt.midi for cand, tgt in zip(candidate_top, target_top)
    ):
        return candidate

    merged_explanations = tuple(
        dict.fromkeys(candidate.explanations + target.explanations)
    ) or candidate.explanations or target.explanations

    return GPInstrumentCandidate(
        instrument_id=candidate.instrument_id,
        instrument=instrument,
        program=candidate.program,
        span=target.span,
        difficulty=target.difficulty,
        fitness=target.fitness,
        melody_penalty=target.melody_penalty,
        melody_shift_penalty=target.melody_shift_penalty,
        explanations=merged_explanations,
    )


__all__ = [
    "_targets_full_span",
    "_uniform_octave_shift",
    "_align_uniform_octave_span",
    "_align_top_voice_to_baseline",
    "_align_top_voice_to_target",
]
