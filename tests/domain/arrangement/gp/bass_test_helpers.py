"""Shared helpers for bass arrangement regression tests."""

from __future__ import annotations

from typing import Dict, List

from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.gp.strategy import GPInstrumentCandidate

MELODY_MIDIS: List[int] = [52, 55, 57, 60, 62, 64, 62, 60, 59, 57]


def top_voice(candidate: GPInstrumentCandidate) -> List[int]:
    grouped: Dict[int, List[int]] = {}
    for note in candidate.span.notes:
        grouped.setdefault(note.onset, []).append(note.midi)
    return [max(grouped[onset]) for onset in sorted(grouped)]


def assert_constant_offset(
    primary_candidate: GPInstrumentCandidate,
    secondary_candidate: GPInstrumentCandidate,
    melody_length: int,
    expected_offset: int,
) -> None:
    primary_top = top_voice(primary_candidate)
    secondary_top = top_voice(secondary_candidate)
    assert len(primary_top) >= melody_length
    assert len(secondary_top) >= melody_length
    primary_segment = primary_top[-melody_length:]
    secondary_segment = secondary_top[-melody_length:]
    assert len(primary_segment) == len(secondary_segment) == melody_length
    offsets = [
        secondary - primary
        for primary, secondary in zip(primary_segment, secondary_segment)
    ]
    assert offsets
    unique_offsets = set(offsets)
    spread = max(unique_offsets) - min(unique_offsets)
    assert spread <= expected_offset + 2
    allowed_delta = expected_offset + 2
    assert all(abs(offset - expected_offset) <= allowed_delta for offset in unique_offsets)


def bass_session(winner: Individual, config) -> GPSessionResult:
    return GPSessionResult(
        winner=winner,
        log=GPSessionLog(seed=config.random_seed, config={}),
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )


__all__ = [
    "MELODY_MIDIS",
    "assert_constant_offset",
    "bass_session",
    "top_voice",
]
