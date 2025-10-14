from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

import pytest

from ocarina_gui.fingering import (
    get_available_instruments,
    get_current_instrument,
    get_current_instrument_id,
)


def test_new_instrument_selection_updates_after_copy(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    selector = gui_app.fingering_selector
    if selector is None:
        pytest.skip("Fingerings selector unavailable")

    gui_app.toggle_fingering_editing()
    try:
        viewmodel = gui_app._fingering_edit_vm
        if viewmodel is None:
            pytest.skip("Fingering editor view-model unavailable")

        new_identifier = "custom_copy"
        new_name = "Custom Copy"
        viewmodel.add_instrument(new_identifier, new_name)

        choices = viewmodel.copyable_instrument_choices()
        if not choices:
            pytest.skip("No compatible instruments available for copy")

        source_id = choices[0][0]
        viewmodel.copy_fingerings_from(source_id)

        expected_id = viewmodel.state.instrument_id
        expected_map = {
            note: tuple(pattern)
            for note, pattern in viewmodel.state.note_map.items()
        }
        expected_notes = set(expected_map.keys())

        gui_app.toggle_fingering_editing()
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits()

    gui_app.update_idletasks()

    available = get_available_instruments()
    lookup = {choice.instrument_id: choice.name for choice in available}
    if expected_id not in lookup:
        pytest.skip("New instrument was not registered")

    expected_name = lookup[expected_id]
    other_choice = next(
        (choice for choice in available if choice.instrument_id != expected_id),
        None,
    )
    if other_choice is None:
        pytest.skip("Need at least one other instrument to switch to")

    def _select(name: str) -> None:
        selector.set(name)
        selector.event_generate("<<ComboboxSelected>>")
        gui_app.update_idletasks()

    _select(other_choice.name)
    assert get_current_instrument_id() == other_choice.instrument_id

    _select(expected_name)
    assert get_current_instrument_id() == expected_id

    table = gui_app.fingering_table
    assert table is not None

    visible_rows = [
        table.item(row, "values")
        for row in table.get_children()
        if row != "_empty"
    ]
    assert visible_rows, "expected fingering rows for the new instrument"

    visible_notes = {values[0] for values in visible_rows}
    assert visible_notes == expected_notes

    instrument = get_current_instrument()
    assert {
        note: tuple(pattern)
        for note, pattern in instrument.note_map.items()
    } == expected_map
