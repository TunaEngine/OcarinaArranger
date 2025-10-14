"""Tests for the arranger preview service helpers."""

from __future__ import annotations

import logging
from typing import Sequence

import pytest

from domain.arrangement.api import (
    ArrangementResult,
    ArrangementStrategyResult,
    DifficultySummary,
    InstrumentArrangement,
)
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange
from ocarina_gui.fingering import InstrumentChoice, InstrumentSpec
from ocarina_gui.preview import PreviewData
from ocarina_tools.events import NoteEvent

from services import arranger_preview
from services.arranger_monophonic import ensure_monophonic
from services.arranger_preview import compute_arranger_preview
from viewmodels.arranger_models import ArrangerBudgetSettings


def _make_spec(
    instrument_id: str,
    *,
    candidate_min: str,
    candidate_max: str,
    preferred_min: str,
    preferred_max: str,
) -> InstrumentSpec:
    return InstrumentSpec.from_dict(
        {
            "id": instrument_id,
            "name": instrument_id,
            "title": instrument_id,
            "canvas": {"width": 120, "height": 120},
            "style": {
                "background_color": "#ffffff",
                "outline_color": "#000000",
                "outline_width": 2.0,
                "outline_smooth": True,
                "outline_spline_steps": 16,
                "hole_outline_color": "#000000",
                "covered_fill_color": "#000000",
            },
            "holes": [],
            "windways": [],
            "note_order": ["C4"],
            "note_map": {"C4": []},
            "preferred_range": {"min": preferred_min, "max": preferred_max},
            "candidate_range": {"min": candidate_min, "max": candidate_max},
        }
    )


def _preview_fixture(events: Sequence[NoteEvent]) -> PreviewData:
    return PreviewData(
        original_events=tuple(events),
        arranged_events=tuple(events),
        pulses_per_quarter=480,
        beats=4,
        beat_type=4,
        original_range=(60, 88),
        arranged_range=(60, 88),
        tempo_bpm=120,
        tempo_changes=(),
    )


def test_compute_arranger_preview_normalizes_legacy_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=480, duration=480, midi=79, program=0),
    )
    preview = _preview_fixture(events)

    choices = (
        InstrumentChoice("alto_c_12", "12-hole Alto C"),
        InstrumentChoice("soprano_c_6", "6-hole Soprano C"),
    )

    specs = {
        "alto_c_12": _make_spec(
            "alto_c_12",
            candidate_min="B3",
            candidate_max="A5",
            preferred_min="C4",
            preferred_max="G5",
        ),
        "soprano_c_6": _make_spec(
            "soprano_c_6",
            candidate_min="C4",
            candidate_max="C6",
            preferred_min="D4",
            preferred_max="A5",
        ),
    }

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: specs[instrument_id],
    )

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c",
        starred_instrument_ids=("soprano_c", "unknown"),
        strategy="starred-best",
        dp_slack_enabled=False,
    )

    assert computation.summaries, "Expected instrument summaries to be returned"
    ids = {summary.instrument_id for summary in computation.summaries}
    assert ids == {"alto_c_12", "soprano_c_6"}

    assert computation.result_summary is not None
    assert computation.result_summary.instrument_id in {"alto_c_12", "soprano_c_6"}
    assert isinstance(computation.result_summary.transposition, int)
    assert computation.resolved_instrument_id == "alto_c_12"
    assert computation.resolved_starred_ids == ("soprano_c_6",)
    assert computation.telemetry, "Expected telemetry hints to be populated"
    for summary in computation.summaries:
        assert isinstance(summary.transposition, int)
    assert computation.arranged_events is not None


def test_compute_arranger_preview_returns_empty_when_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (NoteEvent(onset=0, duration=480, midi=72, program=0),)
    preview = _preview_fixture(events)

    # No available instruments -> computation should bail out gracefully.
    monkeypatch.setattr("services.arranger_preview.get_available_instruments", lambda: [])

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="does_not_exist",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
    )

    assert computation.summaries == ()
    assert computation.result_summary is None


def test_compute_arranger_preview_populates_salvage_details(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=92, program=0),
        NoteEvent(onset=240, duration=120, midi=72, program=0),
    )
    preview = _preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    specs = {
        "alto_c_12": _make_spec(
            "alto_c_12",
            candidate_min="B3",
            candidate_max="A5",
            preferred_min="C4",
            preferred_max="G5",
        )
    }

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: specs[instrument_id],
    )

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        budgets=ArrangerBudgetSettings(),
    )

    assert computation.result_summary is not None
    assert computation.result_summary.applied_steps, "Expected salvage steps to be recorded"
    assert computation.result_summary.edits.total >= 1
    assert isinstance(computation.result_summary.transposition, int)
    assert computation.explanations, "Expected explanation events for salvage edits"
    actions = {row.action for row in computation.explanations}
    assert "OCTAVE_DOWN_LOCAL" in actions or "rhythm-simplify" in actions
    assert computation.telemetry, "Expected telemetry hints for salvage run"
    assert computation.arranged_events is not None


