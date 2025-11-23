from __future__ import annotations

import pytest

from ocarina_gui.fingering import InstrumentSpec
from ocarina_gui.pdf_export.header import (
    build_header_lines,
    draw_document_header,
    header_gap as compute_header_gap,
    header_height as compute_header_height,
)
from ocarina_gui.pdf_export.layouts import resolve_layout
from ocarina_gui.pdf_export.notes import ArrangedNote, PatternData, group_patterns
from ocarina_gui.pdf_export.pages.fingering import build_fingering_pages
from ocarina_gui.pdf_export.pages.piano_roll import build_piano_roll_pages
from ocarina_gui.pdf_export.pages.staff import build_staff_pages
from ocarina_gui.pdf_export.pages.text import build_text_page
from ocarina_gui.pdf_export.types import NoteEvent
from ocarina_gui.pdf_export.writer import PageBuilder


def test_header_link_draws_blue_hyperlink() -> None:
    layout = resolve_layout("A4", "portrait")
    page = PageBuilder(layout)
    header_lines = build_header_lines()

    draw_document_header(page, layout, header_lines)

    link_lines = [line for line in header_lines if line.link]
    annotations = tuple(page.link_annotations)

    assert len(annotations) == len(link_lines)
    if link_lines:
        assert annotations[0].uri == link_lines[0].link
        rect = annotations[0].rect
        assert rect[2] > rect[0]
        assert rect[3] > rect[1]

    commands = getattr(page, "_commands")
    assert "0.000 0.200 0.800 rg" in commands


def test_staff_pdf_includes_measure_numbers() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        NoteEvent(0, 240, 60, 0),
        NoteEvent(1920, 240, 62, 0),
        NoteEvent(3840, 240, 64, 0),
    ]

    pages = build_staff_pages(layout, events, pulses_per_quarter=480)

    assert pages, "expected at least one staff page"

    blocks = _collect_text_blocks(pages[0])
    _assert_header_present(blocks)

    texts_with_gray = _collect_text_with_gray(pages[0])
    measure_numbers = {text for gray, text in texts_with_gray if abs(gray - 0.55) < 1e-6}

    assert "2" in measure_numbers
    assert "3" in measure_numbers


def test_piano_roll_pdf_includes_measure_numbers() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        NoteEvent(0, 240, 60, 0),
        NoteEvent(1920, 240, 62, 0),
        NoteEvent(3840, 240, 64, 0),
    ]

    pages = build_piano_roll_pages(layout, events, pulses_per_quarter=480)

    assert pages, "expected at least one piano roll page"

    blocks = _collect_text_blocks(pages[0])
    _assert_header_present(blocks)

    texts_with_gray = _collect_text_with_gray(pages[0])
    measure_numbers = {text for gray, text in texts_with_gray if abs(gray - 0.35) < 1e-6}

    assert "2" in measure_numbers
    assert "3" in measure_numbers


def test_staff_pdf_uses_time_signature_for_measure_spans() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        NoteEvent(0, 240, 60, 0),
        NoteEvent(720, 240, 62, 0),
        NoteEvent(1440, 240, 64, 0),
    ]

    pages = build_staff_pages(
        layout, events, pulses_per_quarter=480, beats=3, beat_type=8
    )

    texts_with_gray = _collect_text_with_gray(pages[0])
    measure_numbers = {text for gray, text in texts_with_gray if abs(gray - 0.55) < 1e-6}

    assert {"2", "3"} <= measure_numbers


def test_piano_roll_pdf_uses_time_signature_for_measure_spans() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        NoteEvent(0, 240, 60, 0),
        NoteEvent(720, 240, 62, 0),
        NoteEvent(1440, 240, 64, 0),
    ]

    pages = build_piano_roll_pages(
        layout, events, pulses_per_quarter=480, beats=3, beat_type=8
    )

    texts_with_gray = _collect_text_with_gray(pages[0])
    measure_numbers = {text for gray, text in texts_with_gray if abs(gray - 0.35) < 1e-6}

    assert {"2", "3"} <= measure_numbers


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
    header_lines = build_header_lines()
    header_height = compute_header_height(layout, header_lines)
    header_gap = compute_header_gap(layout, header_lines)
    label_top = layout.margin_top + header_height + header_gap
    estimated_y_start = (
        label_top + estimated_label_height + layout.line_height * 0.5
    )
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
    _assert_header_present(blocks)
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


