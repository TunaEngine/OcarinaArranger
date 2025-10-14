from __future__ import annotations

from datetime import datetime, timezone

import pytest

from domain.arrangement.learning import (
    ApprovalLogger,
    ApprovalRecord,
    ArrangementProposal,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan


class _InMemoryStore:
    def __init__(self) -> None:
        self.records: list[ApprovalRecord] = []

    def save(self, record: ApprovalRecord) -> None:
        self.records.append(record)


def _make_span(midi: int) -> PhraseSpan:
    notes = (PhraseNote(onset=0, duration=480, midi=midi),)
    return PhraseSpan(notes, pulses_per_quarter=480)


def test_approval_logger_persists_record_with_metadata() -> None:
    store = _InMemoryStore()
    logger = ApprovalLogger(store)
    proposal = ArrangementProposal(
        original=_make_span(72),
        proposal=_make_span(60),
        applied_steps=("OCTAVE_DOWN_LOCAL", "rhythm-simplify"),
        difficulty_before=1.2,
        difficulty_after=0.7,
    )

    record = logger.log_approval(proposal, metadata={"user_id": "abc"})

    assert store.records == [record]
    assert record.metadata["user_id"] == "abc"
    assert record.proposal.difficulty_delta == pytest.approx(0.5)
    assert record.approved_at.tzinfo is timezone.utc


def test_approval_logger_uses_provided_timestamp() -> None:
    store = _InMemoryStore()
    logger = ApprovalLogger(store)
    proposal = ArrangementProposal(
        original=_make_span(67),
        proposal=_make_span(65),
        applied_steps=("lengthen-pivotal",),
        difficulty_before=0.9,
        difficulty_after=0.7,
    )
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)

    record = logger.log_approval(proposal, approved_at=timestamp)

    assert store.records == [record]
    assert record.approved_at == timestamp

from domain.arrangement.learning import ArrangementEvaluator, EvaluationReport


def test_arrangement_evaluator_reports_overlap_and_gap() -> None:
    store = _InMemoryStore()
    logger = ApprovalLogger(store)
    proposal_a = ArrangementProposal(
        original=_make_span(72),
        proposal=_make_span(60),
        applied_steps=("OCTAVE_DOWN_LOCAL", "rhythm-simplify"),
        difficulty_before=1.2,
        difficulty_after=0.7,
    )
    proposal_b = ArrangementProposal(
        original=_make_span(70),
        proposal=_make_span(67),
        applied_steps=("OCTAVE_DOWN_LOCAL",),
        difficulty_before=1.0,
        difficulty_after=0.7,
    )
    logger.log_approval(proposal_a)
    logger.log_approval(proposal_b)

    evaluator = ArrangementEvaluator(store.records)
    proposal = ArrangementProposal(
        original=_make_span(74),
        proposal=_make_span(62),
        applied_steps=("OCTAVE_DOWN_LOCAL", "lengthen-pivotal"),
        difficulty_before=1.1,
        difficulty_after=0.7,
    )

    report = evaluator.evaluate(proposal)

    assert isinstance(report, EvaluationReport)
    assert report.approval_count == 2
    assert report.step_overlap == pytest.approx(0.5)
    assert report.matched_steps == ("OCTAVE_DOWN_LOCAL",)
    assert report.missing_steps == ("lengthen-pivotal",)
    assert report.difficulty_delta_gap == pytest.approx(0.0)


def test_arrangement_evaluator_handles_empty_history() -> None:
    evaluator = ArrangementEvaluator(())
    proposal = ArrangementProposal(
        original=_make_span(72),
        proposal=_make_span(60),
        applied_steps=("OCTAVE_DOWN_LOCAL",),
        difficulty_before=1.2,
        difficulty_after=0.9,
    )

    report = evaluator.evaluate(proposal)

    assert report.approval_count == 0
    assert report.step_overlap == 0.0
    assert report.difficulty_delta_gap == pytest.approx(proposal.difficulty_delta)
    assert report.matched_steps == ()
    assert report.missing_steps == ("OCTAVE_DOWN_LOCAL",)
