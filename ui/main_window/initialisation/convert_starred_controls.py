"""Starred instrument management for the convert controls."""

from __future__ import annotations

import tkinter as tk
from typing import Iterable

from shared.ttk import ttk


class ArrangerStarredControlsMixin:
    """Provides starred instrument selection helpers."""

    _starred_instrument_container: ttk.Frame | None = None

    def _register_starred_container(self, container: ttk.Frame) -> None:
        self._starred_instrument_container = container
        self._refresh_starred_instrument_controls()

    def _refresh_starred_instrument_controls(self) -> None:
        container = self._starred_instrument_container
        if container is None:
            return

        for child in container.winfo_children():
            child.destroy()

        starred_ids = set(getattr(self._viewmodel.state, "starred_instrument_ids", ()))
        available = sorted(self._instrument_name_by_id.items(), key=lambda item: item[1].lower())
        available_ids = {instrument_id for instrument_id, _ in available}

        if not available:
            placeholder = ttk.Label(
                container,
                text="No instruments available.",
                style="Hint.TLabel",
            )
            placeholder.grid(row=0, column=0, sticky="w")
            self._starred_checkbox_widgets = {}
            return

        self._suspend_starred_updates = True
        try:
            for index, (instrument_id, instrument_name) in enumerate(available):
                var = self._starred_instrument_vars.get(instrument_id)
                if var is None:
                    var = tk.BooleanVar(master=self, value=instrument_id in starred_ids)
                    trace_id = var.trace_add(
                        "write",
                        lambda *_args, instrument_id=instrument_id: self._on_starred_var_changed(
                            instrument_id
                        ),
                    )
                    self._starred_instrument_vars[instrument_id] = var
                    self._starred_var_traces[instrument_id] = trace_id
                    self._register_convert_setting_var(var)
                else:
                    desired = instrument_id in starred_ids
                    if bool(var.get()) != desired:
                        var.set(desired)

                check = ttk.Checkbutton(
                    container,
                    text=instrument_name,
                    variable=var,
                )
                check.grid(row=index, column=0, sticky="w", pady=(0, 2))
                self._starred_checkbox_widgets[instrument_id] = check

            for instrument_id in list(self._starred_instrument_vars.keys()):
                if instrument_id in available_ids:
                    continue
                var = self._starred_instrument_vars.pop(instrument_id)
                trace_id = self._starred_var_traces.pop(instrument_id, None)
                if trace_id:
                    try:
                        var.trace_remove("write", trace_id)
                    except Exception:
                        pass
        finally:
            self._suspend_starred_updates = False

    def _on_starred_var_changed(self, instrument_id: str) -> None:
        if self._suspend_starred_updates:
            return
        var = self._starred_instrument_vars.get(instrument_id)
        if var is None:
            return
        selected = bool(var.get())
        starred = set(getattr(self._viewmodel.state, "starred_instrument_ids", ()))
        if selected:
            starred.add(instrument_id)
        else:
            starred.discard(instrument_id)
        ordered = tuple(
            iid
            for iid in self._instrument_name_by_id
            if iid in starred
        )
        self._viewmodel.update_settings(starred_instrument_ids=ordered)

    def _sync_starred_instruments_from_state(self, starred_ids: Iterable[str] | None) -> None:
        self._refresh_starred_instrument_controls()
        if starred_ids is None:
            starred_set: set[str] = set()
        else:
            starred_set = set(starred_ids)
        self._suspend_starred_updates = True
        try:
            for instrument_id, var in self._starred_instrument_vars.items():
                desired = instrument_id in starred_set
                if bool(var.get()) != desired:
                    var.set(desired)
        finally:
            self._suspend_starred_updates = False


__all__ = ["ArrangerStarredControlsMixin"]
