"""Tests for preview widget interactions in the fingerings tab."""

from __future__ import annotations

from ui.main_window import MainWindow

from .helpers import _HeadlessPreview, _HeadlessTable


def test_register_fingering_preview_binds_click_handler() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    preview = _HeadlessPreview()

    def _fake_cycle(note: str, hole_index: int) -> None:  # pragma: no cover - unused in this test
        pass

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._register_fingering_preview(preview)
    assert preview.hole_handler is not None


def test_fingering_preview_click_cycles_active_note() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = True
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = "target"
    app._fingering_note_to_midi = {"target": 60}
    app.fingering_preview = _HeadlessPreview()
    table = _HeadlessTable(["target"], ("note",))
    table.selection_set("target")
    table.focus("target")
    app.fingering_table = table

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._register_fingering_preview(app.fingering_preview)

    app.fingering_preview.trigger_hole_click(2)

    assert toggled == [("target", 2)]


def test_fingering_preview_click_ignored_when_not_editing() -> None:
    app = MainWindow.__new__(MainWindow)
    app._headless = True
    app._fingering_edit_vm = None
    app._fingering_edit_mode = False
    app._fingering_ignore_next_select = False
    app._fingering_click_guard_note = None
    app._fingering_last_selected_note = "target"
    app._fingering_note_to_midi = {"target": 60}
    app.fingering_preview = _HeadlessPreview()
    table = _HeadlessTable(["target"], ("note",))
    table.selection_set("target")
    table.focus("target")
    app.fingering_table = table

    toggled: list[tuple[str, int]] = []

    def _fake_cycle(note: str, hole_index: int) -> None:
        toggled.append((note, hole_index))

    app._cycle_fingering_state = _fake_cycle  # type: ignore[attr-defined]

    app._register_fingering_preview(app.fingering_preview)
    app.fingering_preview.trigger_hole_click(1)

    assert toggled == []
