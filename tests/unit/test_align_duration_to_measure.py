from shared.tempo import align_duration_to_measure


def test_align_duration_to_measure_returns_same_when_aligned():
    assert align_duration_to_measure(1920, 480, 4, 4) == 1920


def test_align_duration_to_measure_rounds_up_to_next_bar():
    # 4/4 measure at 480 ppq => 1920 ticks. Ensure partial measure rounds up.
    assert align_duration_to_measure(1500, 480, 4, 4) == 1920


def test_align_duration_to_measure_handles_compound_meter():
    # 6/8 should use dotted quarter beats -> 1440 ticks per measure at 480 ppq.
    assert align_duration_to_measure(1000, 480, 6, 8) == 1440
