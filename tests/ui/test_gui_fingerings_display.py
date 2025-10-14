import tkinter as tk
from tkinter import font as tkfont

import pytest

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from shared.ttk import ttk

from ocarina_gui import themes
from ocarina_gui.fingering import (
    FingeringConfigPersistenceError,
    get_available_instruments,
    get_current_instrument,
    get_current_instrument_id,
)
from shared.tk_style import get_ttk_style


def test_fingering_table_populated_from_config(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    table = gui_app.fingering_table
    assert table is not None

    instrument = get_current_instrument()
    columns = table["columns"]
    assert columns[0] == "note"
    assert len(columns) == len(instrument.holes) + len(instrument.windways) + 1

    rows = table.get_children()
    assert rows

    first_row = rows[0]
    values = table.item(first_row, "values")
    assert values[0] == instrument.note_order[0]
    assert len(values) == len(columns)
    assert set(values[1:]).issubset({"●", "○", "◐", "–"})

    table.selection_set(first_row)
    gui_app._on_fingering_table_select()

    preview = gui_app.fingering_preview
    assert preview is not None
    expected_midi = gui_app._parse_note_safe(values[0])
    assert preview._current_midi == expected_midi


def test_add_note_uses_selection_dialog(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    instrument = get_current_instrument()
    existing = set(instrument.note_map.keys())
    captured: dict[str, object] = {}

    def _fake_prompt(parent, choices, *, disabled, title):  # pragma: no cover - arguments validated below
        captured["choices"] = tuple(choices)
        captured["disabled"] = tuple(disabled)
        for choice in choices:
            if choice not in disabled:
                return choice
        return None

    monkeypatch.setattr("ui.main_window.prompt_for_note_name", _fake_prompt)
    monkeypatch.setattr("ui.main_window.messagebox.showinfo", lambda *args, **kwargs: None)

    gui_app.toggle_fingering_editing()
    try:
        gui_app.add_fingering_note()
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits()

    if not captured:
        pytest.skip("No additional fingering notes available to add")

    choices = captured["choices"]
    disabled = set(captured["disabled"])

    assert isinstance(choices, tuple)
    assert any(choice not in existing for choice in choices)
    assert existing.issubset(disabled)


def test_copy_fingerings_prompts_for_compatible_instruments(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    gui_app.toggle_fingering_editing()
    try:
        viewmodel = gui_app._fingering_edit_vm
        if viewmodel is None:
            pytest.skip("Fingering editor view-model unavailable")

        choices = viewmodel.copyable_instrument_choices()
        if not choices:
            pytest.skip("No compatible instruments available for copy")

        captured: dict[str, object] = {}
        called: dict[str, object] = {}

        def _fake_prompt(parent, choices_arg, *, title):
            captured["choices"] = tuple(choices_arg)
            captured["title"] = title
            return choices_arg[0][0]

        def _fake_copy(self, instrument_id):  # pragma: no cover - signature validated
            called["instrument_id"] = instrument_id

        monkeypatch.setattr("ui.main_window.prompt_for_instrument_choice", _fake_prompt)
        monkeypatch.setattr(type(viewmodel), "copy_fingerings_from", _fake_copy, raising=False)
        monkeypatch.setattr("ui.main_window.messagebox.showinfo", lambda *a, **k: None)
        monkeypatch.setattr("ui.main_window.messagebox.showerror", lambda *a, **k: None)

        gui_app.copy_fingerings_from_instrument()
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits()

    assert captured.get("choices") == tuple(choices)
    assert captured.get("title") == "Copy Fingerings"
    assert called.get("instrument_id") == choices[0][0]


def test_remove_flat_note_disables_button(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    gui_app.toggle_fingering_editing()
    try:
        viewmodel = gui_app._fingering_edit_vm
        if viewmodel is None:
            pytest.skip("Fingering editor view-model unavailable")

        state = viewmodel.state
        if not state.candidate_range_min or not state.candidate_range_max:
            pytest.skip("Instrument lacks an explicit available range")

        viewmodel.set_candidate_range(state.candidate_range_min, state.candidate_range_max)
        gui_app._apply_fingering_editor_changes()

        table = gui_app.fingering_table
        assert table is not None

        flat_note = next(
            (row for row in table.get_children() if len(row) > 2 and row[1].lower() == "b"),
            None,
        )
        if flat_note is None:
            pytest.skip("No flat notes available for removal test")

        table.selection_set(flat_note)
        gui_app._on_fingering_table_select()

        remove_button = gui_app._fingering_remove_button
        assert remove_button is not None
        assert not remove_button.instate(["disabled"])

        monkeypatch.setattr("ui.main_window.messagebox.askyesno", lambda *args, **kwargs: True)
        monkeypatch.setattr("ui.main_window.messagebox.showerror", lambda *args, **kwargs: None)

        gui_app.remove_fingering_note()
        gui_app.update_idletasks()

        assert not table.exists(flat_note)
        assert not table.selection()
        assert remove_button.instate(["disabled"])
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits()


def test_fingering_table_columns_size_to_content(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    table = gui_app.fingering_table
    instrument = get_current_instrument()

    try:
        heading_font = tkfont.nametofont("TkHeadingFont")
    except tk.TclError:
        heading_font = tkfont.nametofont("TkDefaultFont")

    try:
        body_font_name = str(table.cget("font"))
    except tk.TclError:
        body_font_name = ""

    if not body_font_name:
        style = get_ttk_style(table)
        body_font_name = style.lookup("Treeview", "font") or ""

    if not body_font_name:
        body_font_name = "TkDefaultFont"

    try:
        body_font = tkfont.nametofont(body_font_name)
    except tk.TclError:
        body_font = tkfont.nametofont("TkDefaultFont")

    heading_text = table.heading("note", "text")
    heading_width = max((heading_font.measure(line) for line in heading_text.split("\n") if line), default=0)
    column_width = int(float(table.column("note", "width")))
    assert column_width >= heading_width

    notes = instrument.note_order or tuple(sorted(instrument.note_map.keys()))
    if notes:
        widest_note = max(body_font.measure(note) for note in notes)
        assert column_width >= widest_note

    assert str(table.column("note", "stretch")) == "0"
    columns = table["columns"]
    if len(columns) > 1:
        assert str(table.column(columns[1], "stretch")) == "0"

    multiline_columns = [column_id for column_id in columns if "\n" in table.heading(column_id, "text")]
    if multiline_columns:
        max_lines = max(
            len([line for line in table.heading(column_id, "text").split("\n") if line])
            for column_id in multiline_columns
        )
        assert max_lines > 1

        style = get_ttk_style(gui_app)
        table_style = getattr(gui_app, "_fingering_table_style", None)
        heading_style = f"{table_style}.Heading" if table_style else "Treeview.Heading"
        padding_value = style.configure(heading_style, "padding") or style.configure("Treeview.Heading", "padding")

        def _normalize_padding(value):
            if not value:
                return (0, 0, 0, 0)
            if isinstance(value, str):
                parts = value.split()
            else:
                try:
                    parts = list(value)
                except TypeError:  # pragma: no cover - defensive for unexpected ttk return types
                    parts = [value]
            numeric = []
            for part in parts:
                if part is None:
                    continue
                text = str(part)
                if text == "":
                    continue
                try:
                    numeric.append(int(float(text)))
                except (TypeError, ValueError):
                    continue
            if not numeric:
                return (0, 0, 0, 0)
            if len(numeric) == 1:
                left = top = right = bottom = numeric[0]
            elif len(numeric) == 2:
                left, top = numeric
                right, bottom = left, top
            elif len(numeric) == 3:
                left, top, right = numeric
                bottom = top
            else:
                left, top, right, bottom, *_ = numeric
            return (left, top, right, bottom)

        left, top, right, bottom = _normalize_padding(padding_value)
        top_bottom_padding = top + bottom
        linespace = heading_font.metrics("linespace")
        required_padding = (max_lines - 1) * linespace
        assert top_bottom_padding >= required_padding


def test_fingering_table_applies_theme_palette(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    table = gui_app.fingering_table
    style = get_ttk_style(gui_app)
    original_theme = themes.get_current_theme()

    choices = [choice.theme_id for choice in themes.get_available_themes() if choice.theme_id != original_theme.theme_id]
    if not choices:
        pytest.skip("No alternate theme available for testing")

    target_theme = choices[0]

    try:
        gui_app.set_theme(target_theme)
        gui_app.update_idletasks()
        active = themes.get_current_theme()
        palette = active.palette.table

        assert style.configure("Treeview", "background") == palette.background
        assert style.configure("Treeview", "fieldbackground") == palette.background
        assert style.configure("Treeview", "foreground") == palette.foreground
        assert style.configure("Treeview.Heading", "background") == palette.heading_background
        assert style.configure("Treeview.Heading", "foreground") == palette.heading_foreground

        background_map = style.map("Treeview", "background")
        foreground_map = style.map("Treeview", "foreground")
        assert ("selected", palette.selection_background) in background_map
        assert ("selected", palette.selection_foreground) in foreground_map

        # Ensure zebra striping picks up the palette colors.
        if table.get_children():
            even_background = table.tag_configure("even").get("background")
            odd_background = table.tag_configure("odd").get("background")
            assert even_background == palette.background
            assert odd_background == palette.row_stripe
    finally:
        gui_app.set_theme(original_theme.theme_id)
        gui_app.update_idletasks()


def test_fingering_preview_replaces_note_text(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    preview = gui_app.fingering_preview
    table = gui_app.fingering_table
    if preview is None or table is None:
        pytest.skip("Fingering preview not available")

    rows = [row for row in table.get_children() if row != "_empty"]
    if len(rows) < 2:
        pytest.skip("Not enough fingerings to switch selection")

    table.selection_set(rows[0])
    table.focus(rows[0])
    gui_app._on_fingering_table_select()
    gui_app.update_idletasks()
    initial = preview.find_withtag("note")

    table.selection_set(rows[1])
    table.focus(rows[1])
    gui_app._on_fingering_table_select()
    gui_app.update_idletasks()
    subsequent = preview.find_withtag("note")

    assert len(subsequent) == len(initial)


def test_instrument_switching_disabled_during_edit(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Fingerings editor requires Tk widgets")

    choices = get_available_instruments()
    if len(choices) < 2:
        pytest.skip("Multiple instruments required to test switching")

    original_id = get_current_instrument_id()
    target_choice = next(
        (choice for choice in choices if choice.instrument_id != original_id),
        None,
    )
    if target_choice is None:
        pytest.skip("No alternate instrument available")

    notifications: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _capture_message(*args, **kwargs):
        notifications.append((args, kwargs))

    monkeypatch.setattr("ui.main_window.messagebox.showinfo", _capture_message)

    gui_app.toggle_fingering_editing()
    try:
        selector = gui_app.fingering_selector
        if selector is None:
            pytest.skip("Fingerings selector widget unavailable")
        assert selector.cget("state") == "disabled"

        convert_combo = gui_app._convert_instrument_combo
        if convert_combo is not None:
            assert convert_combo.cget("state") == "disabled"

        gui_app.set_fingering_instrument(target_choice.instrument_id)
        assert get_current_instrument_id() == original_id
        assert notifications
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits()

    selector = gui_app.fingering_selector
    if selector is not None:
        assert selector.cget("state") == "readonly"
    convert_combo = gui_app._convert_instrument_combo
    if convert_combo is not None:
        assert convert_combo.cget("state") == "readonly"


def test_six_hole_instrument_enables_half_holes(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Fingerings editor requires Tk widgets")

    choices = get_available_instruments()
    target = next((c for c in choices if c.instrument_id == "alto_c_6"), None)
    if target is None:
        pytest.skip("6-hole instrument not available")

    original_id = get_current_instrument_id()
    try:
        gui_app.set_fingering_instrument(target.instrument_id)
        var = getattr(gui_app, "_fingering_allow_half_var", None)
        if var is None:
            pytest.skip("Half-hole toggle variable unavailable")
        assert bool(var.get()) is True
        assert getattr(gui_app, "_fingering_half_notes_enabled", False) is True
    finally:
        if original_id != target.instrument_id:
            gui_app.set_fingering_instrument(original_id)


def test_destroy_discards_pending_fingering_edits(gui_app):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Fingerings editor requires Tk widgets")

    instrument = get_current_instrument()
    if not instrument.note_order:
        pytest.skip("Instrument has no notes to edit")

    target_note = instrument.note_order[0]
    original_pattern = list(instrument.note_map.get(target_note, []))
    if not original_pattern:
        pytest.skip("Instrument note pattern unavailable")

    gui_app.toggle_fingering_editing()
    viewmodel = getattr(gui_app, "_fingering_edit_vm", None)
    if viewmodel is None:
        gui_app.cancel_fingering_edits(show_errors=False)
        pytest.skip("Fingering editor view-model unavailable")

    replacement_pattern = [0] * len(original_pattern)
    if replacement_pattern == original_pattern:
        replacement_pattern = [2 if value == 0 else 0 for value in original_pattern]
    viewmodel.set_note_pattern(target_note, replacement_pattern)
    gui_app._apply_fingering_editor_changes(target_note)

    modified = get_current_instrument().note_map[target_note]
    assert modified == replacement_pattern

    gui_app.destroy()

    restored = get_current_instrument().note_map[target_note]
    assert restored == original_pattern


def test_disk_full_during_save_shows_actionable_error(gui_app, monkeypatch):
    if getattr(gui_app, "_headless", False):
        pytest.skip("Fingerings editor requires Tk widgets")

    gui_app.toggle_fingering_editing()
    try:
        viewmodel = getattr(gui_app, "_fingering_edit_vm", None)
        if viewmodel is None:
            pytest.skip("Fingering editor view-model unavailable")

        errors: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _record_error(*args, **kwargs):
            errors.append((args, kwargs))

        monkeypatch.setattr("ui.main_window.messagebox.showerror", _record_error)

        def _raise_failure(config):  # pragma: no cover - arguments exercised indirectly
            raise FingeringConfigPersistenceError(
                "Could not save fingering configuration at fingering_config.json. "
                "Free up some disk space and try again."
            )

        monkeypatch.setattr(
            "ocarina_gui.fingering.library.save_fingering_config",
            _raise_failure,
        )

        gui_app._apply_fingering_editor_changes(persist=True)

        assert errors, "Expected a save failure to trigger an error dialog"
        message = errors[0][0][1]
        assert "Free up some disk space" in message
    finally:
        if gui_app._fingering_edit_mode:
            gui_app.cancel_fingering_edits(show_errors=False)