def test_ensure_monophonic_prefers_highest_on_simultaneous() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=0, duration=240, midi=72, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=240, midi=72, program=0),
    )


def test_ensure_monophonic_discards_lower_priority_overlap() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=240, duration=480, midi=60, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
    )


def test_ensure_monophonic_trims_when_later_note_is_preferred() -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=60, program=0),
        NoteEvent(onset=240, duration=360, midi=74, program=0),
    )

    collapsed = ensure_monophonic(events)

    assert collapsed == (
        NoteEvent(onset=0, duration=240, midi=60, program=0),
        NoteEvent(onset=240, duration=360, midi=74, program=0),
    )


def test_compute_arranger_preview_transposes_events(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=84, program=0),
        NoteEvent(onset=480, duration=480, midi=86, program=0),
        NoteEvent(onset=960, duration=480, midi=88, program=0),
        NoteEvent(onset=1440, duration=480, midi=79, program=0),
        NoteEvent(onset=1920, duration=480, midi=88, program=0),
    )
    preview = _preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    specs = {
        "alto_c_12": _make_spec(
            "alto_c_12",
            candidate_min="B3",
            candidate_max="A5",
            preferred_min="C4",
            preferred_max="G5",
        )
    }

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: specs[instrument_id],
    )

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
    )

    assert computation.arranged_events is not None
    arranged_midis = [event.midi for event in computation.arranged_events]
    assert arranged_midis == [77, 79, 81, 72, 69]
    assert computation.result_summary is not None
    assert computation.result_summary.transposition == -7


def test_compute_arranger_preview_collapses_polyphonic_results(monkeypatch: pytest.MonkeyPatch) -> None:
    events = (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=960, duration=480, midi=74, program=0),
    )
    preview = _preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    spec = _make_spec(
        "alto_c_12",
        candidate_min="B3",
        candidate_max="A5",
        preferred_min="C4",
        preferred_max="G5",
    )

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: spec,
    )

    instrument_range = InstrumentRange(min_midi=60, max_midi=84, comfort_center=72)

    def _fake_arrange(span, **_kwargs):
        overlapping = PhraseSpan(
            (
                PhraseNote(onset=0, duration=480, midi=72),
                PhraseNote(onset=0, duration=480, midi=60),
            ),
            pulses_per_quarter=span.pulses_per_quarter,
        )
        result = ArrangementResult(span=overlapping, transposition=0)
        summary = DifficultySummary(
            easy=1.0,
            medium=0.0,
            hard=0.0,
            very_hard=0.0,
            tessitura_distance=0.0,
        )
        arrangement = InstrumentArrangement(
            instrument_id="alto_c_12",
            instrument=instrument_range,
            result=result,
            difficulty=summary,
        )
        return ArrangementStrategyResult(
            strategy="current",
            chosen=arrangement,
            comparisons=(arrangement,),
        )

    monkeypatch.setattr("services.arranger_preview.arrange", _fake_arrange)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
    )

    assert computation.arranged_events is not None
    onsets = [event.onset for event in computation.arranged_events]
    assert len(onsets) == len(set(onsets))
    midis = [event.midi for event in computation.arranged_events]
    assert 72 in midis and 60 not in midis


def test_compute_arranger_preview_logs_classic_algorithm(caplog) -> None:
    caplog.set_level(logging.INFO, logger="services.arranger_preview")

    preview = _preview_fixture(())

    computation = compute_arranger_preview(
        preview,
        arranger_mode="classic",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
    )

    assert computation.summaries == ()
    messages = [record.message for record in caplog.records if record.name == "services.arranger_preview"]
    assert any("algorithm=classic" in message for message in messages)


def test_compute_arranger_preview_logs_best_effort_algorithm(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    events = (
        NoteEvent(onset=0, duration=240, midi=92, program=0),
        NoteEvent(onset=240, duration=120, midi=72, program=0),
    )
    preview = _preview_fixture(events)

    choices = (InstrumentChoice("alto_c_12", "12-hole Alto C"),)
    specs = {
        "alto_c_12": _make_spec(
            "alto_c_12",
            candidate_min="B3",
            candidate_max="A5",
            preferred_min="C4",
            preferred_max="G5",
        )
    }

    monkeypatch.setattr(
        "services.arranger_preview.get_available_instruments",
        lambda: choices,
    )
    monkeypatch.setattr(
        "services.arranger_preview.get_instrument",
        lambda instrument_id: specs[instrument_id],
    )

    caplog.set_level(logging.INFO, logger="services.arranger_preview")

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=(),
        strategy="current",
        dp_slack_enabled=False,
        budgets=ArrangerBudgetSettings(),
    )

    assert computation.result_summary is not None
    messages = [record.message for record in caplog.records if record.name == "services.arranger_preview"]
    assert any("algorithm=best_effort" in message for message in messages)
    assert any("transposition=" in message for message in messages)
