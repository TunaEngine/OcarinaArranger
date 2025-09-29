from __future__ import annotations

from pathlib import Path

import pytest

from ocarina_gui.fingering import FingeringLibrary, InstrumentSpec
from ocarina_gui.pdf_export import export_arranged_pdf
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.notes import ArrangedNote, PatternData, group_patterns
from ocarina_gui.pdf_export.pages.fingering import build_fingering_pages
from ocarina_gui.pdf_export.pages.staff import build_staff_pages
from ocarina_gui.pdf_export.pages.text import build_text_page
from ocarina_gui.pdf_export.types import PdfExportOptions
from tests.helpers import make_linear_score


def _install_test_instrument(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test",
            "title": "Test Instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "h1", "x": 40, "y": 40, "radius": 10},
                {"id": "h2", "x": 80, "y": 40, "radius": 10},
                {"id": "h3", "x": 120, "y": 40, "radius": 10},
            ],
            "note_order": ["C4", "D4", "E4"],
            "note_map": {
                "C4": [2, 2, 2],
                "D4": [2, 2, 0],
                "E4": [2, 0, 0],
            },
        }
    )
    monkeypatch.setattr("ocarina_gui.fingering._LIBRARY", FingeringLibrary([instrument]))


def test_export_arranged_pdf_writes_expected_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "arranged.pdf"
    export_arranged_pdf(
        root,
        str(pdf_path),
        "A4",
        "portrait",
        4,
        prefer_flats=True,
        include_piano_roll=True,
        include_staff=True,
        include_text=True,
        include_fingerings=True,
    )

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"Arranged piano roll" in data
    assert b"Quarter" not in data
    assert b"Quarter note" not in data
    assert b"Eighth" not in data
    for label in (b"h1", b"h2", b"h3"):
        assert label in data
    assert b"Arranged staff view" in data
    assert b"Used fingerings visuals" in data
    assert b"C4" in data


def test_export_arranged_pdf_skips_disabled_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "arranged.pdf"
    export_arranged_pdf(
        root,
        str(pdf_path),
        "A4",
        "portrait",
        4,
        prefer_flats=True,
        include_piano_roll=False,
        include_staff=False,
        include_text=False,
        include_fingerings=True,
    )

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"Arranged piano roll" not in data
    assert b"Arranged staff view" not in data
    assert b"001   C4" not in data
    assert b"Used fingerings visuals" in data


def test_export_arranged_pdf_rejects_unknown_page_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree, root = make_linear_score()
    _install_test_instrument(monkeypatch)

    pdf_path = tmp_path / "invalid.pdf"
    with pytest.raises(ValueError):
        export_arranged_pdf(root, str(pdf_path), "Letter", "portrait", 4, prefer_flats=False)


def test_pdf_export_options_default_columns() -> None:
    portrait = PdfExportOptions(page_size="A6", orientation="portrait")
    assert portrait.columns == 2
    assert portrait.include_piano_roll is True
    assert portrait.include_staff is True
    assert portrait.include_text is True
    assert portrait.include_fingerings is True
    landscape = PdfExportOptions(page_size="a6", orientation="LANDSCAPE")
    assert landscape.columns == 4
    custom = PdfExportOptions(page_size="A4", orientation="portrait", columns=3)
    assert custom.columns == 3


