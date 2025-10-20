from __future__ import annotations

import json
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from domain.arrangement.api import arrange, arrange_span, summarize_difficulty, _run_candidate_pipeline
from domain.arrangement.constraints import (
    BreathSettings,
    SubholeConstraintSettings,
    SubholePairLimit,
)
from domain.arrangement.config import (
    FeatureFlags,
    clear_instrument_registry,
    register_instrument_range,
)
from domain.arrangement.importers import phrase_from_note_events
from domain.arrangement.melody import MelodyIsolationAction
from domain.arrangement.salvage import SalvageBudgets, default_salvage_cascade
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools import get_note_events

ASSETS = Path(__file__).parent / "assets"


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    clear_instrument_registry()
    yield
    clear_instrument_registry()


def _load_phrase(filename: str):
    root = ET.parse(ASSETS / filename).getroot()
    events, pulses_per_quarter = get_note_events(root)
    return phrase_from_note_events(events, pulses_per_quarter)


def _load_json(filename: str) -> dict:
    with open(ASSETS / filename, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _note_signature(span):
    return [(note.onset, note.duration, note.midi) for note in span.notes]


def _action_signature(actions: tuple[MelodyIsolationAction, ...]) -> list[dict]:
    return [
        {
            "measure": action.measure,
            "action": action.action,
            "reason": action.reason,
            "kept_voice": action.kept_voice,
            "removed_voice": action.removed_voice,
        }
        for action in actions
    ]


def _drop_signature(actions: tuple[MelodyIsolationAction, ...]) -> list[dict]:
    return [
        {
            "measure": action.measure,
            "action": action.action,
            "reason": action.reason,
            "dropped_voice": action.removed_voice,
        }
        for action in actions
        if action.action == "DROP_HIGH_DUPLICATE"
    ]


def _octave_event_payloads(salvage) -> list[dict]:
    if salvage is None:
        return []
    return [
        event.to_payload()
        for event in salvage.explanations
        if event.action == "OCTAVE_DOWN_LOCAL"
    ]


def test_polyphonic_melody_isolation_keeps_primary_voice() -> None:
    span = _load_phrase("01_melody_from_chords_input.musicxml")
    expected_span = _load_phrase("01_melody_from_chords_expected.musicxml")
    expected_explanations = _load_json("01_melody_from_chords_explanation.json")

    instrument = InstrumentRange(min_midi=60, max_midi=79, comfort_center=69)

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=None,
    )

    normalized_result = result.span.transpose(-result.transposition)
    assert _note_signature(normalized_result) == _note_signature(expected_span)
    assert result.melody_actions
    assert _action_signature(result.melody_actions) == expected_explanations["actions"]
    assert all(event.action == "MELODY_ISOLATION" for event in result.preprocessing)


def test_polyphonic_drops_high_octave_duplicate() -> None:
    span = _load_phrase("02_high_echo_duplicate_input.musicxml")
    expected_span = _load_phrase("02_high_echo_duplicate_expected.musicxml")
    expected_explanations = _load_json("02_high_echo_duplicate_explanation.json")

    instrument = InstrumentRange(min_midi=60, max_midi=79, comfort_center=69)

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=None,
    )

    normalized_result = result.span.transpose(-result.transposition)
    assert _note_signature(normalized_result) == _note_signature(expected_span)

    drop_actions = _drop_signature(result.melody_actions)
    assert drop_actions == expected_explanations["actions"]

    drop_events = [event for event in result.preprocessing if event.action == "DROP_HIGH_DUPLICATE"]
    assert drop_events, "expected DROP_HIGH_DUPLICATE explanation event"
    assert drop_events[0].reason == "salience*contrast < added_difficulty"


def test_polyphonic_local_octave_fold_adds_explanation() -> None:
    span = _load_phrase("03_out_of_range_fold_input.musicxml")
    expected_span = _load_phrase("03_out_of_range_fold_expected.musicxml")
    expected_explanations = _load_json("03_out_of_range_fold_explanation.json")

    instrument = InstrumentRange(min_midi=60, max_midi=79, comfort_center=69)
    cascade = default_salvage_cascade(threshold=0.7)

    result = _run_candidate_pipeline(
        span,
        instrument,
        logger=logging.getLogger("tests.arranger_polyphonic"),
        flags=FeatureFlags(dp_slack=False),
        folding_settings=None,
        salvage_cascade=cascade,
    )

    normalized_result = result.span
    assert _note_signature(normalized_result) == _note_signature(expected_span)

    salvage = result.salvage
    assert salvage is not None
    octave_events = _octave_event_payloads(salvage)
    assert octave_events, "expected OCTAVE_DOWN_LOCAL explanation"
    payload = octave_events[0]
    expected_action = expected_explanations["actions"][0]
    assert payload["bar"] == expected_action["measure"]
    assert payload["action"] == expected_action["action"]
    assert payload["reason"] == expected_action["reason"]
    assert payload["span"] == expected_action["span"]


