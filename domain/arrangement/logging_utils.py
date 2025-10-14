"""Helper formatting routines for arranger debug logging."""

from __future__ import annotations

from typing import Sequence

from ocarina_tools import midi_to_name

from .difficulty import DifficultySummary, difficulty_score
from .melody import MelodyIsolationAction
from .phrase import PhraseSpan
from .soft_key import InstrumentRange


def _format_midi(midi: int) -> str:
    """Return a friendly representation for *midi* including its note name."""

    name = midi_to_name(midi)
    return f"{name}({midi})"


def describe_span(span: PhraseSpan) -> str:
    """Summarise ``span`` for debug logging."""

    count = len(span.notes)
    duration = span.total_duration
    if count == 0:
        return (
            f"notes=0 duration={duration}ppq pulses_per_quarter={span.pulses_per_quarter}"
        )

    lowest = min(note.midi for note in span.notes)
    highest = max(note.midi for note in span.notes)
    return (
        "notes="
        f"{count} range={_format_midi(lowest)}..{_format_midi(highest)} "
        f"duration={duration}ppq pulses_per_quarter={span.pulses_per_quarter}"
    )


def describe_instrument(instrument: InstrumentRange) -> str:
    """Summarise ``instrument`` bounds for debug logging."""

    comfort = instrument.comfort_center
    comfort_text = f", comfort≈{comfort:.2f}" if comfort is not None else ""
    return (
        f"range={_format_midi(instrument.min_midi)}..{_format_midi(instrument.max_midi)}"
        f"{comfort_text}"
    )


def describe_difficulty(summary: DifficultySummary) -> str:
    """Summarise ``DifficultySummary`` metrics."""

    score = difficulty_score(summary)
    return (
        "difficulty="
        f"score={score:.3f} hvh={summary.hard_and_very_hard:.3f} "
        f"med={summary.medium:.3f} tess={summary.tessitura_distance:.3f}"
    )


def describe_melody_actions(
    actions: Sequence[MelodyIsolationAction],
    *,
    limit: int = 5,
) -> str:
    """Provide a compact representation of melody isolation steps."""

    total = len(actions)
    if total == 0:
        return "actions=0"

    preview = []
    for action in list(actions)[:limit]:
        preview.append(
            f"m{action.measure}:{action.action}:{action.reason}:keep={action.kept_voice}"  # noqa: E501
        )

    if total > limit:
        preview.append(f"…(+{total - limit} more)")

    return f"actions={total}[{'; '.join(preview)}]"


__all__ = [
    "describe_span",
    "describe_instrument",
    "describe_difficulty",
    "describe_melody_actions",
]