def test_text_page_uses_multiple_columns_when_space_allows() -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "test",
            "name": "Test",
            "title": "Test Instrument",
            "canvas": {"width": 160, "height": 120},
            "holes": [
                {"id": "h1", "x": 40, "y": 40, "radius": 10},
                {"id": "h2", "x": 80, "y": 40, "radius": 10},
                {"id": "h3", "x": 120, "y": 40, "radius": 10},
            ],
        }
    )
    layout = resolve_layout("A4", "landscape")
    column_gap = layout.line_height * 1.5
    available_width = layout.width - 2 * layout.margin_left
    max_columns_by_width = max(
        1, int((available_width + column_gap) // (150.0 + column_gap))
    )
    char_step = layout.font_size * 0.6
    estimated_label_height = max(len(label) for label in ("h1", "h2", "h3")) * char_step
    estimated_y_start = layout.margin_top + estimated_label_height + layout.line_height * 0.5
    available_height = layout.height - layout.margin_bottom - estimated_y_start
    lines_per_column = max(1, int(available_height // layout.line_height))
    note_count = max_columns_by_width * lines_per_column + lines_per_column // 2 + 1

    notes = [
        ArrangedNote(
            index=index + 1,
            midi=60 + (index % 12),
            note_name=f"C{index % 7}",
            pattern_text="XOO",
            pattern_state=(2, 2, 0),
        )
        for index in range(note_count)
    ]

    pages = build_text_page(layout, instrument, "A4", notes)
    assert pages
    assert len(pages) > 1

    blocks = _collect_text_blocks(pages[0])
    entry_blocks = [block for block in blocks if block[2].strip()[:3].isdigit()]
    assert len(entry_blocks) > 1
    x_positions = {round(block[0], 2) for block in entry_blocks}
    assert len(x_positions) > 1

    label_blocks = [block for block in blocks if block[2] in {"h1", "h2", "h3"}]
    assert label_blocks

    entry_groups: dict[float, list[str]] = {}
    for x, _, text in entry_blocks:
        entry_groups.setdefault(x, []).append(text)
    entry_xs = sorted(entry_groups)
    label_xs = sorted(block[0] for block in label_blocks if block[2] == "h1")
    assert len(label_xs) == len(entry_xs)

    sample_line = entry_blocks[0][2]
    pattern_index = sample_line.index("XOO")
    char_step = layout.font_size * 0.6
    for entry_x, label_x in zip(entry_xs, label_xs):
        assert abs(label_x - (entry_x + pattern_index * char_step)) < 0.6

    command_blob = "\n".join(pages[0]._commands)
    assert "0.00 -1.00 1.00 0.00" in command_blob


def test_fingering_page_respects_requested_columns() -> None:
    instrument = InstrumentSpec.from_dict(
        {
            "id": "wide",
            "name": "Wide",
            "title": "Wide Instrument",
            "canvas": {"width": 320, "height": 180},
            "holes": [
                {"id": f"h{i}", "x": 40 * i, "y": 60, "radius": 10}
                for i in range(1, 7)
            ],
        }
    )
    layout = resolve_layout("A4", "landscape")
    patterns = [
        PatternData(pattern=(2, 2, 2, 2, 2, 2), pattern_text="XXXXXX", note_names=(f"N{idx}",))
        for idx in range(10)
    ]

    pages = build_fingering_pages(layout, patterns, (), instrument, columns=4)
    assert pages

    blocks = _collect_text_blocks(pages[0])
    pattern_blocks = [block for block in blocks if block[2].startswith("Pattern:")]
    assert pattern_blocks
    x_positions = {round(block[0], 2) for block in pattern_blocks}
    assert len(x_positions) >= 4
    y_positions = {round(block[1], 2) for block in pattern_blocks}
    assert len(y_positions) >= 2


def test_group_patterns_sorted_by_midi() -> None:
    notes = [
        ArrangedNote(
            index=1,
            midi=64,
            note_name="E4",
            pattern_text="XOO",
            pattern_state=(2, 2, 0),
        ),
        ArrangedNote(
            index=2,
            midi=60,
            note_name="C4",
            pattern_text="OOO",
            pattern_state=(0, 0, 0),
        ),
        ArrangedNote(
            index=3,
            midi=62,
            note_name="D4",
            pattern_text="/OO",
            pattern_state=(1, 0, 0),
        ),
    ]

    patterns, missing = group_patterns(notes)

    assert not missing
    assert [entry.note_names[0] for entry in patterns] == ["C4", "D4", "E4"]


def test_group_patterns_handles_mixed_accidentals_and_octaves() -> None:
    notes = [
        ArrangedNote(
            index=idx,
            midi=midi,
            note_name=note_name,
            pattern_text=f"pattern-{idx}",
            pattern_state=(idx,),
        )
        for idx, (midi, note_name) in enumerate(
            [
                (80, "Ab5"),
                (70, "Bb4"),
                (72, "C5"),
                (84, "C6"),
                (73, "Db5"),
                (75, "Eb5"),
                (77, "F5"),
                (89, "F6"),
                (79, "G5"),
            ],
            start=1,
        )
    ]

    patterns, missing = group_patterns(notes)

    assert not missing
    assert [entry.note_names[0] for entry in patterns] == [
        "Bb4",
        "C5",
        "Db5",
        "Eb5",
        "F5",
        "G5",
        "Ab5",
        "C6",
        "F6",
    ]


def test_staff_page_draws_ledger_lines_and_octave_labels() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        (0, 120, 52, 0),
        (480, 120, 84, 0),
    ]

    pages = build_staff_pages(layout, events, pulses_per_quarter=480)
    assert pages

    commands = "\n".join(pages[0]._commands)
    assert "0.60 w" in commands

    blocks = _collect_text_blocks(pages[0])
    summary_threshold = layout.margin_top + layout.line_height
    octave_blocks = {
        text
        for _x, y, text in blocks
        if text in {"3", "6"} and y > summary_threshold
    }
    assert {"3", "6"} <= octave_blocks


def _collect_text_blocks(page) -> list[tuple[float, float, str]]:
    blocks: list[tuple[float, float, str]] = []
    commands = getattr(page, "_commands")
    layout = page.layout
    index = 0
    while index < len(commands):
        if commands[index] == "BT" and index + 3 < len(commands):
            tm_cmd = commands[index + 2]
            tj_cmd = commands[index + 3]
            parts = tm_cmd.split()
            try:
                x = float(parts[4])
                baseline = float(parts[5])
            except (IndexError, ValueError):
                x = 0.0
                baseline = layout.height
            text = _parse_tj_text(tj_cmd)
            y = layout.height - baseline
            blocks.append((x, y, text))
            index += 5
        else:
            index += 1
    return blocks


def _parse_tj_text(command: str) -> str:
    text = command
    if text.endswith(" Tj"):
        text = text[:-3].strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    text = text.replace("\\\\", "\\")
    text = text.replace("\\(", "(")
    text = text.replace("\\)", ")")
    return text
