"""Preview builder helpers."""

from __future__ import annotations

import tkinter as tk

import pytest

from ocarina_gui.ui_builders import preview


class FakeStyle:
    def __init__(self, layouts: dict[str, object] | None = None, raise_missing: bool = False):
        self.layouts = dict(layouts or {})
        self.raise_missing = raise_missing

    def layout(self, name: str, layout: object | None = None) -> object:
        if layout is not None:
            self.layouts[name] = layout
            return layout

        if name not in self.layouts:
            if self.raise_missing:
                raise tk.TclError(f"Layout {name} not found")
            return ()

        return self.layouts[name]


def test_prepare_scale_bootstyle_returns_existing_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview, "is_bootstrap_enabled", lambda: True)
    style = FakeStyle({"info.Horizontal.TScale": ("existing",)})

    bootstyle = preview._prepare_scale_bootstyle(style)

    assert bootstyle == "info"
    assert style.layouts["info.Horizontal.TScale"] == ("existing",)


def test_prepare_scale_bootstyle_clones_horizontal_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview, "is_bootstrap_enabled", lambda: True)
    base_layout = ("base",)
    style = FakeStyle({"Horizontal.TScale": base_layout})

    bootstyle = preview._prepare_scale_bootstyle(style)

    assert bootstyle == "info"
    assert style.layouts["info.Horizontal.TScale"] == base_layout


def test_prepare_scale_bootstyle_handles_missing_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview, "is_bootstrap_enabled", lambda: True)
    style = FakeStyle({}, raise_missing=True)

    bootstyle = preview._prepare_scale_bootstyle(style)

    assert bootstyle is None


def test_prepare_scale_bootstyle_bails_without_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview, "is_bootstrap_enabled", lambda: False)

    bootstyle = preview._prepare_scale_bootstyle(FakeStyle())

    assert bootstyle is None
