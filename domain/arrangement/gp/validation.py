"""Validation helpers for arrangement GP programs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, MutableMapping, Sequence

from domain.arrangement.phrase import PhraseSpan

from .ops import GPPrimitive, SpanDescriptor


class ProgramValidationError(ValueError):
    """Base error for malformed GP programs."""

    def __init__(self, message: str, *, operation: GPPrimitive | None = None) -> None:
        super().__init__(message)
        self.operation = operation


class ParameterValidationError(ProgramValidationError):
    """Raised when a parameter falls outside its declared domain."""

    def __init__(
        self,
        parameter: str,
        value: object,
        domain: object,
        *,
        operation: GPPrimitive,
    ) -> None:
        describe = getattr(domain, "describe", None)
        expected = describe() if callable(describe) else str(domain)
        message = (
            f"Parameter '{parameter}' has invalid value {value!r}; expected {expected}"
        )
        super().__init__(message, operation=operation)
        self.parameter = parameter
        self.value = value
        self.domain = domain


class SpanResolutionError(ProgramValidationError):
    """Raised when a span descriptor cannot be resolved inside the phrase."""

    def __init__(self, descriptor: SpanDescriptor, *, operation: GPPrimitive) -> None:
        super().__init__("Operation span is outside the phrase bounds", operation=operation)
        self.descriptor = descriptor


class SpanLimitError(ProgramValidationError):
    """Raised when an operation exceeds the configured per-span cap."""

    def __init__(
        self,
        descriptor: SpanDescriptor,
        limit: int,
        *,
        operation: GPPrimitive,
    ) -> None:
        message = f"Exceeded limit of {limit} operations for span label '{descriptor.label}'"
        super().__init__(message, operation=operation)
        self.descriptor = descriptor
        self.limit = limit


class ProgramLengthError(ProgramValidationError):
    """Raised when a program exceeds the total operation cap."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"Program exceeds maximum of {limit} operations")
        self.limit = limit


class WindowLimitError(ProgramValidationError):
    """Raised when edits exceed the per-window cap."""

    def __init__(
        self,
        *,
        window_index: int,
        limit: int,
        window_bars: int,
        beats_per_measure: int,
        operation: GPPrimitive,
    ) -> None:
        bar_start = window_index * window_bars + 1
        bar_end = bar_start + window_bars - 1
        message = (
            f"Exceeded limit of {limit} operations within bars {bar_start}-{bar_end}"
        )
        super().__init__(message, operation=operation)
        self.window_index = window_index
        self.limit = limit
        self.window_bars = window_bars
        self.beats_per_measure = beats_per_measure


@dataclass(frozen=True)
class ProgramConstraints:
    """Declarative caps applied during GP program validation."""

    max_operations: int | None = 12
    span_limits: Mapping[str, int] | None = None
    max_operations_per_window: int | None = None
    window_bars: int = 8
    beats_per_measure: int = 4


def merge_constraints(
    constraints: ProgramConstraints | None,
    span_limits: Mapping[str, int] | None = None,
) -> ProgramConstraints:
    """Combine explicit span limits with the provided constraint set."""

    base = constraints or ProgramConstraints()
    if span_limits:
        combined = dict(base.span_limits or {})
        combined.update(span_limits)
        base = replace(base, span_limits=combined)
    return base


def validate_program(
    program: Sequence[GPPrimitive],
    phrase: PhraseSpan,
    *,
    span_limits: Mapping[str, int] | None = None,
    constraints: ProgramConstraints | None = None,
) -> None:
    """Ensure that a GP program is safe to execute against *phrase*.

    Args:
        program: Sequence of primitives to validate.
        phrase: The phrase the program will be applied to.
        span_limits: Optional mapping from span labels to maximum number of
            operations that may target the same concrete span. Deprecated in
            favour of ``constraints`` but still supported for compatibility.
        constraints: Declarative caps that apply during validation.

    Raises:
        ProgramValidationError: if validation fails.
    """

    applied = merge_constraints(constraints, span_limits)
    span_limits = applied.span_limits or {}
    span_counts: MutableMapping[tuple[str, tuple[int, int]], int] = {}
    window_counts: MutableMapping[int, int] = {}

    if applied.max_operations is not None and len(program) > applied.max_operations:
        raise ProgramLengthError(applied.max_operations)

    pulses_per_bar = max(1, phrase.pulses_per_quarter * applied.beats_per_measure)
    window_size = pulses_per_bar * max(1, applied.window_bars)

    for operation in program:
        for name, domain in operation.parameter_domains().items():
            value = getattr(operation, name)
            if not domain.contains(value):
                raise ParameterValidationError(
                    name, value, domain, operation=operation
                )

        try:
            resolved = operation.span.resolve(phrase)
        except ValueError as exc:  # pragma: no cover - intentionally surfaced
            raise SpanResolutionError(operation.span, operation=operation) from exc

        limit = span_limits.get(operation.span.label)
        if limit is not None:
            key = (operation.span.label, resolved)
            count = span_counts.get(key, 0) + 1
            span_counts[key] = count
            if count > limit:
                raise SpanLimitError(operation.span, limit, operation=operation)

        window_limit = applied.max_operations_per_window
        if window_limit is not None and window_size > 0:
            start, end = resolved
            if end <= start:
                continue
            first_window = start // window_size
            last_window = (end - 1) // window_size
            for window_index in range(first_window, last_window + 1):
                window_count = window_counts.get(window_index, 0) + 1
                window_counts[window_index] = window_count
                if window_count > window_limit:
                    raise WindowLimitError(
                        window_index=window_index,
                        limit=window_limit,
                        window_bars=applied.window_bars,
                        beats_per_measure=applied.beats_per_measure,
                        operation=operation,
                    )