def test_fingering_pdf_outline_uses_smoothed_path(monkeypatch: pytest.MonkeyPatch) -> None:
    layout = resolve_layout("A4", "portrait")
    instrument = InstrumentSpec.from_dict(
        {
            "id": "smooth",
            "name": "Smooth",
            "title": "Smooth Instrument",
            "canvas": {"width": 160, "height": 120},
            "style": {"outline_smooth": True, "outline_spline_steps": 12},
            "outline": {
                "points": [[10, 30], [50, 20], [90, 25], [120, 80]],
                "closed": False,
            },
            "holes": [{"id": "h1", "x": 40, "y": 40, "radius": 10}],
            "note_order": ["C4"],
            "note_map": {"C4": [2]},
        }
    )
    pattern = PatternData(pattern=(2,), pattern_text="X", note_names=("C4",))

    captured: list[list[tuple[float, float]]] = []

    original_draw = PageBuilder.draw_polygon

    def _recording_draw(self, points, **kwargs):
        captured.append(list(points))
        return original_draw(self, points, **kwargs)

    monkeypatch.setattr(PageBuilder, "draw_polygon", _recording_draw)

    pages = build_fingering_pages(layout, [pattern], (), instrument, columns=1)
    assert pages, "expected fingering page to be generated"

    blocks = _collect_text_blocks(pages[0])
    _assert_header_present(blocks)

    original_point_count = len(instrument.outline.points) if instrument.outline else 0
    outline_points = None
    for entry in captured:
        if len(entry) > original_point_count:
            outline_points = entry
            break

    assert outline_points is not None, "expected outline polygon to be recorded"
    assert len(outline_points) > original_point_count


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
    _assert_header_present(blocks)
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


def test_staff_page_draws_ledger_lines_without_octave_labels() -> None:
    layout = resolve_layout("A4", "portrait")
    events = [
        NoteEvent(0, 120, 52, 0),
        NoteEvent(480, 120, 84, 0),
    ]

    pages = build_staff_pages(layout, events, pulses_per_quarter=480)
    assert pages

    commands = "\n".join(pages[0]._commands)
    assert "0.60 w" in commands

    blocks = _collect_text_blocks(pages[0])
    _assert_header_present(blocks)
    header_lines = build_header_lines()
    summary_threshold = (
        layout.margin_top
        + compute_header_height(layout, header_lines)
        + compute_header_gap(layout, header_lines)
        + layout.line_height * 2
    )
    octave_blocks = {
        text
        for _x, y, text in blocks
        if text in {"3", "6"} and y > summary_threshold
    }
    assert not octave_blocks


def _collect_text_with_gray(page) -> list[tuple[float, str]]:
    commands = getattr(page, "_commands")
    results: list[tuple[float, str]] = []
    for index, command in enumerate(commands):
        if command != "BT" or index < 1 or index + 3 >= len(commands):
            continue
        fill_command = commands[index - 1]
        text_command = commands[index + 3]
        if not fill_command.endswith(" g") or not text_command.endswith(" Tj"):
            continue
        try:
            gray = float(fill_command.split()[0])
        except ValueError:
            continue
        text_body = text_command[:-3]
        if not (text_body.startswith("(") and text_body.endswith(")")):
            continue
        results.append((gray, text_body[1:-1]))
    return results


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


def _assert_header_present(blocks: list[tuple[float, float, str]]) -> None:
    header_lines = build_header_lines()
    expected = {line.text for line in header_lines}
    observed = {text for _x, _y, text in blocks}
    assert expected <= observed


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
