"""Tests for column drag-and-drop behaviours in the fingerings table."""
from __future__ import annotations

from types import SimpleNamespace

from ui.main_window import MainWindow

from .helpers import _HeadlessPreview, _HeadlessTable


def _build_table(app: MainWindow, columns: tuple[str, ...]) -> _HeadlessTable:
    table = _HeadlessTable(["target"], columns)
    table.selection_set("target")
    table.focus("target")
    for column, width in zip(columns, (80, 60, 60, 60)):
        table.column(column, width=width)
    app.fingering_table = table
    return table


def _configure_app_for_reorder(app: MainWindow, table: _HeadlessTable) -> None:
    app._fingering_column_index = {name: index for index, name in enumerate(table["columns"][1:])}
    app._fingering_display_columns_override = list(table["columns"][1:])
    app._fingering_display_columns = table["columns"]
    app._fingering_column_drag_source = None
    app._on_fingering_table_select()


def _make_headless_app(*, edit_mode: bool) -> MainWindow:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = edit_mode
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = None
    app._fingering_note_to_midi = {"target": 60}
    app.fingering_preview = _HeadlessPreview()
    app._fingering_drop_indicator = None
    app._fingering_drop_indicator_color = None
    app._fingering_display_columns_override = None
    app._fingering_display_columns = tuple()
    app._fingering_column_index = {}
    app._fingering_column_drag_source = None
    app._fingering_heading_open_cursor = "hand2"
    app._fingering_heading_closed_cursor = "closedhand"
    app._fingering_heading_cursor_active = ""
    app._fingering_heading_closed_cursor_supported = None
    return app


def test_fingering_column_reorder_updates_display_order() -> None:
    app = _make_headless_app(edit_mode=True)
    columns = ("note", "hole_left", "hole_center", "hole_right")
    table = _build_table(app, columns)
    _configure_app_for_reorder(app, table)

    press = SimpleNamespace(x=140, y=0)
    table.set_click_target(note="target", column_ref="#3", region="heading")
    app._on_fingering_table_button_press(press)
    assert app._fingering_column_drag_source == "hole_center"

    release = SimpleNamespace(x=240, y=0)
    table.set_click_target(note="target", column_ref="#4", region="heading")
    app._on_fingering_cell_click(release)

    assert app._fingering_display_columns == ("note", "hole_left", "hole_right", "hole_center")
    assert app._fingering_display_columns_override == [
        "hole_left",
        "hole_right",
        "hole_center",
    ]
    assert app._fingering_column_drag_source is None


def test_fingering_column_reorder_preserves_hole_mapping() -> None:
    app = _make_headless_app(edit_mode=True)
    columns = ("note", "hole_left", "hole_center", "hole_right")
    table = _build_table(app, columns)
    _configure_app_for_reorder(app, table)

    table.set_click_target(note="target", column_ref="#3", region="heading")
    app._on_fingering_table_button_press(SimpleNamespace(x=140, y=0))
    table.set_click_target(note="target", column_ref="#4", region="heading")
    app._on_fingering_cell_click(SimpleNamespace(x=240, y=0))

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    table.set_click_target(note="target", column_ref="#3")
    app._on_fingering_cell_click(SimpleNamespace(x=10, y=5))
    app._on_fingering_cell_click(SimpleNamespace(x=10, y=5))

    assert toggled == [("target", 2)]


def test_fingering_column_reorder_updates_viewmodel_order() -> None:
    app = _make_headless_app(edit_mode=True)
    columns = ("note", "hole_left", "hole_center", "hole_right")
    table = _build_table(app, columns)
    _configure_app_for_reorder(app, table)

    orders: list[list[int]] = []

    class _FakeViewModel:
        def __init__(self) -> None:
            self.state = SimpleNamespace(
                instrument_id="inst", holes=[object(), object(), object()], windways=[]
            )

        def reorder_holes(self, order: list[int]) -> None:
            orders.append(list(order))

    applied: list[str | None] = []

    app._fingering_edit_vm = _FakeViewModel()
    app._apply_fingering_editor_changes = lambda focus=None: applied.append(focus)  # type: ignore[attr-defined]

    press = SimpleNamespace(x=140, y=0)
    table.set_click_target(note="target", column_ref="#3", region="heading")
    app._on_fingering_table_button_press(press)
    assert app._fingering_column_drag_source == "hole_center"

    release = SimpleNamespace(x=240, y=0)
    table.set_click_target(note="target", column_ref="#4", region="heading")
    app._on_fingering_cell_click(release)

    assert orders == [[0, 2, 1]]
    assert applied == ["target"]


def test_fingering_column_reorder_disabled_when_not_editing() -> None:
    app = _make_headless_app(edit_mode=False)
    columns = ("note", "hole_left", "hole_right")
    table = _build_table(app, columns)
    app._fingering_column_index = {"hole_left": 0, "hole_right": 1}
    app._fingering_display_columns_override = None
    app._fingering_display_columns = columns
    app._fingering_column_drag_source = None

    app._on_fingering_table_select()
    before = app._fingering_display_columns

    table.set_click_target(note="target", column_ref="#2", region="heading")
    app._on_fingering_heading_pointer_motion(SimpleNamespace(x=120, y=0))
    assert table.cursor == ""
    app._on_fingering_table_button_press(SimpleNamespace(x=120, y=0))
    assert app._fingering_column_drag_source is None

    table.set_click_target(note="target", column_ref="#3", region="heading")
    app._on_fingering_cell_click(SimpleNamespace(x=180, y=0))

    assert app._fingering_display_columns == before


def test_fingering_heading_cursor_feedback_during_reorder() -> None:
    app = _make_headless_app(edit_mode=True)
    columns = ("note", "hole_left", "hole_right")
    table = _build_table(app, columns)
    _configure_app_for_reorder(app, table)

    table.set_click_target(note="target", column_ref="#2", region="heading")
    hover = SimpleNamespace(x=120, y=0)
    app._on_fingering_heading_pointer_motion(hover)
    assert table.cursor == "hand2"

    app._on_fingering_table_button_press(hover)
    assert table.cursor in {"closedhand", "hand2"}

    app._on_fingering_heading_release(hover)
    assert table.cursor == "hand2"

    app._on_fingering_heading_pointer_leave(SimpleNamespace(x=0, y=0))
    assert table.cursor == ""
