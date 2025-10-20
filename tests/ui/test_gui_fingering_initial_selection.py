import pytest

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from ocarina_gui.fingering import (  # noqa: E402
    get_current_instrument,
    get_current_instrument_id,
)


@pytest.mark.parametrize("gui_app", [{"instrument_id": "test_alt"}], indirect=True)
def test_initial_fingering_selection_respects_saved_instrument(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    expected_id = "test_alt"
    expected_name = "Secondary test instrument"

    assert gui_app._viewmodel.state.instrument_id == expected_id
    assert gui_app._selected_instrument_id == expected_id
    assert get_current_instrument_id() == expected_id

    selector = gui_app.fingering_selector
    assert selector is not None
    assert selector.get() == expected_name

    instrument_var = gui_app.fingering_instrument_var
    assert instrument_var is not None
    assert instrument_var.get() == expected_name

    instrument = get_current_instrument()
    assert instrument.instrument_id == expected_id

    table = gui_app.fingering_table
    assert table is not None
    rows = table.get_children()
    assert rows
    first_row = rows[0]
    values = table.item(first_row, "values")
    assert values[0] == instrument.note_order[0]

    assert gui_app.range_min.get() == instrument.preferred_range_min
    assert gui_app.range_max.get() == instrument.preferred_range_max
    assert gui_app._viewmodel.state.range_min == instrument.preferred_range_min
    assert gui_app._viewmodel.state.range_max == instrument.preferred_range_max