def test_polyphonic_transposition_prefers_lower_key() -> None:
    span = _load_phrase("polyphonic_high_register.xml")
    instrument = InstrumentRange(min_midi=55, max_midi=80, comfort_center=67)

    baseline = summarize_difficulty(span, instrument)
    cascade = default_salvage_cascade(threshold=0.8)
    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=cascade,
    )

    summary = summarize_difficulty(result.span, instrument)
    assert result.transposition <= -6
    assert summary.hard_and_very_hard < baseline.hard_and_very_hard
    assert max(note.midi for note in result.span.notes) <= max(note.midi for note in span.notes) - 6


def test_polyphonic_salvage_respects_budgets_and_reports_explanations() -> None:
    span = _load_phrase("polyphonic_salvage.xml")
    instrument = InstrumentRange(min_midi=60, max_midi=76, comfort_center=67)
    budgets = SalvageBudgets(max_octave_edits=1, max_rhythm_edits=1, max_substitutions=1, max_steps_per_span=3)
    cascade = default_salvage_cascade(threshold=0.18, budgets=budgets)

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=cascade,
    )

    salvage = result.salvage
    assert salvage is not None
    assert salvage.edits_used["total"] <= budgets.max_steps_per_span
    assert salvage.edits_used.get("rhythm", 0) <= budgets.max_rhythm_edits
    assert salvage.edits_used.get("octave", 0) <= budgets.max_octave_edits
    payloads = [event.to_payload() for event in salvage.explanations]
    if payloads:
        assert payloads[0]["schema_version"] == 1
        if salvage.success:
            assert payloads[-1]["reason_code"] != "not-recommended"
        else:
            assert payloads[-1]["reason_code"] == "not-recommended"
    else:
        assert not salvage.applied_steps
        assert salvage.edits_used["total"] == 0


def test_polyphonic_subhole_run_replaced_with_grace_and_hold() -> None:
    span = _load_phrase("04_subhole_speed_input.musicxml")
    expected_span = _load_phrase("04_subhole_speed_expected.musicxml")
    expected_explanations = _load_json("04_subhole_speed_explanation.json")

    annotated = [note.with_tags(note.tags | {"subhole"}) for note in span.notes]
    span = span.with_notes(annotated)

    instrument = InstrumentRange(min_midi=60, max_midi=79, comfort_center=69)
    settings = SubholeConstraintSettings(
        max_changes_per_second=4.0,
        max_subhole_changes_per_second=3.0,
        pair_limits={
            frozenset({64, 65}): SubholePairLimit(max_hz=2.0, ease=1.0),
        },
    )

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=None,
        tempo_bpm=120.0,
        subhole_settings=settings,
    )

    normalized_result = result.span.transpose(-result.transposition)
    assert _note_signature(normalized_result) == _note_signature(expected_span)

    subhole_events = [
        event.to_payload()
        for event in result.preprocessing
        if event.action == "SUBHOLE_RATE_REPLACE"
    ]
    assert subhole_events, "expected SUBHOLE_RATE_REPLACE explanation event"
    payload = subhole_events[0]
    expected_action = expected_explanations["actions"][0]
    assert payload["bar"] == expected_action["measure"]
    assert payload["action"] == expected_action["action"]
    assert payload["reason"] == expected_action["reason"]


