"""Shared dataclasses for GP arrangement strategy results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, TYPE_CHECKING

from domain.arrangement.difficulty import DifficultySummary
from domain.arrangement.explanations import ExplanationEvent
from domain.arrangement.phrase import PhraseSpan
from domain.arrangement.soft_key import InstrumentRange

from .fitness import FitnessVector
from .ops import GPPrimitive
from .session import GPSessionResult
from .session_logging import IndividualSummary

if TYPE_CHECKING:
    from domain.arrangement.api import ArrangementStrategyResult


@dataclass(frozen=True)
class GPInstrumentCandidate:
    """Arrangement outcome for a single instrument using a GP program."""

    instrument_id: str
    instrument: InstrumentRange
    program: Tuple[GPPrimitive, ...]
    span: PhraseSpan
    difficulty: DifficultySummary
    fitness: FitnessVector
    melody_penalty: float
    melody_shift_penalty: float
    explanations: Tuple[ExplanationEvent, ...] = ()


@dataclass(frozen=True)
class GPArrangementStrategyResult:
    """Return value capturing GP session data and ranked instrument outcomes."""

    session: GPSessionResult
    programs: Tuple[Tuple[GPPrimitive, ...], ...]
    chosen: GPInstrumentCandidate
    comparisons: Tuple[GPInstrumentCandidate, ...]
    archive_summary: Tuple[IndividualSummary, ...]
    termination_reason: str
    fallback: "ArrangementStrategyResult | None" = None


__all__ = [
    "GPArrangementStrategyResult",
    "GPInstrumentCandidate",
]
