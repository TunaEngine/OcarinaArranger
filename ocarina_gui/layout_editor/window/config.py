"""Persistence and lifecycle helpers for the layout editor window."""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from ...fingering import (
    InstrumentSpec,
    get_available_instruments,
    get_instrument,
    update_library_from_config,
)


LOGGER = logging.getLogger(__name__)


def _resolve_instrument_entry(
    config: Mapping[str, object], instrument_id: str
) -> Dict[str, object] | None:
    """Return a defensive copy of the matching instrument entry, if present."""

    instruments = config.get("instruments")
    if isinstance(instruments, Mapping):
        entry = instruments.get(instrument_id)
        if isinstance(entry, Mapping):
            return dict(entry)

    if isinstance(instruments, Sequence) and not isinstance(instruments, (str, bytes)):
        for item in instruments:
            if not isinstance(item, Mapping):
                continue
            entry_id = str(item.get("id", ""))
            if entry_id == instrument_id:
                return dict(item)

    return None


class _LayoutEditorConfigMixin:
    """Operations concerned with loading, saving and closing the editor."""

    def _load_specs(self) -> tuple[InstrumentSpec, ...]:
        return tuple(
            get_instrument(choice.instrument_id) for choice in get_available_instruments()
        )

    def _apply_config_to_library(
        self,
        config: Dict[str, object],
        *,
        instrument_id: Optional[str] = None,
        error_title: str = "Apply failed",
        failure_message_prefix: str | None = None,
        refresh_warning_message: str = "Layout applied but UI refresh failed: {exc}",
    ) -> bool:
        target_id = instrument_id or self._viewmodel.state.instrument_id
        payload = copy.deepcopy(config)
        try:
            update_library_from_config(payload, current_instrument_id=target_id)
        except ValueError as exc:
            message = str(exc) if failure_message_prefix is None else f"{failure_message_prefix}{exc}"
            messagebox.showerror(error_title, message, parent=self)
            return False
        if self._on_config_saved is not None:
            try:
                self._on_config_saved(copy.deepcopy(config), target_id)
            except Exception as exc:  # pragma: no cover - UI callback best effort
                messagebox.showwarning(
                    "Refresh warning",
                    refresh_warning_message.format(exc=exc),
                    parent=self,
                )
        return True

    def _save_json(self) -> None:
        config = self._viewmodel.build_config()
        text = json.dumps(config, indent=2)
        initial = Path(__file__).parent / "config" / "fingering_config.json"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save fingering configuration",
            defaultextension=".json",
            initialfile=initial.name,
            initialdir=initial.parent,
            filetypes=(("JSON Files", "*.json"), ("All Files", "*")),
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save configuration: {exc}")
            return
        if not self._apply_config_to_library(
            config,
            failure_message_prefix="Configuration saved but not applied: ",
            refresh_warning_message="Layout saved but UI refresh failed: {exc}",
        ):
            return
        self._viewmodel.mark_clean()
        self._status_var.set(f"Saved to {path}")
        self._update_dirty_indicator()

    def _load_json(self) -> None:
        initial = Path(__file__).parent / "config" / "fingering_config.json"
        path = filedialog.askopenfilename(
            parent=self,
            title="Load fingering configuration",
            defaultextension=".json",
            initialfile=initial.name,
            initialdir=initial.parent,
            filetypes=(("JSON Files", "*.json"), ("All Files", "*")),
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Import failed", f"Could not read configuration: {exc}", parent=self)
            return
        self._import_config_text(text, source=path)

    def _export_instrument(self) -> None:
        state = self._viewmodel.state
        config = self._viewmodel.build_config()
        instrument_id = state.instrument_id
        instrument = _resolve_instrument_entry(config, instrument_id)
        if instrument is None:
            messagebox.showerror(
                "Export failed",
                "Current instrument configuration is missing from the data set.",
                parent=self,
            )
            return
        text = json.dumps(instrument, indent=2)
        initial = Path(__file__).parent / "config" / f"{instrument_id}.json"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export instrument",
            defaultextension=".json",
            initialfile=initial.name,
            initialdir=initial.parent,
            filetypes=(("JSON Files", "*.json"), ("All Files", "*")),
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not write instrument: {exc}", parent=self)
            return
        self._status_var.set(f"Exported instrument '{state.name}' to {path}")

    def _import_instrument(self) -> None:
        initial = Path(__file__).parent / "config"
        path = filedialog.askopenfilename(
            parent=self,
            title="Import instrument",
            defaultextension=".json",
            initialdir=initial,
            filetypes=(("JSON Files", "*.json"), ("All Files", "*")),
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Import failed", f"Could not read instrument: {exc}", parent=self)
            return

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Import failed", f"Invalid JSON: {exc}", parent=self)
            return
        if not isinstance(data, dict):
            messagebox.showerror("Import failed", "Instrument data must be a JSON object", parent=self)
            return

        instrument_id = str(data.get("id", "")).strip()
        conflict_strategy = "error"
        if instrument_id and instrument_id in dict(self._viewmodel.choices()):
            result = messagebox.askyesnocancel(
                "Instrument exists",
                (
                    "Instrument '{instrument}' already exists.\n"
                    "Choose 'Yes' to replace, 'No' to import a copy, or 'Cancel' to abort."
                ).format(instrument=instrument_id),
                parent=self,
            )
            if result is None:
                return
            conflict_strategy = "replace" if result else "copy"

        try:
            state = self._viewmodel.import_instrument(data, conflict_strategy=conflict_strategy)
        except ValueError as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return

        self._refresh_all()
        self._status_var.set(f"Imported instrument '{state.name}' from {path}")
        self._update_dirty_indicator()

    def _import_config_text(self, text: str, *, source: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Import failed", f"Invalid JSON: {exc}", parent=self)
            return
        if not isinstance(data, dict):
            messagebox.showerror("Import failed", "Configuration must be a JSON object", parent=self)
            return
        self._apply_config(data, source=source)

    def _apply_config(self, config: Dict[str, object], *, source: str) -> None:
        try:
            self._viewmodel.load_config(
                config,
                current_instrument_id=self._viewmodel.state.instrument_id,
            )
        except ValueError as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        if not self._apply_config_to_library(
            config,
            refresh_warning_message="Layout imported but UI refresh failed: {exc}",
        ):
            return

        self._refresh_all()
        self._status_var.set(f"Loaded from {source}")
        self._update_dirty_indicator()

    def _apply_and_close(self) -> None:
        config = self._viewmodel.build_config()
        if not self._apply_config_to_library(config):
            return
        self._viewmodel.mark_clean()
        self._update_dirty_indicator()
        self.destroy()

    def _cancel_edits(self) -> None:
        if not self._initial_config:
            self.destroy()
            return
        if not self._apply_config_to_library(
            self._initial_config,
            instrument_id=self._initial_instrument_id,
            error_title="Cancel layout edits",
            refresh_warning_message="Layout restored but UI refresh failed: {exc}",
        ):
            return
        try:
            self._viewmodel.load_config(
                copy.deepcopy(self._initial_config),
                current_instrument_id=self._initial_instrument_id,
            )
        except ValueError:
            pass
        else:
            self._viewmodel.mark_clean()
            self._update_dirty_indicator()
        self.destroy()

    def _on_close_request(self) -> None:
        if self._viewmodel.is_dirty():
            if not messagebox.askyesno(
                "Close editor",
                "There are unsaved changes. Close without saving?",
                parent=self,
            ):
                return
        self.destroy()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return

        cancel_callbacks = getattr(self, "_cancel_footer_layout_callbacks", None)
        if callable(cancel_callbacks):
            try:
                cancel_callbacks()
            except Exception:
                LOGGER.debug("Failed to cancel footer layout callbacks on destroy", exc_info=True)

        callback = self._on_close
        self._on_close = None
        if callable(callback):
            callback()