def test_polyphonic_breath_planning_inserts_midbar_breath() -> None:
    span = _load_phrase("05_breath_planning_input.musicxml")
    expected_span = _load_phrase("05_breath_planning_expected.musicxml")
    expected_explanations = _load_json("05_breath_planning_explanation.json")

    instrument = InstrumentRange(min_midi=60, max_midi=79, comfort_center=69)
    breath_settings = BreathSettings(
        base_limit_seconds=3.0,
        tempo_factor=0.02,
        register_factor=1.25,
        min_limit_seconds=1.0,
        max_limit_seconds=5.0,
    )

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=None,
        tempo_bpm=60.0,
        breath_settings=breath_settings,
    )

    normalized_result = result.span.transpose(-result.transposition)
    assert _note_signature(normalized_result) == _note_signature(expected_span)

    breath_events = [
        event.to_payload()
        for event in result.preprocessing
        if event.action == "BREATH_INSERT"
    ]
    assert breath_events, "expected BREATH_INSERT explanation event"
    payload = breath_events[0]
    expected_action = expected_explanations["actions"][0]
    assert payload["bar"] == expected_action["measure"]
    assert payload["action"] == expected_action["action"]
    assert payload["reason"] == expected_action["reason"]


def test_polyphonic_starred_strategy_uses_dp_and_ranks_instruments() -> None:
    span = _load_phrase("polyphonic_starred.xml")

    register_instrument_range("current", InstrumentRange(min_midi=60, max_midi=82, comfort_center=70))
    register_instrument_range("alto", InstrumentRange(min_midi=55, max_midi=79, comfort_center=67))
    register_instrument_range("soprano", InstrumentRange(min_midi=69, max_midi=93, comfort_center=76))

    cascade = default_salvage_cascade(threshold=0.5)
    result = arrange(
        span,
        instrument_id="current",
        starred_ids=("alto", "soprano"),
        strategy="starred-best",
        flags=FeatureFlags(dp_slack=True),
        salvage_cascade=cascade,
    )

    assert result.strategy == "starred-best"
    assert len(result.comparisons) == 2
    ranking = tuple(
        sorted(
            result.comparisons,
            key=lambda item: (
                item.difficulty.hard_and_very_hard,
                item.difficulty.medium,
                item.difficulty.tessitura_distance,
            ),
        )
    )
    assert result.comparisons == ranking
    assert result.chosen == ranking[0]
    assert result.chosen.result.folding is not None


def test_polyphonic_dp_slack_folds_far_apart_voices() -> None:
    span = _load_phrase("polyphonic_long_dp.xml")
    instrument = InstrumentRange(min_midi=60, max_midi=76, comfort_center=68)

    without_dp = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=False),
        salvage_cascade=None,
    )
    with_dp = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=True),
        salvage_cascade=None,
    )

    assert without_dp.folding is None
    assert with_dp.folding is not None
    assert all(
        instrument.min_midi <= note.midi <= instrument.max_midi
        for note in without_dp.span.notes
    )
    assert any(
        event.reason_code == "range-clamp" for event in without_dp.preprocessing
    )
    assert with_dp.span.notes != without_dp.span.notes

    baseline = summarize_difficulty(without_dp.span, instrument)
    summary = summarize_difficulty(with_dp.span, instrument)
    assert summary.hard_and_very_hard < baseline.hard_and_very_hard
    assert summary.tessitura_distance <= baseline.tessitura_distance


def test_polyphonic_complex_pipeline_runs_full_salvage() -> None:
    span = _load_phrase("polyphonic_complex_pipeline.xml")
    instrument = InstrumentRange(min_midi=58, max_midi=80, comfort_center=69)
    budgets = SalvageBudgets(max_octave_edits=1, max_rhythm_edits=1, max_substitutions=1, max_steps_per_span=3)
    cascade = default_salvage_cascade(threshold=0.18, budgets=budgets)

    result = arrange_span(
        span,
        instrument=instrument,
        flags=FeatureFlags(dp_slack=True),
        salvage_cascade=cascade,
    )

    assert result.folding is not None
    salvage = result.salvage
    assert salvage is not None
    assert salvage.applied_steps
    if salvage.success:
        assert "OCTAVE_DOWN_LOCAL" in salvage.applied_steps
        assert "rhythm-simplify" in salvage.applied_steps
        assert salvage.edits_used.get("total", 0) > 0
        assert salvage.difficulty < salvage.starting_difficulty
        assert salvage.explanations
    else:
        assert salvage.applied_steps[-1] == "not-recommended"
        assert salvage.explanations
        assert salvage.explanations[-1].action == "not-recommended"
        assert salvage.edits_used.get("total", 0) == 0
        assert salvage.difficulty == salvage.starting_difficulty

    baseline = summarize_difficulty(span.transpose(result.transposition), instrument)
    summary = summarize_difficulty(result.span, instrument)
    assert summary.hard_and_very_hard < baseline.hard_and_very_hard
    assert summary.leap_exposure > 0
