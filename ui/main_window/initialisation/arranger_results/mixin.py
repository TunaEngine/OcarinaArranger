"""Arranger v2 results helpers shared between mixins and UI builders."""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Iterable

from shared.ttk import ttk

logger = logging.getLogger(__name__)

from viewmodels.arranger_models import (
    ArrangerEditBreakdown,
    ArrangerExplanationRow,
    ArrangerResultSummary,
    ArrangerTelemetryHint,
)


class ArrangerResultsMixin:
    """Expose reusable helpers for arranger v2 result widgets."""

    def _initialise_arranger_results(self, state) -> None:  # noqa: ANN001 - mixin hook
        self._arranger_results_notebook: ttk.Notebook | None = None
        self.arranger_summary_status = tk.StringVar(
            master=self,
            value="Arrange a score to view best-effort results.",
        )
        self.arranger_summary_transposition = tk.StringVar(master=self, value="–")
        self.arranger_summary_easy = tk.StringVar(master=self, value="–")
        self.arranger_summary_medium = tk.StringVar(master=self, value="–")
        self.arranger_summary_hard = tk.StringVar(master=self, value="–")
        self.arranger_summary_very_hard = tk.StringVar(master=self, value="–")
        self.arranger_summary_tessitura = tk.StringVar(master=self, value="–")
        self.arranger_summary_starting = tk.StringVar(master=self, value="–")
        self.arranger_summary_final = tk.StringVar(master=self, value="–")
        self.arranger_summary_threshold = tk.StringVar(master=self, value="–")
        self.arranger_summary_delta = tk.StringVar(master=self, value="–")
        self.arranger_applied_steps = tk.StringVar(master=self, value="No edits applied.")
        self.arranger_edits_total = tk.StringVar(master=self, value="–")
        self.arranger_edits_octave = tk.StringVar(master=self, value="–")
        self.arranger_edits_rhythm = tk.StringVar(master=self, value="–")
        self.arranger_edits_substitution = tk.StringVar(master=self, value="–")
        self.arranger_explanation_filter = tk.StringVar(master=self, value="all")
        self.arranger_explanation_detail = tk.StringVar(
            master=self,
            value="Select an explanation to view before/after note counts.",
        )
        self._arranger_explanations_tree: ttk.Treeview | None = None
        self._arranger_explanation_filter_widget: ttk.Combobox | None = None
        self._arranger_explanation_rows: tuple[ArrangerExplanationRow, ...] = ()
        self._arranger_explanation_row_map: dict[str, ArrangerExplanationRow] = {}
        self._arranger_telemetry_container: ttk.Frame | None = None
        self._arranger_telemetry_placeholder: ttk.Label | None = None
        self._arranger_progress_frame: ttk.Frame | None = None
        self._arranger_progress_bar: ttk.Progressbar | None = None
        self._arranger_progress_previous_status: str | None = None
        self._arranger_progress_active_message: str | None = None
        self.arranger_progress_percent = tk.StringVar(master=self, value="0%")
        self.arranger_progress_value = tk.DoubleVar(master=self, value=0.0)
        self.arranger_explanation_filter.trace_add(
            "write", self._on_arranger_explanation_filter_changed
        )

    def _register_arranger_results_notebook(self, notebook: ttk.Notebook) -> None:
        self._arranger_results_notebook = notebook
        self._refresh_arranger_results_from_state()

    def _register_arranger_progress_widgets(
        self, frame: ttk.Frame, progress: ttk.Progressbar
    ) -> None:
        self._arranger_progress_frame = frame
        self._arranger_progress_bar = progress
        try:
            progress.configure(variable=self.arranger_progress_value)
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        try:
            frame.grid_remove()
        except (tk.TclError, RuntimeError, AttributeError):
            pass

    def _set_arranger_results_loading(
        self,
        loading: bool,
        *,
        message: str | None = None,
        restore_status: bool = True,
    ) -> None:
        frame = self._arranger_progress_frame
        bar = self._arranger_progress_bar
        if loading:
            if restore_status:
                try:
                    self._arranger_progress_previous_status = self.arranger_summary_status.get()
                except (tk.TclError, RuntimeError, AttributeError):
                    self._arranger_progress_previous_status = None
            if message is not None:
                try:
                    self.arranger_summary_status.set(message)
                except (tk.TclError, RuntimeError, AttributeError):
                    pass
            self._arranger_progress_active_message = message
            try:
                self.arranger_progress_value.set(0.0)
            except (tk.TclError, RuntimeError, AttributeError):
                pass
            try:
                self.arranger_progress_percent.set("0%")
            except (tk.TclError, RuntimeError, AttributeError):
                pass
            if frame is not None:
                try:
                    if frame.winfo_manager() != "grid":
                        frame.grid()
                except (tk.TclError, RuntimeError, AttributeError):
                    pass
            return

        if bar is not None:
            try:
                bar.configure(value=0.0)
            except (tk.TclError, RuntimeError, AttributeError):
                pass
        if frame is not None:
            try:
                if frame.winfo_manager() == "grid":
                    frame.grid_remove()
            except (tk.TclError, RuntimeError, AttributeError):
                pass
        if restore_status and self._arranger_progress_previous_status is not None:
            try:
                self.arranger_summary_status.set(
                    self._arranger_progress_previous_status
                )
            except (tk.TclError, RuntimeError, AttributeError):
                pass
        self._arranger_progress_previous_status = None
        self._arranger_progress_active_message = None
        try:
            self.arranger_progress_value.set(0.0)
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        try:
            self.arranger_progress_percent.set("0%")
        except (tk.TclError, RuntimeError, AttributeError):
            pass

    def _update_arranger_progress(
        self, percent: float, message: str | None = None
    ) -> None:
        try:
            value = float(percent)
        except (TypeError, ValueError):
            value = 0.0
        value = max(0.0, min(100.0, value))
        percent_str = f"{value:.0f}%"
        
        # Update progress bar value
        try:
            self.arranger_progress_value.set(value)
        except (tk.TclError, RuntimeError, AttributeError):
            logger.debug("Failed to update arranger progress variable", exc_info=True)

        # Update progress bar directly to ensure immediate effect
        bar = self._arranger_progress_bar
        if bar is not None:
            try:
                bar.configure(value=value)
            except (tk.TclError, RuntimeError, AttributeError):
                logger.debug("Failed to configure arranger progress bar", exc_info=True)
        
        # Update message
        if message is not None:
            self._arranger_progress_active_message = message
        active_message = self._arranger_progress_active_message
        if active_message is not None:
            self.arranger_summary_status.set(active_message)
        
        # Update percentage label
        self.arranger_progress_percent.set(percent_str)

    def _register_arranger_explanations_tree(self, tree: ttk.Treeview) -> None:
        self._arranger_explanations_tree = tree
        tree.bind("<<TreeviewSelect>>", self._on_arranger_explanation_selected)
        self._populate_arranger_explanations_tree()

    def _register_arranger_explanation_filter(self, widget: ttk.Combobox) -> None:
        self._arranger_explanation_filter_widget = widget
        widget.configure(state="readonly")
        widget.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_arranger_explanation_filter_changed(),
        )
        self._apply_arranger_explanations(self._arranger_explanation_rows)

    def _register_arranger_telemetry_container(self, container: ttk.Frame) -> None:
        self._arranger_telemetry_container = container
        self._apply_arranger_telemetry(self._viewmodel.state.arranger_telemetry)

    def _refresh_arranger_results_from_state(self) -> None:
        state = getattr(self._viewmodel, "state", None)
        if state is None:
            return
        self._apply_arranger_result_summary(state.arranger_result_summary)
        self._apply_arranger_explanations(state.arranger_explanations)
        self._apply_arranger_telemetry(state.arranger_telemetry)

    def _apply_arranger_result_summary(
        self, summary: ArrangerResultSummary | None
    ) -> None:
        self._set_arranger_results_loading(False, restore_status=False)
        if summary is None:
            self.arranger_summary_status.set(
                "Arrange a score to view best-effort results."
            )
            for var in (
                self.arranger_summary_transposition,
                self.arranger_summary_easy,
                self.arranger_summary_medium,
                self.arranger_summary_hard,
                self.arranger_summary_very_hard,
                self.arranger_summary_tessitura,
                self.arranger_summary_starting,
                self.arranger_summary_final,
                self.arranger_summary_threshold,
                self.arranger_summary_delta,
            ):
                var.set("–")
            for var in (
                self.arranger_edits_total,
                self.arranger_edits_octave,
                self.arranger_edits_rhythm,
                self.arranger_edits_substitution,
            ):
                var.set("–")
            self.arranger_applied_steps.set("No edits applied.")
            return

        instrument_name = summary.instrument_name or self._instrument_name_by_id.get(
            summary.instrument_id,
            summary.instrument_id,
        )
        comparison = (
            f"{summary.final_difficulty:.2f} ≤ {summary.difficulty_threshold:.2f}"
            if summary.met_threshold
            else f"{summary.final_difficulty:.2f} > {summary.difficulty_threshold:.2f}"
        )
        status_prefix = "Met" if summary.met_threshold else "Above"
        transpose_text = f"{summary.transposition:+d}" if summary.transposition else "0"
        self.arranger_summary_status.set(
            (
                f"{instrument_name} {status_prefix.lower()} difficulty threshold "
                f"({comparison}); transposition {transpose_text}."
            )
        )
        self.arranger_summary_transposition.set(transpose_text)
        self.arranger_summary_easy.set(f"{summary.easy:.2f}")
        self.arranger_summary_medium.set(f"{summary.medium:.2f}")
        self.arranger_summary_hard.set(f"{summary.hard:.2f}")
        self.arranger_summary_very_hard.set(f"{summary.very_hard:.2f}")
        self.arranger_summary_tessitura.set(f"{summary.tessitura:.2f}")
        self.arranger_summary_starting.set(f"{summary.starting_difficulty:.2f}")
        self.arranger_summary_final.set(f"{summary.final_difficulty:.2f}")
        self.arranger_summary_threshold.set(f"{summary.difficulty_threshold:.2f}")
        self.arranger_summary_delta.set(f"{summary.difficulty_delta:+.2f}")
        steps_text = (
            ", ".join(summary.applied_steps)
            if summary.applied_steps
            else "No edits applied."
        )
        self.arranger_applied_steps.set(steps_text)
        edits = summary.edits if isinstance(summary.edits, ArrangerEditBreakdown) else ArrangerEditBreakdown()
        self.arranger_edits_total.set(str(int(edits.total)))
        self.arranger_edits_octave.set(str(int(edits.octave)))
        self.arranger_edits_rhythm.set(str(int(edits.rhythm)))
        self.arranger_edits_substitution.set(str(int(edits.substitution)))

    def _apply_arranger_explanations(
        self, explanations: Iterable[ArrangerExplanationRow] | tuple[ArrangerExplanationRow, ...]
    ) -> None:
        self._arranger_explanation_rows = tuple(explanations or ())
        widget = self._arranger_explanation_filter_widget
        codes = sorted({row.reason_code for row in self._arranger_explanation_rows})
        values = ["all"] + codes
        if widget is not None:
            widget.configure(values=values)
        current_filter = (self.arranger_explanation_filter.get() or "all").lower()
        if current_filter not in values:
            self.arranger_explanation_filter.set("all")
        self._populate_arranger_explanations_tree()

    def _populate_arranger_explanations_tree(self) -> None:
        tree = self._arranger_explanations_tree
        if tree is None:
            return
        tree.delete(*tree.get_children())
        self._arranger_explanation_row_map.clear()
        filter_value = (self.arranger_explanation_filter.get() or "all").lower()
        filtered_rows = [
            row
            for row in self._arranger_explanation_rows
            if filter_value in {"", "all", row.reason_code.lower()}
        ]
        if not filtered_rows:
            self.arranger_explanation_detail.set(
                "No explanation events recorded for the current filter."
            )
            return
        self.arranger_explanation_detail.set(
            "Select an explanation to view before/after note counts."
        )
        for row in filtered_rows:
            item_id = tree.insert(
                "",
                "end",
                values=(
                    row.bar,
                    row.action,
                    row.reason,
                    f"{row.difficulty_delta:+.2f}",
                    f"{row.before_note_count} → {row.after_note_count}",
                ),
            )
            self._arranger_explanation_row_map[item_id] = row

    def _on_arranger_explanation_filter_changed(self, *_args: object) -> None:
        self._populate_arranger_explanations_tree()

    def _on_arranger_explanation_selected(self, _event: object | None = None) -> None:
        tree = self._arranger_explanations_tree
        if tree is None:
            return
        selection = tree.selection()
        if not selection:
            self.arranger_explanation_detail.set(
                "Select an explanation to view before/after note counts."
            )
            return
        item_id = selection[0]
        row = self._arranger_explanation_row_map.get(item_id)
        if row is None:
            self.arranger_explanation_detail.set(
                "Select an explanation to view before/after note counts."
            )
            return
        span_text = f", {row.span}" if row.span else ""
        self.arranger_explanation_detail.set(
            f"Bar {row.bar}{span_text}: {row.before_note_count} → {row.after_note_count} notes (Δ {row.difficulty_delta:+.2f})."
        )

    def _apply_arranger_telemetry(
        self, telemetry: Iterable[ArrangerTelemetryHint] | tuple[ArrangerTelemetryHint, ...]
    ) -> None:
        container = self._arranger_telemetry_container
        if container is None:
            return
        for child in container.winfo_children():
            child.destroy()
        hints = tuple(telemetry or ())
        if not hints:
            placeholder = ttk.Label(
                container,
                text="No telemetry available yet.",
                style="Hint.TLabel",
                wraplength=320,
                anchor="w",
                justify="left",
            )
            placeholder.grid(row=0, column=0, sticky="nw")
            self._arranger_telemetry_placeholder = placeholder
            return
        self._arranger_telemetry_placeholder = None
        for index, hint in enumerate(hints):
            row_container = ttk.Frame(container)
            row_container.grid(row=index, column=0, sticky="ew", pady=(0, 4))
            row_container.columnconfigure(1, weight=1)
            ttk.Label(
                row_container,
                text=f"{hint.category}:",
                style="Emphasis.TLabel",
            ).grid(row=0, column=0, sticky="nw", padx=(0, 4))
            ttk.Label(
                row_container,
                text=hint.message,
                wraplength=320,
                justify="left",
                anchor="w",
            ).grid(row=0, column=1, sticky="nw")

