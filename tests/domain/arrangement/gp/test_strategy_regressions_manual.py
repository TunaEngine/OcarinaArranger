from __future__ import annotations

from domain.arrangement.config import register_instrument_range
from domain.arrangement.gp import arrange_v3_gp
from domain.arrangement.gp.fitness import FitnessVector
from domain.arrangement.gp.ops import GlobalTranspose
from domain.arrangement.gp.selection import Individual
from domain.arrangement.gp.session import GPSessionResult
from domain.arrangement.gp.session_logging import GPSessionLog
from domain.arrangement.soft_key import InstrumentRange

from tests.domain.arrangement.gp.gp_test_helpers import gp_config, make_span


def test_manual_transposition_disables_auto_range_expansion(monkeypatch) -> None:
    """Manual transpose offsets should skip auto-range program seeding."""

    instrument = InstrumentRange(min_midi=57, max_midi=77, comfort_center=67)
    register_instrument_range("manual_bass", instrument)

    base_phrase = make_span([64, 66, 68, 71])
    manual_shift = -5
    shifted_phrase = base_phrase.transpose(manual_shift)

    config = gp_config()
    winner = Individual(
        program=(),
        fitness=FitnessVector(
            playability=0.9,
            fidelity=0.9,
            tessitura=0.9,
            program_size=0.0,
        ),
    )
    fake_result = GPSessionResult(
        winner=winner,
        log=GPSessionLog(seed=config.random_seed, config={}),
        archive=(winner,),
        population=(winner,),
        generations=config.generations,
        elapsed_seconds=0.01,
        termination_reason="generation_limit",
    )

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy.run_gp_session",
        lambda *_args, **_kwargs: fake_result,
    )

    def _fail_auto_range(*_args, **_kwargs) -> tuple[tuple[GlobalTranspose, ...], ...]:
        raise AssertionError(
            "auto_range_programs should not run when manual transpose is set"
        )

    monkeypatch.setattr(
        "domain.arrangement.gp.strategy._auto_range_programs",
        _fail_auto_range,
    )

    result = arrange_v3_gp(
        shifted_phrase,
        instrument_id="manual_bass",
        config=config,
        manual_transposition=manual_shift,
    )

    assert result.chosen.program == ()
    assert result.programs == ((),)

