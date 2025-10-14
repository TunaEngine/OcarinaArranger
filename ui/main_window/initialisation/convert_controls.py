from __future__ import annotations

import logging
import tkinter as tk
from typing import Dict, Iterable, Sequence

from shared.ttk import ttk

from ocarina_gui.constants import DEFAULT_MAX, DEFAULT_MIN
from ocarina_gui.preferences import (
    ARRANGER_MODES,
    DEFAULT_ARRANGER_MODE,
    Preferences,
    save_preferences,
)

from viewmodels.main_viewmodel import (
    ARRANGER_STRATEGIES,
    ARRANGER_STRATEGY_CURRENT,
    ARRANGER_STRATEGY_STARRED_BEST,
    DEFAULT_ARRANGER_STRATEGY,
)
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerInstrumentSummary

from .arranger_results import ArrangerResultsMixin


logger = logging.getLogger(__name__)


class ConvertControlsMixin(ArrangerResultsMixin):
    """Initialise conversion-related Tk variables and helpers."""

    def _create_convert_controls(self, state) -> None:
        self.input_path = tk.StringVar(master=self, value=state.input_path)
        self.prefer_mode = tk.StringVar(master=self, value=state.prefer_mode)
        self.prefer_flats = tk.BooleanVar(master=self, value=state.prefer_flats)
        self.collapse_chords = tk.BooleanVar(master=self, value=state.collapse_chords)
        self.favor_lower = tk.BooleanVar(master=self, value=state.favor_lower)
        self.transpose_offset = tk.IntVar(master=self, value=state.transpose_offset)
        self.convert_instrument_var = tk.StringVar(
            master=self,
            value=self._instrument_name_by_id.get(self._selected_instrument_id, ""),
        )
        self.range_min = tk.StringVar(master=self, value=state.range_min or DEFAULT_MIN)
        self.range_max = tk.StringVar(master=self, value=state.range_max or DEFAULT_MAX)
        mode_value = state.arranger_mode or DEFAULT_ARRANGER_MODE
        if mode_value not in ARRANGER_MODES:
            mode_value = DEFAULT_ARRANGER_MODE
        self.arranger_mode = tk.StringVar(master=self, value=mode_value)
        strategy_value = state.arranger_strategy or DEFAULT_ARRANGER_STRATEGY
        if strategy_value not in ARRANGER_STRATEGIES:
            strategy_value = DEFAULT_ARRANGER_STRATEGY
        self.arranger_strategy = tk.StringVar(master=self, value=strategy_value)
        self._suppress_arranger_strategy_trace = False
        dp_enabled = bool(getattr(state, "arranger_dp_slack_enabled", False))
        self.arranger_dp_slack = tk.BooleanVar(master=self, value=dp_enabled)
        budgets_state = getattr(state, "arranger_budgets", ArrangerBudgetSettings())
        if not isinstance(budgets_state, ArrangerBudgetSettings):
            budgets_state = ArrangerBudgetSettings()
        budgets_state = budgets_state.normalized()
        self.arranger_budget_octave = tk.IntVar(
            master=self, value=budgets_state.max_octave_edits
        )
        self.arranger_budget_rhythm = tk.IntVar(
            master=self, value=budgets_state.max_rhythm_edits
        )
        self.arranger_budget_substitution = tk.IntVar(
            master=self, value=budgets_state.max_substitutions
        )
        self.arranger_budget_total = tk.IntVar(
            master=self, value=budgets_state.max_steps_per_span
        )
        self._arranger_budget_vars: dict[str, tk.IntVar] = {
            "max_octave_edits": self.arranger_budget_octave,
            "max_rhythm_edits": self.arranger_budget_rhythm,
            "max_substitutions": self.arranger_budget_substitution,
            "max_steps_per_span": self.arranger_budget_total,
        }
        self._suspend_arranger_budget_trace = False
        self._suspend_arranger_dp_trace = False
        self.arranger_show_advanced = tk.BooleanVar(master=self, value=False)
        self._arranger_advanced_frame: ttk.Frame | None = None
        self._suspend_starred_updates = False
        self._starred_instrument_vars: dict[str, tk.BooleanVar] = {}
        self._starred_var_traces: dict[str, str] = {}
        self._starred_checkbox_widgets: dict[str, ttk.Checkbutton] = {}
        self._starred_instrument_container: ttk.Frame | None = None
        self._arranger_summary_container: ttk.Frame | None = None
        self._arranger_summary_body: ttk.Frame | None = None
        self._arranger_summary_placeholder: ttk.Label | None = None
        self._initialise_arranger_results(state)
        self.status = tk.StringVar(master=self, value=state.status_message)
        self._reimport_button: ttk.Button | None = None
        self._last_imported_path: str | None = None
        self._last_import_settings: Dict[str, object] = {}
        self._convert_setting_traces: list[tuple[tk.Variable, str]] = []
        self._suppress_arranger_mode_trace = False
        self._register_convert_setting_var(self.prefer_mode)
        self._register_convert_setting_var(self.prefer_flats)
        self._register_convert_setting_var(self.collapse_chords)
        self._register_convert_setting_var(self.favor_lower)
        self._register_convert_setting_var(self.range_min)
        self._register_convert_setting_var(self.range_max)
        self._register_convert_setting_var(self.convert_instrument_var)
        self._register_convert_setting_var(self.transpose_offset)
        self._register_convert_setting_var(self.arranger_mode)
        self._register_convert_setting_var(self.arranger_strategy)
        self._register_convert_setting_var(self.arranger_dp_slack)
        for var in self._arranger_budget_vars.values():
            self._register_convert_setting_var(var)
        self.arranger_mode.trace_add("write", self._on_arranger_mode_changed)
        self.arranger_strategy.trace_add("write", self._on_arranger_strategy_changed)
        self.arranger_dp_slack.trace_add(
            "write", self._on_arranger_dp_slack_changed
        )
        for key, var in self._arranger_budget_vars.items():
            var.trace_add(
                "write",
                lambda *_args, budget_key=key: self._on_arranger_budget_changed(
                    budget_key
                ),
            )
        self.arranger_show_advanced.trace_add(
            "write", self._on_arranger_show_advanced_changed
        )
        self.arranger_explanation_filter.trace_add(
            "write", self._on_arranger_explanation_filter_changed
        )
        if self._selected_instrument_id:
            self._on_library_instrument_changed(
                self._selected_instrument_id, update_range=False
            )

    def _on_arranger_mode_changed(self, *_args: object) -> None:
        if self._suppress_arranger_mode_trace:
            return
        raw_value = (self.arranger_mode.get() or "").strip().lower()
        if raw_value in {"v2", "best_effort"}:
            normalized = "best_effort"
        elif raw_value in {"v1", "classic"}:
            normalized = DEFAULT_ARRANGER_MODE
        elif raw_value in ARRANGER_MODES:
            normalized = raw_value
        else:
            normalized = DEFAULT_ARRANGER_MODE
        if raw_value != normalized:
            self._suppress_arranger_mode_trace = True
            try:
                self.arranger_mode.set(normalized)
            finally:
                self._suppress_arranger_mode_trace = False
            return

        self._viewmodel.update_settings(arranger_mode=normalized)

        preferences = self.preferences
        if isinstance(preferences, Preferences) and preferences.arranger_mode != normalized:
            preferences.arranger_mode = normalized
            try:
                save_preferences(preferences)
            except Exception:
                logger.warning(
                    "Failed to persist arranger mode preference", extra={"mode": normalized}
                )

        refresh = getattr(self, "_update_arranger_mode_layout", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                logger.exception(
                    "Failed to refresh arranger mode layout", extra={"mode": normalized}
                )
        advanced_refresh = getattr(self, "_update_arranger_advanced_visibility", None)
        if callable(advanced_refresh):
            try:
                advanced_refresh()
            except Exception:
                logger.debug("Advanced arranger visibility update failed", exc_info=True)

    def _on_arranger_strategy_changed(self, *_args: object) -> None:
        if self._suppress_arranger_strategy_trace:
            return
        raw_value = (self.arranger_strategy.get() or "").strip().lower()
        if raw_value in {"current", ARRANGER_STRATEGY_CURRENT}:
            normalized = ARRANGER_STRATEGY_CURRENT
        elif raw_value in {"starred", "starred-best"}:
            normalized = ARRANGER_STRATEGY_STARRED_BEST
        elif raw_value in ARRANGER_STRATEGIES:
            normalized = raw_value
        else:
            normalized = DEFAULT_ARRANGER_STRATEGY
        if raw_value != normalized:
            self._suppress_arranger_strategy_trace = True
            try:
                self.arranger_strategy.set(normalized)
            finally:
                self._suppress_arranger_strategy_trace = False
            return

        self._viewmodel.update_settings(arranger_strategy=normalized)

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

            # Remove variables that are no longer available
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

    def _register_arranger_summary_container(self, container: ttk.Frame) -> None:
        self._arranger_summary_container = container
        headings = [
            "Instrument",
            "",
            "Transpose",
            "Easy",
            "Medium",
            "Hard",
            "Very Hard",
            "Tessitura",
        ]
        self._arranger_summary_column_count = len(headings)
        for column, title in enumerate(headings):
            ttk.Label(container, text=title).grid(
                row=0,
                column=column,
                sticky="w",
                padx=(0, 8),
            )
            weight = 1 if column == 0 else 0
            container.columnconfigure(column, weight=weight)
        body = ttk.Frame(container)
        body.grid(row=1, column=0, columnspan=len(headings), sticky="nsew")
        for column in range(len(headings)):
            body.columnconfigure(column, weight=1 if column == 0 else 0)
        container.rowconfigure(1, weight=1)
        self._arranger_summary_body = body
        self._render_arranger_summary()

    def _render_arranger_summary(
        self, entries: Sequence[ArrangerInstrumentSummary] | None = None
    ) -> None:
        body = self._arranger_summary_body
        if body is None:
            return
        for child in body.winfo_children():
            child.destroy()

        data: Sequence[ArrangerInstrumentSummary]
        if entries is not None:
            data = entries
        else:
            data = getattr(self._viewmodel.state, "arranger_strategy_summary", ())

        column_count = getattr(self, "_arranger_summary_column_count", 0) or 1

        if not data:
            placeholder = ttk.Label(
                body,
                text="Arrange a score to compare instruments.",
                style="Hint.TLabel",
                anchor="w",
                justify="left",
                wraplength=360,
            )
            placeholder.grid(row=0, column=0, columnspan=column_count, sticky="w")
            self._arranger_summary_placeholder = placeholder
            return

        self._arranger_summary_placeholder = None
        for row, summary in enumerate(data, start=0):
            instrument_name = summary.instrument_name or self._instrument_name_by_id.get(
                summary.instrument_id, summary.instrument_id
            )
            ttk.Label(body, text=instrument_name).grid(
                row=row,
                column=0,
                sticky="w",
                padx=(0, 8),
                pady=(0, 2),
            )
            badge_text = "⭐ Winner" if summary.is_winner else ""
            ttk.Label(body, text=badge_text, style="Hint.TLabel").grid(
                row=row,
                column=1,
                sticky="w",
                padx=(0, 8),
                pady=(0, 2),
            )
            ttk.Label(
                body,
                text=f"{summary.transposition:+d}" if summary.transposition else "0",
            ).grid(
                row=row,
                column=2,
                sticky="e",
                padx=(0, 8),
                pady=(0, 2),
            )
            for column_offset, value in enumerate(
                (
                    summary.easy,
                    summary.medium,
                    summary.hard,
                    summary.very_hard,
                    summary.tessitura,
                ),
                start=3,
            ):
                ttk.Label(body, text=f"{value:.2f}").grid(
                    row=row,
                    column=column_offset,
                    sticky="e",
                    padx=(0, 8),
                    pady=(0, 2),
                )

    def _register_arranger_advanced_frame(self, frame: ttk.Frame) -> None:
        self._arranger_advanced_frame = frame
        self._update_arranger_advanced_visibility()

    def _update_arranger_advanced_visibility(self) -> None:
        frame = self._arranger_advanced_frame
        if frame is None:
            return
        visible = bool(self.arranger_show_advanced.get()) and (
            (self.arranger_mode.get() or "") == "best_effort"
        )
        if visible:
            frame.grid()
        else:
            frame.grid_remove()

    def _on_arranger_show_advanced_changed(self, *_args: object) -> None:
        self._update_arranger_advanced_visibility()

    def _on_arranger_dp_slack_changed(self, *_args: object) -> None:
        if self._suspend_arranger_dp_trace:
            return
        try:
            enabled = bool(self.arranger_dp_slack.get())
        except (tk.TclError, AttributeError):
            enabled = False
        self._viewmodel.update_settings(arranger_dp_slack_enabled=enabled)

    def _collect_arranger_budget_values(self) -> ArrangerBudgetSettings:
        def _safe_get(var: tk.IntVar, fallback: int) -> int:
            try:
                return int(var.get())
            except (tk.TclError, ValueError, TypeError, AttributeError):
                return fallback

        return ArrangerBudgetSettings(
            max_octave_edits=_safe_get(self.arranger_budget_octave, 1),
            max_rhythm_edits=_safe_get(self.arranger_budget_rhythm, 1),
            max_substitutions=_safe_get(self.arranger_budget_substitution, 1),
            max_steps_per_span=_safe_get(self.arranger_budget_total, 3),
        )

    def _apply_arranger_budget_vars(self, budgets: ArrangerBudgetSettings) -> None:
        normalized = budgets if isinstance(budgets, ArrangerBudgetSettings) else ArrangerBudgetSettings()
        if not isinstance(budgets, ArrangerBudgetSettings):
            normalized = ArrangerBudgetSettings()
        normalized = normalized.normalized()
        self._suspend_arranger_budget_trace = True
        try:
            self.arranger_budget_octave.set(normalized.max_octave_edits)
            self.arranger_budget_rhythm.set(normalized.max_rhythm_edits)
            self.arranger_budget_substitution.set(normalized.max_substitutions)
            self.arranger_budget_total.set(normalized.max_steps_per_span)
        finally:
            self._suspend_arranger_budget_trace = False

    def _on_arranger_budget_changed(self, _key: str) -> None:
        if self._suspend_arranger_budget_trace:
            return
        budgets = self._collect_arranger_budget_values()
        self._viewmodel.update_settings(arranger_budgets=budgets)

    def reset_arranger_budgets(self) -> None:
        defaults = ArrangerBudgetSettings()
        self._viewmodel.update_settings(arranger_budgets=defaults)
        self._apply_arranger_budget_vars(defaults)

    def _sync_arranger_budgets_from_state(
        self, budgets: ArrangerBudgetSettings | None
    ) -> None:
        if budgets is None:
            budgets = ArrangerBudgetSettings()
        self._apply_arranger_budget_vars(budgets)



__all__ = ["ConvertControlsMixin"]
