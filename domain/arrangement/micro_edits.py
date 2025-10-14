from __future__ import annotations

from typing import Sequence

from shared.ottava import OttavaShift

from .phrase import PhraseSpan


def drop_ornamental_eighth(span: PhraseSpan) -> PhraseSpan:
    notes = list(span.notes)
    eighth = span.eighth_duration()
    for index, note in enumerate(notes):
        if "ornamental" not in note.tags:
            continue
        if note.duration > eighth:
            continue
        removed_duration = note.duration
        new_notes = notes[:index] + notes[index + 1 :]
        if not new_notes:
            return span
        if index > 0:
            prev = new_notes[index - 1]
            new_notes[index - 1] = prev.with_duration(prev.duration + removed_duration)
        else:
            new_notes = [n.with_onset(n.onset - removed_duration) for n in new_notes]
        return span.with_notes(new_notes)
    return span


def lengthen_pivotal_note(span: PhraseSpan) -> PhraseSpan:
    notes = list(span.notes)
    for index, note in enumerate(notes):
        if "pivotal" not in note.tags:
            continue
        note_end = note.onset + note.duration
        if index + 1 < len(notes):
            next_onset = notes[index + 1].onset
        else:
            next_onset = span.total_duration
        slack = max(0, next_onset - note_end)
        if slack <= 0:
            continue
        new_notes = notes.copy()
        new_notes[index] = note.with_duration(note.duration + slack)
        return span.with_notes(new_notes)
    return span


def shift_short_phrase_octave(span: PhraseSpan, direction: str = "down") -> PhraseSpan:
    if direction not in {"up", "down"}:
        raise ValueError("direction must be 'up' or 'down'")
    semitone = 12 if direction == "up" else -12
    max_span = span.pulses_per_quarter * 2

    notes = list(span.notes)

    def _apply(indices: Sequence[int]) -> PhraseSpan:
        updated = notes.copy()
        shift = OttavaShift(source="micro-edit", direction=direction, size=8)
        for idx in indices:
            updated[idx] = updated[idx].with_midi(updated[idx].midi + semitone).add_ottava_shift(shift)
        return span.with_notes(updated)

    sequences: list[list[int]] = []
    current: list[int] = []
    for idx, note in enumerate(notes):
        if "octave-shiftable" in note.tags:
            current.append(idx)
            continue
        if current:
            sequences.append(current)
            current = []
    if current:
        sequences.append(current)

    best: tuple[int, ...] | None = None
    for seq in sequences:
        trimmed = list(seq)
        while trimmed and (
            notes[trimmed[-1]].onset + notes[trimmed[-1]].duration - notes[trimmed[0]].onset
        ) > max_span:
            trimmed.pop(0)
        if not trimmed:
            continue
        candidate = tuple(trimmed)
        if best is None:
            best = candidate
            continue
        best_end = notes[best[-1]].midi
        candidate_end = notes[candidate[-1]].midi
        if candidate_end > best_end or (
            candidate_end == best_end
            and notes[candidate[0]].onset > notes[best[0]].onset
        ):
            best = candidate

    if best is None:
        return span

    return _apply(best)


__all__ = [
    "drop_ornamental_eighth",
    "lengthen_pivotal_note",
    "shift_short_phrase_octave",
]
