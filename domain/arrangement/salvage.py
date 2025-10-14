from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, MutableMapping, Sequence, Tuple, Union

from .explanations import ExplanationEvent
from .micro_edits import drop_ornamental_eighth, lengthen_pivotal_note, shift_short_phrase_octave
from .phrase import PhraseSpan


DifficultyFn = Callable[[PhraseSpan], float]
TransformFn = Callable[[PhraseSpan], PhraseSpan]
ExplainFn = Callable[[PhraseSpan, PhraseSpan, float, float], str]
ExplainType = Union[str, ExplainFn, None]


@dataclass(frozen=True)
class SalvageStep:
    name: str
    transform: TransformFn
    explain: ExplainType = None
    budget_key: Union[str, None] = None

    def describe(
        self,
        before: PhraseSpan,
        after: PhraseSpan,
        before_difficulty: float,
        after_difficulty: float,
    ) -> str:
        if callable(self.explain):
            return self.explain(before, after, before_difficulty, after_difficulty)
        if isinstance(self.explain, str):
            return self.explain
        return self.name


@dataclass(frozen=True)
class SalvageResult:
    span: PhraseSpan
    difficulty: float
    applied_steps: Tuple[str, ...]
    success: bool
    explanations: Tuple[ExplanationEvent, ...]
    starting_difficulty: float
    edits_used: Mapping[str, int]

    @property
    def difficulty_delta(self) -> float:
        return self.starting_difficulty - self.difficulty


class SalvageCascade:
    """Apply salvage transformations until the span meets the difficulty threshold."""

    def __init__(
        self,
        *,
        threshold: float,
        steps: Sequence[SalvageStep],
        epsilon: float = 1e-6,
        beats_per_measure: int = 4,
        budgets: SalvageBudgets | None = None,
    ) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        if beats_per_measure <= 0:
            raise ValueError("beats_per_measure must be positive")
        self._threshold = float(threshold)
        self._steps = tuple(steps)
        self._epsilon = float(epsilon)
        self._beats_per_measure = int(beats_per_measure)
        self._budgets = budgets or SalvageBudgets()

    def run(self, span: PhraseSpan, difficulty_fn: DifficultyFn) -> SalvageResult:
        current = span
        difficulty = float(difficulty_fn(current))
        starting_difficulty = difficulty
        applied: list[str] = []
        explanations: list[ExplanationEvent] = []
        usage: MutableMapping[str, int] = {}
        total_steps_used = 0

        def _increment_usage(key: str) -> None:
            usage[key] = usage.get(key, 0) + 1

        for step in self._steps:
            if difficulty <= self._threshold:
                break

            if total_steps_used >= self._budgets.max_steps_per_span:
                break

            if step.budget_key:
                limit = self._budgets.limit_for(step.budget_key)
                if limit is not None and usage.get(step.budget_key, 0) >= limit:
                    continue

            candidate = step.transform(current)
            if candidate == current:
                continue

            candidate_difficulty = float(difficulty_fn(candidate))
            if (difficulty - candidate_difficulty) > self._epsilon or candidate_difficulty <= self._threshold:
                reason = step.describe(current, candidate, difficulty, candidate_difficulty)
                explanations.append(
                    ExplanationEvent.from_step(
                        action=step.name,
                        reason=reason,
                        before=current,
                        after=candidate,
                        difficulty_before=difficulty,
                        difficulty_after=candidate_difficulty,
                        beats_per_measure=self._beats_per_measure,
                    )
                )
                current = candidate
                difficulty = candidate_difficulty
                applied.append(step.name)
                total_steps_used += 1
                if step.budget_key:
                    _increment_usage(step.budget_key)

        success = difficulty <= self._threshold
        if not success:
            reason = (
                f"Span remains above difficulty threshold "
                f"({difficulty:.2f} > {self._threshold:.2f})."
            )
            explanations.append(
                ExplanationEvent.from_step(
                    action="not-recommended",
                    reason=reason,
                    before=current,
                    after=current,
                    difficulty_before=difficulty,
                    difficulty_after=difficulty,
                    beats_per_measure=self._beats_per_measure,
                    reason_code="not-recommended",
                )
            )
            applied.append("not-recommended")

        usage_with_total: dict[str, int] = dict(usage)
        usage_with_total["total"] = total_steps_used
        return SalvageResult(
            span=current,
            difficulty=difficulty,
            applied_steps=tuple(applied),
            success=success,
            explanations=tuple(explanations),
            starting_difficulty=starting_difficulty,
            edits_used=MappingProxyType(usage_with_total),
        )

    @property
    def beats_per_measure(self) -> int:
        return self._beats_per_measure


@dataclass(frozen=True)
class SalvageBudgets:
    max_octave_edits: int = 1
    max_rhythm_edits: int = 1
    max_substitutions: int = 1
    max_steps_per_span: int = 3

    def limit_for(self, key: str) -> Union[int, None]:
        mapping = {
            "octave": self.max_octave_edits,
            "rhythm": self.max_rhythm_edits,
            "substitution": self.max_substitutions,
        }
        return mapping.get(key)


def default_salvage_cascade(
    threshold: float = 0.9,
    *,
    budgets: SalvageBudgets | None = None,
) -> SalvageCascade:
    steps = (
        SalvageStep(
            "OCTAVE_DOWN_LOCAL",
            lambda span: shift_short_phrase_octave(span, direction="down"),
            explain="Shifted phrase down an octave to reduce register load",
            budget_key="octave",
        ),
        SalvageStep(
            "rhythm-simplify",
            drop_ornamental_eighth,
            explain="Dropped ornamental notes to ease speed constraints",
            budget_key="rhythm",
        ),
        SalvageStep(
            "lengthen-pivotal",
            lengthen_pivotal_note,
            explain="Lengthened pivotal tone for clearer phrasing",
            budget_key="substitution",
        ),
    )
    return SalvageCascade(threshold=threshold, steps=steps, budgets=budgets)


__all__ = [
    "ExplanationEvent",
    "SalvageBudgets",
    "SalvageCascade",
    "SalvageResult",
    "SalvageStep",
    "default_salvage_cascade",
]
