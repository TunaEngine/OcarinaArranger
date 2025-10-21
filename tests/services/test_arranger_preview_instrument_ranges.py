"""Tests covering instrument selection normalization and range overrides."""

from __future__ import annotations

from typing import Callable, Sequence

import pytest

from domain.arrangement.api import (
    ArrangementResult,
    ArrangementStrategyResult,
    DifficultySummary,
    InstrumentArrangement,
)
from domain.arrangement.soft_key import InstrumentRange
from ocarina_gui.fingering import InstrumentChoice
from ocarina_tools.events import NoteEvent
from ocarina_tools.pitch import parse_note_name

from services.arranger_preview import compute_arranger_preview
from viewmodels.arranger_models import ArrangerBudgetSettings

from tests.services.arranger_preview_test_helpers import make_spec, preview_fixture


@pytest.fixture
def default_events() -> Sequence[NoteEvent]:
    return (
        NoteEvent(onset=0, duration=480, midi=72, program=0),
        NoteEvent(onset=480, duration=480, midi=79, program=0),
    )


@pytest.fixture
def register_default_instruments(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    choices: tuple[InstrumentChoice, ...] = (
        InstrumentChoice("alto_c_12", "12-hole Alto C"),
        InstrumentChoice("soprano_c_6", "6-hole Soprano C"),
    )
    specs = {
        "alto_c_12": make_spec(
            "alto_c_12",
            candidate_min="B3",
            candidate_max="A5",
            preferred_min="C4",
            preferred_max="G5",
        ),
        "soprano_c_6": make_spec(
            "soprano_c_6",
            candidate_min="C4",
            candidate_max="C6",
            preferred_min="D4",
            preferred_max="A5",
        ),
    }

    def _install() -> None:
        monkeypatch.setattr(
            "services.arranger_preview.get_available_instruments",
            lambda: choices,
        )
        monkeypatch.setattr(
            "services.arranger_preview.get_instrument",
            lambda instrument_id: specs[instrument_id],
        )

    return _install


def test_compute_arranger_preview_normalizes_legacy_ids(
    default_events: Sequence[NoteEvent],
    register_default_instruments: Callable[[], None],
) -> None:
    register_default_instruments()

    preview = preview_fixture(default_events)

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
    assert ids == {"soprano_c_6"}

    assert computation.result_summary is not None
    assert computation.result_summary.transposition == -3
    assert computation.result_summary.instrument_id == "soprano_c_6"
    assert isinstance(computation.result_summary.transposition, int)
    assert computation.resolved_instrument_id == "soprano_c_6"
    assert computation.resolved_instrument_range == ("D4", "A5")
    assert computation.resolved_starred_ids == ("soprano_c_6",)
    assert computation.telemetry, "Expected telemetry hints to be populated"
    for summary in computation.summaries:
        assert isinstance(summary.transposition, int)
    assert computation.arranged_events is not None


def test_compute_arranger_preview_keeps_selected_for_current_strategy(
    default_events: Sequence[NoteEvent],
    register_default_instruments: Callable[[], None],
) -> None:
    register_default_instruments()

    preview = preview_fixture(default_events)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=("soprano_c_6",),
        strategy="current",
        dp_slack_enabled=False,
    )

    assert computation.resolved_instrument_id == "alto_c_12"
    assert computation.resolved_instrument_range is None


