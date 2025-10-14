from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol, Tuple

from .phrase import PhraseSpan


@dataclass(frozen=True)
class ArrangementProposal:
    original: PhraseSpan
    proposal: PhraseSpan
    applied_steps: Tuple[str, ...]
    difficulty_before: float
    difficulty_after: float

    @property
    def difficulty_delta(self) -> float:
        return self.difficulty_before - self.difficulty_after


@dataclass(frozen=True)
class ApprovalRecord:
    proposal: ArrangementProposal
    approved_at: datetime
    metadata: Mapping[str, object]


class ApprovalStore(Protocol):
    def save(self, record: ApprovalRecord) -> None:  # pragma: no cover - protocol definition
        ...


class ApprovalLogger:
    """Persist user approvals for later arranger tuning."""

    def __init__(self, store: ApprovalStore) -> None:
        self._store = store

    def log_approval(
        self,
        proposal: ArrangementProposal,
        *,
        metadata: Mapping[str, object] | None = None,
        approved_at: datetime | None = None,
    ) -> ApprovalRecord:
        record_metadata = MappingProxyType(dict(metadata or {}))
        timestamp = approved_at or datetime.now(timezone.utc)
        record = ApprovalRecord(proposal=proposal, approved_at=timestamp, metadata=record_metadata)
        self._store.save(record)
        return record


@dataclass(frozen=True)
class EvaluationReport:
    approval_count: int
    step_overlap: float
    difficulty_delta_gap: float
    matched_steps: Tuple[str, ...]
    missing_steps: Tuple[str, ...]


class ArrangementEvaluator:
    """Compare candidate arrangements against historical approvals."""

    def __init__(self, approvals: Iterable[ApprovalRecord]) -> None:
        records = tuple(approvals)
        self._approvals = records
        self._approval_count = len(records)
        self._step_counts = Counter(step for record in records for step in record.proposal.applied_steps)
        if records:
            average = sum(record.proposal.difficulty_delta for record in records) / len(records)
        else:
            average = 0.0
        self._average_delta = average

    def evaluate(self, proposal: ArrangementProposal) -> EvaluationReport:
        steps = tuple(proposal.applied_steps)
        if steps:
            matched = tuple(step for step in steps if self._step_counts.get(step, 0) > 0)
            missing = tuple(step for step in steps if self._step_counts.get(step, 0) == 0)
            overlap = len(matched) / len(steps)
        else:
            matched = ()
            missing = ()
            overlap = 0.0

        if self._approval_count:
            delta_gap = proposal.difficulty_delta - self._average_delta
        else:
            delta_gap = proposal.difficulty_delta

        return EvaluationReport(
            approval_count=self._approval_count,
            step_overlap=overlap,
            difficulty_delta_gap=delta_gap,
            matched_steps=matched,
            missing_steps=missing,
        )


__all__ = [
    "ApprovalLogger",
    "ApprovalRecord",
    "ApprovalStore",
    "ArrangementProposal",
    "ArrangementEvaluator",
    "EvaluationReport",
]
