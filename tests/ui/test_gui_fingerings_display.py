import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import pytest

from ocarina_gui import themes
from ocarina_gui.fingering import get_current_instrument


def test_fingering_table_populated_from_config(gui_app):
    if getattr(gui_app, "_headless", False) or gui_app.fingering_table is None:
        pytest.skip("Fingerings table requires Tk widgets")

    table = gui_app.fingering_table
    assert table is not None

    instrument = get_current_instrument()
    columns = table["columns"]
    assert columns[0] == "note"
    assert len(columns) == len(instrument.holes) + 1

    rows = table.get_children()
    assert rows

    first_row = rows[0]
    values = table.item(first_row, "values")
    assert values[0] == instrument.note_order[0]
    assert len(values) == len(columns)
    assert set(values[1:]).issubset({"●", "○", "◐"})

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
        style = ttk.Style(table)
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

        style = ttk.Style(gui_app)
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
    style = ttk.Style(gui_app)
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
