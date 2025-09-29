from ocarina_gui.note_values import describe_note_glyph, describe_note_value


def test_describe_note_value_returns_known_label_and_fraction() -> None:
    desc = describe_note_value(480, 480)
    assert desc.label == "Quarter"
    assert desc.fraction == "1/4"
    assert desc.short_text() == "Quarter (1/4)"
    assert desc.long_text() == "Quarter note (1/4)"
    assert desc.compact_text() == "1/4"


def test_describe_note_value_handles_unknown_ratio() -> None:
    desc = describe_note_value(600, 480)
    assert desc.label == "1 1/4 beats"
    assert desc.fraction == "5/16"


def test_describe_note_value_handles_zero_and_ticks() -> None:
    rest = describe_note_value(0, 480)
    assert rest.label == "Rest"
    assert rest.fraction == ""

    ticks = describe_note_value(240, 0)
    assert ticks.label == "240 ticks"
    assert ticks.fraction == "240"


def test_describe_note_glyph_handles_basic_and_dotted_values() -> None:
    quarter = describe_note_glyph(480, 480)
    assert quarter is not None
    assert quarter.base == "quarter"
    assert quarter.dots == 0

    dotted_eighth = describe_note_glyph(360, 480)
    assert dotted_eighth is not None
    assert dotted_eighth.base == "eighth"
    assert dotted_eighth.dots == 1

    assert describe_note_glyph(0, 480) is None
