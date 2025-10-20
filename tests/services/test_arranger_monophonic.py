from ocarina_tools import NoteEvent

from services.arranger_monophonic import ensure_monophonic


def test_ensure_monophonic_prefers_anchor_over_grace() -> None:
    grace = NoteEvent(onset=0, duration=20, midi=64, program=0, is_grace=True)
    anchor = NoteEvent(onset=0, duration=60, midi=62, program=0, is_grace=False)

    collapsed = ensure_monophonic([grace, anchor])

    assert len(collapsed) == 1
    kept = collapsed[0]
    assert not kept.is_grace
    assert kept.midi == 62


def test_ensure_monophonic_trims_grace_overlap() -> None:
    grace = NoteEvent(onset=0, duration=40, midi=64, program=0, is_grace=True)
    anchor = NoteEvent(onset=20, duration=40, midi=62, program=0, is_grace=False)

    collapsed = ensure_monophonic([grace, anchor])

    assert len(collapsed) == 2
    trimmed_grace, kept_anchor = collapsed
    assert trimmed_grace.duration == 20
    assert trimmed_grace.is_grace
    assert kept_anchor.onset == 20
