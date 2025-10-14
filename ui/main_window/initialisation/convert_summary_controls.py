"""Summary table helpers for convert controls."""

from __future__ import annotations

from typing import Sequence

from shared.ttk import ttk

from viewmodels.arranger_models import ArrangerInstrumentSummary


class ArrangerSummaryControlsMixin:
    """Renders arranger comparison summaries."""

    _arranger_summary_container: ttk.Frame | None = None
    _arranger_summary_body: ttk.Frame | None = None
    _arranger_summary_column_count: int = 0
    _arranger_summary_placeholder: ttk.Label | None = None

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


__all__ = ["ArrangerSummaryControlsMixin"]
