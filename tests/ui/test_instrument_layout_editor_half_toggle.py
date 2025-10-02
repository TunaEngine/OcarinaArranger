from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from ocarina_gui.fingering import InstrumentSpec
from ocarina_gui.fingering.half_holes import instrument_allows_half_holes
from ocarina_gui.layout_editor import InstrumentLayoutEditor
from viewmodels.instrument_layout_editor import InstrumentLayoutEditorViewModel


def _collect_checkbuttons(widget: tk.Misc) -> list[ttk.Checkbutton]:
    found: list[ttk.Checkbutton] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Checkbutton):
            found.append(child)
        found.extend(_collect_checkbuttons(child))
    return found


def _simple_spec(instrument_id: str, name: str) -> InstrumentSpec:
    return InstrumentSpec.from_dict(
        {
            "id": instrument_id,
            "name": name,
            "title": name,
            "canvas": {"width": 200, "height": 120},
            "holes": [
                {"id": f"{instrument_id}_H1", "x": 50.0, "y": 60.0, "radius": 6.0},
                {"id": f"{instrument_id}_H2", "x": 90.0, "y": 55.0, "radius": 6.0},
            ],
            "note_order": ["C5", "D5"],
            "note_map": {"C5": [2, 2], "D5": [0, 0]},
            "preferred_range": {"min": "C5", "max": "D5"},
        }
    )


@pytest.fixture
def layout_editor_specs() -> list[InstrumentSpec]:
    return [
        InstrumentSpec.from_dict(
            {
                "id": "test_instrument",
                "name": "Test Instrument",
                "title": "Test Instrument",
                "canvas": {"width": 200, "height": 120},
                "holes": [
                    {"id": "H1", "x": 50.0, "y": 60.0, "radius": 6.0},
                    {"id": "H2", "x": 90.0, "y": 55.0, "radius": 6.0},
                ],
                "windways": [
                    {"id": "Windway", "x": 40.0, "y": 30.0, "width": 16.0, "height": 10.0}
                ],
                "note_order": ["C5", "D5"],
                "note_map": {"C5": [2, 2, 2], "D5": [1, 2, 2]},
                "preferred_range": {"min": "C5", "max": "D5"},
            }
        )
    ]


@pytest.fixture
def layout_editor_switch_specs() -> list[InstrumentSpec]:
    return [
        _simple_spec("alto_c_12", "12-hole instrument"),
        _simple_spec("alto_c_6", "6-hole instrument"),
    ]


@pytest.mark.gui
def test_layout_editor_exposes_half_toggle(layout_editor_specs) -> None:
    root: tk.Tk | None = None
    editor: InstrumentLayoutEditor | None = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        var = tk.BooleanVar(master=root, value=False)
        toggled: list[bool] = []
        viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
        editor = InstrumentLayoutEditor(
            root,
            viewmodel=viewmodel,
            allow_half_var=var,
            on_half_toggle=lambda: toggled.append(var.get()),
        )
        root.update_idletasks()
        buttons = _collect_checkbuttons(editor)
        toggle = next(btn for btn in buttons if btn.cget("text") == "Allow half-holes")
        assert not var.get()
        toggle.invoke()
        assert var.get() is True
        assert toggled == [True]
    finally:
        if editor is not None:
            editor.destroy()
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_switching_instruments_updates_half_toggle(layout_editor_switch_specs) -> None:
    root: tk.Tk | None = None
    editor: InstrumentLayoutEditor | None = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        var = tk.BooleanVar(master=root, value=False)
        viewmodel = InstrumentLayoutEditorViewModel(layout_editor_switch_specs)
        editor = InstrumentLayoutEditor(root, viewmodel=viewmodel, allow_half_var=var)
        root.update_idletasks()

        assert viewmodel.state.instrument_id == "alto_c_12"
        assert var.get() is False

        editor.instrument_var.set(layout_editor_switch_specs[1].name)
        editor._on_instrument_change(None)
        root.update_idletasks()

        assert viewmodel.state.instrument_id == "alto_c_6"
        assert var.get() is True
    finally:
        if editor is not None:
            editor.destroy()
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_layout_editor_omits_half_toggle_without_var(layout_editor_specs) -> None:
    root: tk.Tk | None = None
    editor: InstrumentLayoutEditor | None = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
        editor = InstrumentLayoutEditor(root, viewmodel=viewmodel)
        root.update_idletasks()
        buttons = _collect_checkbuttons(editor)
        assert all(btn.cget("text") != "Allow half-holes" for btn in buttons)
    finally:
        if editor is not None:
            editor.destroy()
        if root is not None:
            root.destroy()


@pytest.mark.gui
def test_half_toggle_updates_viewmodel_state(layout_editor_specs) -> None:
    root: tk.Tk | None = None
    editor: InstrumentLayoutEditor | None = None
    instrument_id = layout_editor_specs[0].instrument_id
    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tkinter display is not available")
        root.withdraw()
        var = tk.BooleanVar(master=root, value=False)
        viewmodel = InstrumentLayoutEditorViewModel(layout_editor_specs)
        editor = InstrumentLayoutEditor(root, viewmodel=viewmodel, allow_half_var=var)
        root.update_idletasks()

        assert instrument_allows_half_holes(instrument_id) is False
        assert viewmodel.state.allow_half_holes is False

        var.set(True)
        editor._handle_half_toggle()

        assert viewmodel.state.allow_half_holes is True
        config = viewmodel.build_config()
        entry = next(
            item for item in config["instruments"] if item["id"] == instrument_id
        )
        assert entry["allow_half_holes"] is True
    finally:
        if editor is not None:
            editor.destroy()
        if root is not None:
            root.destroy()
