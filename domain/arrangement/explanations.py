from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Optional, Sequence, Tuple

from .phrase import PhraseNote, PhraseSpan


def _normalize_reason_code(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return normalized or "unspecified"


def _default_span_id(span: PhraseSpan) -> str:
    return f"span-{span.first_onset}-{span.total_duration}"


@dataclass(frozen=True)
class ExplanationEvent:
    schema_version: int
    bar: int
    action: str
    reason: str
    reason_code: str
    before: PhraseSpan
    after: PhraseSpan
    difficulty_delta: float
    span_id: str
    key_id: Optional[str]
    span: Optional[str] = None

    @classmethod
    def from_step(
        cls,
        *,
        schema_version: int = 1,
        action: str,
        reason: str,
        before: PhraseSpan,
        after: PhraseSpan,
        difficulty_before: float,
        difficulty_after: float,
        beats_per_measure: int = 4,
        reason_code: Optional[str] = None,
        span_id: Optional[str] = None,
        key_id: Optional[str] = None,
        span_label: Optional[str] = None,
    ) -> "ExplanationEvent":
        if beats_per_measure <= 0:
            raise ValueError("beats_per_measure must be positive")

        delta = difficulty_before - difficulty_after
        bar = before.bar_number(beats_per_measure=beats_per_measure)
        normalized_reason = reason.strip()
        derived_reason_code = _normalize_reason_code(
            (reason_code or normalized_reason or action).strip()
        )
        return cls(
            schema_version=int(schema_version),
            bar=bar,
            action=action,
            reason=normalized_reason,
            reason_code=derived_reason_code,
            before=before,
            after=after,
            difficulty_delta=round(delta, 6),
            span_id=span_id or _default_span_id(before),
            key_id=key_id,
            span=span_label,
        )

    def to_payload(self) -> Mapping[str, object]:
        return {
            "schema_version": self.schema_version,
            "bar": self.bar,
            "action": self.action,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "difficulty_delta": self.difficulty_delta,
            "before_note_count": len(self.before.notes),
            "after_note_count": len(self.after.notes),
            "span_id": self.span_id,
            "key_id": self.key_id,
            "span": self.span,
        }


def span_label_for_notes(
    notes: Sequence["PhraseNote"],
    *,
    pulses_per_quarter: int,
    beats_per_measure: int,
) -> str | None:
    if not notes:
        return None
    pulses_per_measure = max(1, pulses_per_quarter * max(1, beats_per_measure))
    start_onset = min(note.onset for note in notes)
    end_onset = max(note.onset + note.duration for note in notes)
    measure_start = (start_onset // pulses_per_measure) * pulses_per_measure
    start_beat = int((start_onset - measure_start) / max(1, pulses_per_quarter)) + 1
    end_beat = int((max(end_onset - 1, start_onset) - measure_start) / max(1, pulses_per_quarter)) + 1
    if start_beat == end_beat:
        return f"beat {start_beat}"
    return f"beats {start_beat}-{end_beat}"


def octave_shifted_notes(
    before: PhraseSpan, after: PhraseSpan
) -> Tuple["PhraseNote", ...]:
    after_map: dict[tuple[int, int], list["PhraseNote"]] = {}
    for note in after.notes:
        after_map.setdefault((note.onset, note.duration), []).append(note)

    shifted: list["PhraseNote"] = []
    for note in before.notes:
        key = (note.onset, note.duration)
        candidates = after_map.get(key)
        if not candidates:
            continue
        match_index = None
        for idx, candidate in enumerate(candidates):
            if note.midi - candidate.midi == 12:
                match_index = idx
                break
        if match_index is None:
            continue
        candidates.pop(match_index)
        shifted.append(note)
    return tuple(shifted)


__all__ = ["ExplanationEvent", "octave_shifted_notes", "span_label_for_notes"]
