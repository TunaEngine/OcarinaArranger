"""Logging-specific GP strategy regressions."""

from __future__ import annotations

import logging

from domain.arrangement.config import clear_instrument_registry, register_instrument_range
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.gp.program_utils import apply_program
from domain.arrangement.soft_key import InstrumentRange
from ocarina_tools import midi_to_name

from tests.domain.arrangement.gp.test_strategy import _gp_config, _make_span


def setup_function() -> None:  # noqa: D401 - pytest hook to reset registry
    clear_instrument_registry()


def test_gp_strategy_logs_note_names(caplog) -> None:
    phrase = _make_span([60, 62, 64])
    register_instrument_range(
        "ocarina", InstrumentRange(min_midi=57, max_midi=81, comfort_center=69)
    )

    with caplog.at_level(logging.DEBUG, logger="domain.arrangement.gp.strategy"):
        result = arrange_v3_gp(
            phrase,
            instrument_id="ocarina",
            config=_gp_config(),
        )

    winner_logs = [
        record
        for record in caplog.records
        if record.name == "domain.arrangement.gp.strategy"
        and record.msg.startswith("arrange_v3_gp:winner note names")
    ]
    assert winner_logs, "expected winner note name log entry"
    winner_record = winner_logs[-1]
    winner_program = tuple(result.session.winner.program)
    winner_span = phrase if not winner_program else apply_program(winner_program, phrase)
    winner_names = tuple(midi_to_name(note.midi) for note in winner_span.notes)

    chosen_logs = [
        record
        for record in caplog.records
        if record.name == "domain.arrangement.gp.strategy"
        and record.msg.startswith("arrange_v3_gp:note names")
    ]
    assert chosen_logs, "expected chosen candidate note name log entry"
    record = chosen_logs[-1]
    original_names = tuple(midi_to_name(note.midi) for note in phrase.notes)
    arranged_names = tuple(midi_to_name(note.midi) for note in result.chosen.span.notes)
    assert winner_record.args[2] == original_names
    assert winner_record.args[3] == winner_names
    assert record.args[2] == original_names
    assert record.args[3] == arranged_names


__all__ = ["test_gp_strategy_logs_note_names"]