def test_compute_arranger_preview_respects_selected_range_override(
    default_events: Sequence[NoteEvent],
    monkeypatch: pytest.MonkeyPatch,
    register_default_instruments: Callable[[], None],
) -> None:
    register_default_instruments()
    preview = preview_fixture(default_events)

    registered: dict[str, InstrumentRange] = {}

    def _capture_range(instrument_id: str, instrument_range: InstrumentRange) -> None:
        registered[instrument_id] = instrument_range

    monkeypatch.setattr(
        "services.arranger_preview_utils.register_instrument_range",
        _capture_range,
    )

    def _fake_arrange(span, **kwargs):
        instrument_id = kwargs.get("instrument_id", "alto_c_12")
        instrument_range = registered.get(
            instrument_id,
            InstrumentRange(min_midi=60, max_midi=84, comfort_center=72),
        )
        result = ArrangementResult(span=span, transposition=0)
        difficulty = DifficultySummary(
            easy=1.0,
            medium=0.0,
            hard=0.0,
            very_hard=0.0,
            tessitura_distance=0.0,
            leap_exposure=0.0,
            fast_windway_switch_exposure=0.0,
            subhole_transition_duration=0.0,
            subhole_exposure=0.0,
        )
        arrangement = InstrumentArrangement(
            instrument_id=instrument_id,
            instrument=instrument_range,
            result=result,
            difficulty=difficulty,
        )
        return ArrangementStrategyResult(
            strategy=kwargs.get("strategy", "current"),
            chosen=arrangement,
            comparisons=(arrangement,),
        )

    monkeypatch.setattr("services.arranger_preview.arrange", _fake_arrange)

    computation = compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=("soprano_c_6",),
        strategy="starred-best",
        dp_slack_enabled=False,
        budgets=ArrangerBudgetSettings(),
        selected_instrument_range=("F4", "D5"),
    )

    assert computation.result_summary is not None
    assert set(registered) == {"alto_c_12", "soprano_c_6"}

    selected_range = registered["alto_c_12"]
    starred_range = registered["soprano_c_6"]

    assert selected_range.min_midi == parse_note_name("F4")
    assert selected_range.max_midi == parse_note_name("D5")
    expected_center = (parse_note_name("F4") + parse_note_name("D5")) / 2.0
    assert selected_range.comfort_center == expected_center

    assert starred_range.min_midi == parse_note_name("C4")
    assert starred_range.max_midi == parse_note_name("C6")
    starred_center = (parse_note_name("D4") + parse_note_name("A5")) / 2.0
    assert starred_range.comfort_center == starred_center


def test_compute_arranger_preview_preserves_override_for_starred_selection(
    default_events: Sequence[NoteEvent],
    monkeypatch: pytest.MonkeyPatch,
    register_default_instruments: Callable[[], None],
) -> None:
    register_default_instruments()
    preview = preview_fixture(default_events)

    registered: dict[str, InstrumentRange] = {}

    def _capture_range(instrument_id: str, instrument_range: InstrumentRange) -> None:
        registered[instrument_id] = instrument_range

    monkeypatch.setattr(
        "services.arranger_preview_utils.register_instrument_range",
        _capture_range,
    )

    def _fake_arrange(span, **kwargs):
        instrument_id = kwargs.get("instrument_id", "alto_c_12")
        instrument_range = registered.get(
            instrument_id,
            InstrumentRange(min_midi=60, max_midi=84, comfort_center=72),
        )
        result = ArrangementResult(span=span, transposition=0)
        difficulty = DifficultySummary(
            easy=1.0,
            medium=0.0,
            hard=0.0,
            very_hard=0.0,
            tessitura_distance=0.0,
            leap_exposure=0.0,
            fast_windway_switch_exposure=0.0,
            subhole_transition_duration=0.0,
            subhole_exposure=0.0,
        )
        arrangement = InstrumentArrangement(
            instrument_id=instrument_id,
            instrument=instrument_range,
            result=result,
            difficulty=difficulty,
        )
        return ArrangementStrategyResult(
            strategy=kwargs.get("strategy", "current"),
            chosen=arrangement,
            comparisons=(arrangement,),
        )

    monkeypatch.setattr("services.arranger_preview.arrange", _fake_arrange)

    compute_arranger_preview(
        preview,
        arranger_mode="best_effort",
        instrument_id="alto_c_12",
        starred_instrument_ids=("alto_c_12",),
        strategy="starred-best",
        dp_slack_enabled=False,
        budgets=ArrangerBudgetSettings(),
        selected_instrument_range=("F4", "D5"),
    )

    assert registered, "Expected instrument ranges to be registered"
    selected_range = registered["alto_c_12"]

    assert selected_range.min_midi == parse_note_name("F4")
    assert selected_range.max_midi == parse_note_name("D5")
    expected_center = (parse_note_name("F4") + parse_note_name("D5")) / 2.0
    assert selected_range.comfort_center == expected_center
