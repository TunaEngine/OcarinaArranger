import pytest

from domain.arrangement.gp.engine import LocalSearchBudgets, evaluate_spans
from domain.arrangement.phrase import PhraseNote, PhraseSpan
from domain.arrangement.soft_key import InstrumentRange


def _span_for(midis: list[int]) -> PhraseSpan:
    return PhraseSpan(
        tuple(
            PhraseNote(onset=index * 240, duration=240, midi=midi)
            for index, midi in enumerate(midis)
        ),
        pulses_per_quarter=480,
    )


def test_memetic_dp_improves_highest_penalty_span() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    troublesome = _span_for([84, 85, 86, 87])
    stable = _span_for([62, 64, 65, 67])

    baseline = evaluate_spans((troublesome, stable), instrument)
    memetic = evaluate_spans((troublesome, stable), instrument, enable_memetic_dp=True)

    baseline_penalties = [evaluation.playability_penalty for evaluation in baseline]
    memetic_penalties = [evaluation.playability_penalty for evaluation in memetic]

    assert memetic_penalties[0] <= baseline_penalties[0]
    assert memetic_penalties[1] == pytest.approx(baseline_penalties[1])

    if memetic_penalties[0] < baseline_penalties[0]:
        assert memetic[0].annotations[-1] == "memetic-dp:fold-octaves"
        assert memetic[0].folding is not None

    repeat = evaluate_spans((troublesome, stable), instrument, enable_memetic_dp=True)
    assert repeat == memetic


def test_memetic_local_search_respects_budgets() -> None:
    instrument = InstrumentRange(60, 72, comfort_center=66)
    troublesome = _span_for([84, 85, 86, 87])

    baseline = evaluate_spans((troublesome,), instrument)

    allowed = evaluate_spans(
        (troublesome,),
        instrument,
        enable_memetic_dp=True,
        budgets=LocalSearchBudgets(max_total_edits=2, max_edits_per_span=1),
    )
    assert allowed[0].annotations in ((), ("memetic-dp:fold-octaves",))
    assert allowed[0].playability_penalty <= baseline[0].playability_penalty

    span_limited = evaluate_spans(
        (troublesome,),
        instrument,
        enable_memetic_dp=True,
        budgets=LocalSearchBudgets(max_total_edits=2, max_edits_per_span=0),
    )
    assert span_limited == baseline

    total_limited = evaluate_spans(
        (troublesome,),
        instrument,
        enable_memetic_dp=True,
        budgets=LocalSearchBudgets(max_total_edits=0, max_edits_per_span=1),
    )
    assert total_limited == baseline
