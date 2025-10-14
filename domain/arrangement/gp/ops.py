"""Definitions for arrangement genetic programming primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Protocol, Tuple, Union

from domain.arrangement.phrase import PhraseSpan


class ParameterDomain(Protocol):
    """Simple protocol for parameter domains."""

    def contains(self, value: Any) -> bool:
        """Return ``True`` if *value* is valid for this domain."""

    def clamp(self, value: Any) -> Any:
        """Return the closest admissible value within the domain."""

    def describe(self) -> str:
        """Human friendly description of the domain bounds."""


@dataclass(frozen=True)
class RangeDomain(ParameterDomain):
    """Inclusive integer range with an optional step constraint."""

    minimum: int
    maximum: int
    step: int = 1

    def contains(self, value: Any) -> bool:
        if not isinstance(value, int):
            return False
        if value < self.minimum or value > self.maximum:
            return False
        return (value - self.minimum) % self.step == 0

    def clamp(self, value: Any) -> int:
        if not isinstance(value, int):
            raise TypeError("RangeDomain only clamps integers")
        coerced = min(max(value, self.minimum), self.maximum)
        offset = (coerced - self.minimum) % self.step
        return coerced - offset

    def describe(self) -> str:
        step_desc = "" if self.step == 1 else f" (step {self.step})"
        return f"[{self.minimum}, {self.maximum}]{step_desc}"


@dataclass(frozen=True)
class ChoiceDomain(ParameterDomain):
    """Finite set of admissible values."""

    choices: Tuple[Any, ...]

    def contains(self, value: Any) -> bool:
        return value in self.choices

    def clamp(self, value: Any) -> Any:
        if not self.choices:
            raise ValueError("ChoiceDomain must contain at least one option")
        if value in self.choices:
            return value
        return self.choices[0]

    def describe(self) -> str:
        return ", ".join(repr(choice) for choice in self.choices)


@dataclass(frozen=True)
class SpanDescriptor:
    """Metadata describing which portion of a ``PhraseSpan`` an operation targets."""

    start_onset: int | None = None
    end_onset: int | None = None
    label: str = "phrase"

    def resolve(self, span: PhraseSpan) -> tuple[int, int]:
        """Resolve to concrete ``(start, end)`` bounds within *span*.

        Raises:
            ValueError: if the descriptor targets an empty or invalid region.
        """

        total_duration = span.total_duration
        start = 0 if self.start_onset is None else int(self.start_onset)
        end = total_duration if self.end_onset is None else int(self.end_onset)

        if start < 0 or end < 0:
            raise ValueError("Span positions must be non-negative")
        if start >= end:
            raise ValueError("Span descriptor must produce a positive-length region")
        if start > total_duration or end > total_duration:
            raise ValueError("Span descriptor extends beyond the phrase bounds")
        return (start, end)

    def clamp(self, span: PhraseSpan) -> SpanDescriptor | None:
        """Return a descriptor trimmed to *span*'s bounds, or ``None`` if empty."""

        total_duration = span.total_duration
        if total_duration <= 0:
            return None
        start = 0 if self.start_onset is None else int(self.start_onset)
        end = total_duration if self.end_onset is None else int(self.end_onset)

        start = max(0, min(start, total_duration))
        end = max(start, min(end, total_duration))
        if start >= end:
            return None
        return SpanDescriptor(start_onset=start, end_onset=end, label=self.label)


class PrimitiveBase:
    """Mix-in that surfaces domain metadata for parameter validation."""

    PARAMETER_DOMAINS: ClassVar[Mapping[str, ParameterDomain]]
    ACTION: ClassVar[str] = "gp-operation"
    REASON_CODE: ClassVar[str] = "gp-operation"

    @classmethod
    def parameter_domains(cls) -> Mapping[str, ParameterDomain]:
        return cls.PARAMETER_DOMAINS

    def parameter_values(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.PARAMETER_DOMAINS}

    def action_name(self) -> str:
        """Return the telemetry action label for the primitive."""

        return type(self).ACTION

    def reason_code(self) -> str:
        """Return the canonical reason code exposed through explanations."""

        return type(self).REASON_CODE


def _entire_span() -> SpanDescriptor:
    return SpanDescriptor()


@dataclass(frozen=True)
class GlobalTranspose(PrimitiveBase):
    """Shift the entire phrase up or down by a number of semitones."""

    semitones: int
    span: SpanDescriptor = field(default_factory=_entire_span)

    ACTION: ClassVar[str] = "GP_GLOBAL_TRANSPOSE"
    REASON_CODE: ClassVar[str] = "global-transpose"
    PARAMETER_DOMAINS: ClassVar[Mapping[str, ParameterDomain]] = {
        "semitones": RangeDomain(-12, 12),
    }


@dataclass(frozen=True)
class LocalOctave(PrimitiveBase):
    """Shift a contiguous region by whole octaves."""

    span: SpanDescriptor
    octaves: int

    ACTION: ClassVar[str] = "GP_LOCAL_OCTAVE"
    REASON_CODE: ClassVar[str] = "range-edge"
    PARAMETER_DOMAINS: ClassVar[Mapping[str, ParameterDomain]] = {
        "octaves": RangeDomain(-2, 2),
    }


@dataclass(frozen=True)
class SimplifyRhythm(PrimitiveBase):
    """Simplify rhythmic density inside a region by forcing subdivisions."""

    span: SpanDescriptor
    subdivisions: int

    ACTION: ClassVar[str] = "GP_SIMPLIFY_RHYTHM"
    REASON_CODE: ClassVar[str] = "rhythm-simplify"
    PARAMETER_DOMAINS: ClassVar[Mapping[str, ParameterDomain]] = {
        "subdivisions": RangeDomain(1, 4),
    }


GPPrimitive = Union[GlobalTranspose, LocalOctave, SimplifyRhythm]

__all__ = [
    "ChoiceDomain",
    "GPPrimitive",
    "GlobalTranspose",
    "LocalOctave",
    "ParameterDomain",
    "RangeDomain",
    "SimplifyRhythm",
    "SpanDescriptor",
]
