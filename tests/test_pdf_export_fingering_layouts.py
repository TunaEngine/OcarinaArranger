from __future__ import annotations

from ocarina_gui.fingering import InstrumentSpec
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.notes import PatternData
from ocarina_gui.pdf_export.pages.fingering import build_fingering_pages

from tests.test_pdf_export import _collect_text_blocks


def _collect_rect_blocks(page) -> list[tuple[float, float, float, float]]:
    rects: list[tuple[float, float, float, float]] = []
    commands = getattr(page, "_commands")
    for command in commands:
        parts = command.split()
        if len(parts) < 5 or parts[-1] != "re":
            continue
        try:
            x, y, width, height = (float(value) for value in parts[:4])
        except ValueError:
            continue
        rects.append((x, y, width, height))
    return rects


def test_a6_fingering_page_uses_vertical_space_for_two_columns() -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "compact",
            "name": "Compact",
            "title": "Compact Instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": f"h{idx}", "x": 28 * idx, "y": 60, "radius": 8}
                for idx in range(1, 5)
            ],
            "note_order": ["C4"],
            "note_map": {"C4": [2, 2, 2, 2]},
        }
    )
    layout = resolve_layout("A6", "portrait")
    patterns = [
        PatternData(pattern=(2, 1, 0, 2), pattern_text=f"T{idx}", note_names=(f"N{idx}",))
        for idx in range(6)
    ]

    pages = build_fingering_pages(
        layout, patterns, (), instrument, columns=2, include_text=True
    )
    assert pages

    blocks = _collect_text_blocks(pages[0])
    pattern_texts = {entry.pattern_text for entry in patterns}
    pattern_blocks = [block for block in blocks if block[2] in pattern_texts]

    y_positions = {round(block[1], 2) for block in pattern_blocks}
    assert len(y_positions) >= 3


def test_fingering_labels_render_below_diagrams() -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "compact",
            "name": "Compact",
            "title": "Compact Instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "h1", "x": 28, "y": 60, "radius": 8},
                {"id": "h2", "x": 56, "y": 60, "radius": 8},
            ],
            "note_order": ["C4"],
            "note_map": {"C4": [2, 2]},
        }
    )
    layout = resolve_layout("A4", "portrait")
    pattern = PatternData(pattern=(2, 1), pattern_text="PATTERN-1", note_names=("NOTE-1",))

    pages = build_fingering_pages(
        layout, (pattern,), (), instrument, columns=2, include_text=True
    )
    assert pages

    rects = _collect_rect_blocks(pages[0])
    assert rects, "expected to capture at least one fingering diagram rectangle"

    _, rect_y, _width, rect_height = rects[0]
    diagram_top = layout.height - (rect_y + rect_height)
    diagram_bottom = diagram_top + rect_height

    blocks = _collect_text_blocks(pages[0])
    note_block = next(block for block in blocks if block[2] == "NOTE-1")
    pattern_block = next(block for block in blocks if block[2] == "PATTERN-1")

    assert note_block[1] >= diagram_bottom
    assert pattern_block[1] >= diagram_bottom
