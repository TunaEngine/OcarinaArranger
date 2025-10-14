"""Helpers for repairing GP programs before execution."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, MutableMapping, Sequence

from domain.arrangement.phrase import PhraseSpan

from .ops import GPPrimitive, GlobalTranspose, LocalOctave, RangeDomain, SimplifyRhythm
from .validation import ProgramConstraints, merge_constraints


def repair_program(
    program: Sequence[GPPrimitive],
    phrase: PhraseSpan,
    *,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
) -> list[GPPrimitive]:
    """Return a sanitized copy of *program* safe for execution.

    The helper trims spans to the score bounds, merges compatible primitives and
    drops edits that cannot be brought back within their declared parameter
    domains.
    """

    applied = merge_constraints(constraints, span_limits)
    span_limits = applied.span_limits or {}
    span_counts: MutableMapping[tuple[str, tuple[int, int]], int] = {}
    window_counts: MutableMapping[int, int] = {}
    repaired: list[GPPrimitive] = []
    limit_records: list[tuple[tuple[str, tuple[int, int]] | None, tuple[int, ...]]] = []

    pulses_per_bar = max(1, phrase.pulses_per_quarter * applied.beats_per_measure)
    window_size = pulses_per_bar * max(1, applied.window_bars)

    for operation in program:
        trimmed = operation.span.clamp(phrase)
        if trimmed is None:
            continue

        operation = replace(operation, span=trimmed)

        # All parameters must still be within their domains.
        if not all(
            domain.contains(getattr(operation, name))
            for name, domain in operation.parameter_domains().items()
        ):
            continue

        if applied.max_operations is not None and len(repaired) >= applied.max_operations:
            break

        resolved = trimmed.resolve(phrase)
        limit = span_limits.get(trimmed.label)
        span_key: tuple[str, tuple[int, int]] | None = None
        if limit is not None:
            span_key = (trimmed.label, resolved)
            count = span_counts.get(span_key, 0)
            if count >= limit:
                continue

        window_limit = applied.max_operations_per_window
        windows_to_update: list[int] = []
        if window_limit is not None and window_size > 0:
            start, end = resolved
            if end > start:
                first_window = start // window_size
                last_window = (end - 1) // window_size
                candidate_windows = list(range(first_window, last_window + 1))
                if any(window_counts.get(window_index, 0) >= window_limit for window_index in candidate_windows):
                    continue
                windows_to_update = candidate_windows

        if repaired and type(repaired[-1]) is type(operation) and repaired[-1].span == trimmed:
            merged = _merge_operations(repaired[-1], operation)
            if merged is None:
                repaired.pop()
                span_key_removed, windows_removed = limit_records.pop()
                if span_key_removed is not None:
                    count = span_counts.get(span_key_removed, 0) - 1
                    if count > 0:
                        span_counts[span_key_removed] = count
                    elif span_key_removed in span_counts:
                        del span_counts[span_key_removed]
                for window_index in windows_removed:
                    window_count = window_counts.get(window_index, 0) - 1
                    if window_count > 0:
                        window_counts[window_index] = window_count
                    elif window_index in window_counts:
                        del window_counts[window_index]
                continue
            repaired[-1] = merged
            continue

        repaired.append(operation)
        limit_records.append((span_key, tuple(windows_to_update)))
        if span_key is not None:
            span_counts[span_key] = span_counts.get(span_key, 0) + 1
        for window_index in windows_to_update:
            window_counts[window_index] = window_counts.get(window_index, 0) + 1

    return repaired


def _merge_operations(first: GPPrimitive, second: GPPrimitive) -> GPPrimitive | None:
    if isinstance(first, GlobalTranspose) and isinstance(second, GlobalTranspose):
        domain = first.parameter_domains()["semitones"]
        assert isinstance(domain, RangeDomain)
        combined = first.semitones + second.semitones
        combined = domain.clamp(combined)
        return replace(first, semitones=combined)

    if isinstance(first, LocalOctave) and isinstance(second, LocalOctave):
        domain = first.parameter_domains()["octaves"]
        assert isinstance(domain, RangeDomain)
        combined = first.octaves + second.octaves
        combined = domain.clamp(combined)
        if combined == 0:
            return None
        return replace(first, octaves=combined)

    if isinstance(first, SimplifyRhythm) and isinstance(second, SimplifyRhythm):
        domain = first.parameter_domains()["subdivisions"]
        assert isinstance(domain, RangeDomain)
        combined = min(first.subdivisions, second.subdivisions)
        combined = domain.clamp(combined)
        return replace(first, subdivisions=combined)

    return second
