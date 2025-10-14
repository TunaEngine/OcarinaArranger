from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from shared.ottava import OttavaShift

from .phrase import PhraseNote, PhraseSpan
from .soft_key import InstrumentRange


@dataclass(frozen=True)
class FoldingSettings:
    """Weights and penalties for octave folding with slack."""

    shift_penalty: float = 0.5
    substitution_penalty: float = 3.0
    out_of_range_weight: float = 2.5
    leap_threshold: int = 5
    leap_penalty: float = 0.2
    pitch_deviation_weight: float = 0.02
    shift_transition_penalty: float = 0.4
    substitution_interval_limit: int = 2

    def __post_init__(self) -> None:
        if self.substitution_interval_limit < 0:
            raise ValueError("substitution_interval_limit must be non-negative")
        numeric_fields = (
            self.shift_penalty,
            self.substitution_penalty,
            self.out_of_range_weight,
            self.leap_threshold,
            self.leap_penalty,
            self.pitch_deviation_weight,
            self.shift_transition_penalty,
        )
        if any(value < 0 for value in numeric_fields):
            raise ValueError("folding penalties must be non-negative")


@dataclass(frozen=True)
class FoldingStep:
    index: int
    original_midi: int
    midi: int
    shift: int
    substituted: bool
    register_penalty: float
    substitution_penalty: float
    transition_penalty: float


@dataclass(frozen=True)
class FoldingResult:
    span: PhraseSpan
    total_cost: float
    steps: Tuple[FoldingStep, ...]


@dataclass(frozen=True)
class _CandidateOption:
    midi: int
    shift: int
    substituted: bool
    substitution_delta: int = 0


@dataclass(frozen=True)
class _DPCell:
    cost: float
    prev_option: _CandidateOption | None
    transition_penalty: float
    register_penalty: float
    substitution_penalty: float


def _generate_options(note: PhraseNote, settings: FoldingSettings) -> Tuple[_CandidateOption, ...]:
    options: set[_CandidateOption] = set()
    for shift in (-1, 0, 1):
        base_midi = note.midi + (12 * shift)
        options.add(_CandidateOption(base_midi, shift, False, 0))
        if settings.substitution_interval_limit <= 0:
            continue
        for delta in range(-settings.substitution_interval_limit, settings.substitution_interval_limit + 1):
            if delta == 0:
                continue
            options.add(_CandidateOption(base_midi + delta, shift, True, delta))
    sorted_options = sorted(options, key=lambda option: (option.shift, option.midi, option.substitution_delta))
    return tuple(sorted_options)


def _register_penalty(midi: int, instrument: InstrumentRange, settings: FoldingSettings) -> float:
    if midi < instrument.min_midi:
        return (instrument.min_midi - midi) * settings.out_of_range_weight
    if midi > instrument.max_midi:
        return (midi - instrument.max_midi) * settings.out_of_range_weight
    return 0.0


def _state_cost(note: PhraseNote, option: _CandidateOption, instrument: InstrumentRange, settings: FoldingSettings) -> tuple[float, float, float]:
    register_pen = _register_penalty(option.midi, instrument, settings)
    substitution_pen = settings.substitution_penalty if option.substituted else 0.0
    deviation_pen = abs(option.midi - note.midi) * settings.pitch_deviation_weight
    shift_pen = abs(option.shift) * settings.shift_penalty
    total = register_pen + substitution_pen + deviation_pen + shift_pen
    return total, register_pen, substitution_pen


def _transition_penalty(prev: _CandidateOption, current: _CandidateOption, settings: FoldingSettings) -> float:
    penalty = 0.0
    if prev.shift != current.shift:
        penalty += abs(prev.shift - current.shift) * settings.shift_transition_penalty
    interval = abs(current.midi - prev.midi)
    if interval > settings.leap_threshold:
        penalty += (interval - settings.leap_threshold) * settings.leap_penalty
    return penalty


def fold_octaves_with_slack(
    span: PhraseSpan,
    instrument: InstrumentRange,
    *,
    settings: FoldingSettings | None = None,
) -> FoldingResult:
    """Fold phrase octaves using DP while allowing finite penalties for slack."""

    active_settings = settings or FoldingSettings()
    notes = span.notes
    if not notes:
        return FoldingResult(span, 0.0, ())

    option_grid = [_generate_options(note, active_settings) for note in notes]
    dp_table: list[dict[_CandidateOption, _DPCell]] = []

    for index, (note, options) in enumerate(zip(notes, option_grid)):
        row: dict[_CandidateOption, _DPCell] = {}
        for option in options:
            state_cost, register_pen, substitution_pen = _state_cost(note, option, instrument, active_settings)
            if index == 0:
                row[option] = _DPCell(state_cost, None, 0.0, register_pen, substitution_pen)
                continue

            best_cost: float | None = None
            best_prev: _CandidateOption | None = None
            best_transition = 0.0
            prev_row = dp_table[index - 1]
            for prev_option, prev_cell in prev_row.items():
                transition_pen = _transition_penalty(prev_option, option, active_settings)
                total_cost = prev_cell.cost + transition_pen + state_cost
                if best_cost is None or total_cost < best_cost:
                    best_cost = total_cost
                    best_prev = prev_option
                    best_transition = transition_pen
            if best_prev is None or best_cost is None:
                continue
            row[option] = _DPCell(best_cost, best_prev, best_transition, register_pen, substitution_pen)
        if not row:
            # If we cannot find any transitions, fall back to keeping the original note.
            fallback_option = _CandidateOption(notes[index].midi, 0, False, 0)
            state_cost, register_pen, substitution_pen = _state_cost(notes[index], fallback_option, instrument, active_settings)
            row[fallback_option] = _DPCell(state_cost, None, 0.0, register_pen, substitution_pen)
        dp_table.append(row)

    final_row = dp_table[-1]
    best_option, best_cell = min(final_row.items(), key=lambda item: item[1].cost)

    new_notes = list(notes)
    steps: list[FoldingStep] = []
    option: _CandidateOption | None = best_option
    index = len(notes) - 1

    while option is not None and index >= 0:
        cell = dp_table[index][option]
        note = notes[index]
        updated = note.with_midi(option.midi)
        if option.shift != 0:
            direction = "up" if option.shift > 0 else "down"
            shift_size = 8 * abs(option.shift)
            updated = updated.add_ottava_shift(
                OttavaShift(source="octave-shift", direction=direction, size=shift_size)
            )
        if option.substituted:
            updated = updated.with_tags(note.tags.union({"substituted"}))
        new_notes[index] = updated
        steps.append(
            FoldingStep(
                index=index,
                original_midi=note.midi,
                midi=option.midi,
                shift=option.shift,
                substituted=option.substituted,
                register_penalty=cell.register_penalty,
                substitution_penalty=cell.substitution_penalty,
                transition_penalty=cell.transition_penalty,
            )
        )
        option = cell.prev_option
        index -= 1

    steps.reverse()
    result_span = span.with_notes(new_notes)
    return FoldingResult(result_span, best_cell.cost, tuple(steps))


__all__ = [
    "FoldingResult",
    "FoldingSettings",
    "FoldingStep",
    "fold_octaves_with_slack",
]
