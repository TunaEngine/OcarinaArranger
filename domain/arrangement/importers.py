from __future__ import annotations

from typing import Iterable

from ocarina_tools.events import NoteEvent

from .phrase import PhraseNote, PhraseSpan


def phrase_from_note_events(events: Iterable[NoteEvent], pulses_per_quarter: int) -> PhraseSpan:
    notes = [
        PhraseNote(
            onset=event.onset,
            duration=event.duration,
            midi=event.midi,
            ottava_shifts=event.ottava_shifts,
        )
        for event in events
    ]
    span = PhraseSpan(tuple(notes), pulses_per_quarter=pulses_per_quarter)
    if not span.notes:
        return span

    eighth = span.eighth_duration()
    max_duration = max(note.duration for note in span.notes)
    highest_midi = max(note.midi for note in span.notes)

    annotated = []
    multiple_notes = len(span.notes) > 1
    for note in span.notes:
        tags: set[str] = set(note.tags)
        if multiple_notes and note.duration <= eighth:
            tags.add("ornamental")
        if note.duration == max_duration:
            tags.add("pivotal")
        if note.midi >= highest_midi - 2:
            tags.add("octave-shiftable")
        annotated.append(note.with_tags(tags))

    return span.with_notes(annotated)


def note_events_from_phrase(span: PhraseSpan, *, program: int) -> tuple[NoteEvent, ...]:
    """Convert ``span`` back into :class:`~ocarina_tools.events.NoteEvent` values."""

    return tuple(
        NoteEvent(
            onset=note.onset,
            duration=note.duration,
            midi=note.midi,
            program=program,
            ottava_shifts=note.ottava_shifts,
        )
        for note in span.notes
    )


__all__ = ["phrase_from_note_events", "note_events_from_phrase"]
