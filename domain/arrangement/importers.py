from __future__ import annotations

from typing import Iterable

from ocarina_tools.events import NoteEvent

from .phrase import PhraseNote, PhraseSpan


def phrase_from_note_events(events: Iterable[NoteEvent], pulses_per_quarter: int) -> PhraseSpan:
    normalized_notes: list[PhraseNote] = []
    for event in events:
        onset = max(0, int(event.onset))
        duration = max(1, int(event.duration))
        base = PhraseNote(
            onset=onset,
            duration=duration,
            midi=event.midi,
            ottava_shifts=event.ottava_shifts,
        )
        base_tags: set[str] = set(base.tags)
        if event.is_grace:
            base_tags.update({"grace", "ornamental"})
            if event.grace_type:
                base_tags.add(f"grace-type:{event.grace_type}")
        base = base.with_tags(base_tags)
        normalized_notes.append(base)

    notes = normalized_notes
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
            is_grace="grace" in note.tags,
            grace_type=_extract_grace_type(note.tags),
        )
        for note in span.notes
    )


__all__ = ["phrase_from_note_events", "note_events_from_phrase"]


def _extract_grace_type(tags: frozenset[str]) -> str | None:
    for tag in tags:
        if tag.startswith("grace-type:"):
            value = tag.split(":", 1)[1].strip()
            if value:
                return value
    return None
