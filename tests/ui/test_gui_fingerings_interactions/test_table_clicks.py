"""Tests for table selection interactions within the fingerings tab."""

from __future__ import annotations

from ui.main_window import MainWindow

from .helpers import _HeadlessPreview, _HeadlessTable, make_click_event


def test_fingering_cell_click_respects_active_row() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = True
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = None
    app._fingering_note_to_midi = {"primary": 60, "target": 62}
    app._fingering_drop_indicator = None
    app._fingering_drop_indicator_color = None
    app.fingering_preview = _HeadlessPreview()

    table = _HeadlessTable(["primary", "target"], ("note", "hole_1"))
    table.selection_set("primary")
    table.focus("primary")
    app.fingering_table = table
    app._fingering_column_index = {"hole_1": 0}
    app._fingering_display_columns_override = ["hole_1"]
    app._fingering_display_columns = ("note", "hole_1")
    app._fingering_column_drag_source = None

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._on_fingering_table_select()

    event = make_click_event()
    table.set_click_target(note="target", column_ref="#2")

    table.selection_set("target")
    table.focus("target")
    app._on_fingering_table_select()

    app._on_fingering_cell_click(event)
    assert toggled == []
    assert table.selection() == ("target",)
    assert table.focus() == "target"

    app._on_fingering_cell_click(event)
    assert toggled == [("target", 0)]


def test_fingering_cell_click_requires_active_row_after_switching() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = True
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = None
    rows = ["note_a", "note_b", "note_c", "note_d"]
    app._fingering_note_to_midi = {note: 60 + index for index, note in enumerate(rows)}
    app.fingering_preview = _HeadlessPreview()
    app._fingering_drop_indicator = None
    app._fingering_drop_indicator_color = None

    table = _HeadlessTable(rows, ("note", "hole_1"))
    table.selection_set(rows[0])
    table.focus(rows[0])
    app.fingering_table = table
    app._fingering_column_index = {"hole_1": 0}
    app._fingering_display_columns_override = ["hole_1"]
    app._fingering_display_columns = ("note", "hole_1")
    app._fingering_column_drag_source = None

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._on_fingering_table_select()

    event = make_click_event()

    for note in rows[1:-1]:
        table.set_click_target(note=note, column_ref="#2")
        table.selection_set(note)
        table.focus(note)
        app._on_fingering_table_select()
        app._on_fingering_cell_click(event)
        assert toggled == []
        assert table.selection() == (note,)
        assert table.focus() == note

    target = rows[-1]
    table.set_click_target(note=target, column_ref="#2")

    table.selection_set(target)
    table.focus(target)
    app._on_fingering_table_select()

    app._on_fingering_cell_click(event)
    assert toggled == []
    assert table.selection() == (target,)
    assert table.focus() == target

    app._on_fingering_cell_click(event)
    assert toggled == [(target, 0)]


def test_fingering_cell_click_does_not_mark_select_ignore_on_focus_restore() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = True
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = None
    app._fingering_note_to_midi = {"primary": 60, "target": 62}
    app.fingering_preview = _HeadlessPreview()
    app._fingering_drop_indicator = None
    app._fingering_drop_indicator_color = None

    table = _HeadlessTable(["primary", "target"], ("note", "hole_1"))
    table.selection_set("primary")
    table.focus("primary")
    app.fingering_table = table
    app._fingering_column_index = {"hole_1": 0}
    app._fingering_display_columns_override = ["hole_1"]
    app._fingering_display_columns = ("note", "hole_1")
    app._fingering_column_drag_source = None

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._on_fingering_table_select()

    event = make_click_event()
    table.set_click_target(note="target", column_ref="#2")

    table.selection_set("target")
    table.focus("target")
    app._on_fingering_table_select()

    table.focus("primary")

    assert app._fingering_ignore_next_select is False

    app._on_fingering_cell_click(event)

    assert app._fingering_ignore_next_select is False
    assert toggled == []
    assert app._fingering_click_guard_note is None
    assert table.focus() == "target"

    app._on_fingering_cell_click(event)
    assert toggled == [("target", 0)]
