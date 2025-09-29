"""Utilities for describing rhythmic note values from MIDI tick durations."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple


@dataclass(frozen=True)
class NoteValueDescription:
    """Human friendly representation of a note duration."""

    label: str
    fraction: str

    def long_text(self) -> str:
        """Return an expanded description such as ``"Quarter note (1/4)"``."""

        base = self.label.strip()
        if base and self.fraction:
            return f"{base} note ({self.fraction})"
        if base:
            return f"{base} note"
        return self.fraction

    def short_text(self) -> str:
        """Return a compact representation (e.g. ``"Quarter (1/4)"``)."""

        base = self.label.strip()
        if base and self.fraction:
            return f"{base} ({self.fraction})"
        return base or self.fraction

    def compact_text(self) -> str:
        """Return the most condensed label, preferring the fractional form."""

        return self.fraction or self.label.strip()


_KNOWN_VALUES: Tuple[Tuple[float, str], ...] = (
    (4.0, "Whole"),
    (3.0, "Dotted half"),
    (2.0, "Half"),
    (1.5, "Dotted quarter"),
    (1.0, "Quarter"),
    (0.75, "Dotted eighth"),
    (0.5, "Eighth"),
    (0.375, "Dotted sixteenth"),
    (0.25, "Sixteenth"),
    (0.1875, "Dotted thirty-second"),
    (0.125, "Thirty-second"),
    (0.09375, "Dotted sixty-fourth"),
    (0.0625, "Sixty-fourth"),
)


@dataclass(frozen=True)
class NoteGlyphDescription:
    """Details about how a note head should be drawn on a staff."""

    base: str
    dots: int = 0

    def requires_stem(self) -> bool:
        return self.base not in {"whole"}


_BASE_NOTE_VALUES: Tuple[Tuple[str, Fraction], ...] = (
    ("whole", Fraction(1, 1)),
    ("half", Fraction(1, 2)),
    ("quarter", Fraction(1, 4)),
    ("eighth", Fraction(1, 8)),
    ("sixteenth", Fraction(1, 16)),
    ("thirty-second", Fraction(1, 32)),
    ("sixty-fourth", Fraction(1, 64)),
)


def _dot_factor(dots: int) -> Fraction:
    total = Fraction(0, 1)
    for index in range(dots + 1):
        total += Fraction(1, 2**index)
    return total


def describe_note_value(duration_ticks: int, pulses_per_quarter: int) -> NoteValueDescription:
    """Return a :class:`NoteValueDescription` for the given duration."""

    if duration_ticks <= 0:
        return NoteValueDescription(label="Rest", fraction="")
    if pulses_per_quarter <= 0:
        ticks = max(0, int(duration_ticks))
        suffix = "tick" if ticks == 1 else "ticks"
        return NoteValueDescription(label=f"{ticks} {suffix}", fraction=str(ticks))

    beats = duration_ticks / pulses_per_quarter
    tolerance = 0.02
    for value, label in _KNOWN_VALUES:
        if abs(beats - value) <= tolerance:
            fraction = _fraction_of_whole(duration_ticks, pulses_per_quarter)
            return NoteValueDescription(label=label, fraction=fraction)

    beats_fraction = Fraction(duration_ticks, pulses_per_quarter).limit_denominator(32)
    label = _format_beats(beats_fraction)
    fraction = _fraction_of_whole(duration_ticks, pulses_per_quarter)
    return NoteValueDescription(label=label, fraction=fraction)


def describe_note_glyph(
    duration_ticks: int, pulses_per_quarter: int
) -> Optional[NoteGlyphDescription]:
    """Return how a staff note of the given duration should be drawn."""

    if duration_ticks <= 0 or pulses_per_quarter <= 0:
        return None

    whole_fraction = Fraction(
        duration_ticks, max(1, pulses_per_quarter) * 4
    ).limit_denominator(128)
    tolerance = Fraction(1, 192)
    best: Optional[tuple[Fraction, NoteGlyphDescription]] = None

    for base, base_fraction in _BASE_NOTE_VALUES:
        for dots in range(0, 3):
            value = base_fraction * _dot_factor(dots)
            diff = abs(value - whole_fraction)
            glyph = NoteGlyphDescription(base=base, dots=dots)
            if diff <= tolerance:
                return glyph
            if best is None or diff < best[0]:
                best = (diff, glyph)

    if best is not None:
        return best[1]
    return None


def _fraction_of_whole(duration_ticks: int, pulses_per_quarter: int) -> str:
    whole_fraction = Fraction(duration_ticks, max(1, pulses_per_quarter) * 4).limit_denominator(64)
    if whole_fraction.numerator == 0:
        return ""
    if whole_fraction.denominator == 1:
        return str(whole_fraction.numerator)
    return f"{whole_fraction.numerator}/{whole_fraction.denominator}"


def _format_beats(fraction: Fraction) -> str:
    numerator, denominator = fraction.numerator, fraction.denominator
    if denominator == 1:
        count = numerator
        suffix = "beat" if count == 1 else "beats"
        return f"{count} {suffix}"

    if numerator > denominator:
        whole = numerator // denominator
        remainder = Fraction(numerator % denominator, denominator)
        if remainder.numerator == 0:
            return f"{whole} beats"
        return f"{whole} {remainder.numerator}/{remainder.denominator} beats"

    suffix = "beat" if numerator == 1 else "beats"
    return f"{numerator}/{denominator} {suffix}"


__all__ = [
    "NoteGlyphDescription",
    "NoteValueDescription",
    "describe_note_glyph",
    "describe_note_value",
]
