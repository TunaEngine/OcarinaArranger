"""Summary table helpers for convert controls."""

from __future__ import annotations

import math
import re
from typing import Sequence

from shared.ttk import ttk

from viewmodels.arranger_models import ArrangerInstrumentSummary


class _SummaryTreeview(ttk.Treeview):
    """Treeview variant that preserves text values when reading them back."""

    @staticmethod
    def _stringify(value: object) -> str:
        return value if isinstance(value, str) else str(value)

    def item(self, item: str, option: str | None = None, **kw: object):  # type: ignore[override]
        result = super().item(item, option=option, **kw)
        if kw:
            return result
        if option is None:
            if isinstance(result, dict):
                values = result.get("values")
                if values:
                    result = dict(result)
                    result["values"] = tuple(self._stringify(value) for value in values)
            return result
        if option == "values":
            if isinstance(result, (tuple, list)):
                return tuple(self._stringify(value) for value in result)
        return result


class ArrangerSummaryControlsMixin:
    """Renders arranger comparison summaries."""

    _arranger_summary_container: ttk.Frame | None = None
    _arranger_summary_body: ttk.Frame | None = None
    _arranger_summary_tree: ttk.Treeview | None = None
    _arranger_summary_column_keys: tuple[str, ...] = ()
    _arranger_summary_placeholder: ttk.Label | None = None

    def _register_arranger_summary_container(self, container: ttk.Frame) -> None:
        self._arranger_summary_container = container
        headings = (
            ("instrument", "Instrument"),
            ("status", "Status"),
            ("transpose", "Transpose"),
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
            ("very_hard", "Very Hard"),
            ("tessitura", "Tessitura"),
        )
        self._arranger_summary_column_keys = tuple(key for key, _ in headings)

        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        body = ttk.Frame(container)
        body.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        tree = _SummaryTreeview(
            body,
            columns=self._arranger_summary_column_keys,
            show="headings",
            selectmode="none",
            height=6,
        )
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        for key, title in headings:
            anchor = "w" if key in {"instrument", "status"} else "e"
            stretch = key in {"instrument", "status"}
            width = 170 if key == "instrument" else 110 if key == "status" else 80
            tree.heading(key, text=title, anchor=anchor)
            tree.column(
                key,
                anchor=anchor,
                stretch=stretch,
                width=width,
                minwidth=60,
            )

        tree.tag_configure("winner", font=("TkDefaultFont", 9, "bold"))

        self._arranger_summary_body = body
        self._arranger_summary_tree = tree
        self._render_arranger_summary()

    def _render_arranger_summary(
        self, entries: Sequence[ArrangerInstrumentSummary] | None = None
    ) -> None:
        body = self._arranger_summary_body
        tree = self._arranger_summary_tree
        if body is None or tree is None:
            return
        tree.delete(*tree.get_children())

        data: Sequence[ArrangerInstrumentSummary]
        if entries is not None:
            data = entries
        else:
            data = getattr(self._viewmodel.state, "arranger_strategy_summary", ())

        if not data:
            tree.grid_remove()
            placeholder = self._arranger_summary_placeholder
            if placeholder is not None:
                destroy = getattr(placeholder, "destroy", None)
                if callable(destroy):
                    try:
                        destroy()
                    except Exception:
                        pass
            placeholder = self._create_arranger_summary_placeholder(body)
            self._arranger_summary_placeholder = placeholder
            return

        placeholder = self._arranger_summary_placeholder
        if placeholder is not None:
            try:
                placeholder.destroy()
            except Exception:
                pass
        self._arranger_summary_placeholder = None
        if not tree.winfo_ismapped():
            tree.grid(row=0, column=0, sticky="nsew")

        current_id = getattr(self._viewmodel.state, "instrument_id", "")
        for summary in data:
            instrument_name = summary.instrument_name or self._instrument_name_by_id.get(
                summary.instrument_id, summary.instrument_id
            )
            status_tokens: list[str] = []
            if summary.is_winner:
                status_tokens.append("⭐ Winner")
            if current_id and summary.instrument_id == current_id:
                status_tokens.append("Current")
            status_text = " · ".join(status_tokens)
            transposition_text = self._format_transposition(summary.transposition)
            values = (
                instrument_name,
                status_text,
                transposition_text,
                f"{summary.easy:.2f}",
                f"{summary.medium:.2f}",
                f"{summary.hard:.2f}",
                f"{summary.very_hard:.2f}",
                f"{summary.tessitura:.2f}",
            )
            tags = ("winner",) if summary.is_winner else ()
            tree.insert("", "end", values=values, tags=tags)

        tree.yview_moveto(0.0)

    @staticmethod
    def _format_transposition(value: object) -> str:
        """Render the summary transposition column consistently."""

        if value is None:
            return "0"

        original_text: str | None = None
        numeric_value: float

        numeric_source: str | None = None

        if isinstance(value, str):
            original_text = value.strip()
            if not original_text:
                return "0"
            match = re.search(r"[-+]?\d+(?:\.\d+)?", original_text)
            if match is not None:
                numeric_source = match.group(0)
            candidate = numeric_source if numeric_source is not None else original_text
        else:
            candidate = value

        try:
            numeric_value = float(candidate)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            if original_text is not None:
                return original_text
            return str(value)

        if not math.isfinite(numeric_value):
            return original_text or str(value)

        if numeric_value.is_integer():
            numeric_int = int(numeric_value)
            if numeric_int == 0:
                return "0"
            return f"{numeric_int:+d}"

        return f"{numeric_value:+g}"

    def _create_arranger_summary_placeholder(self, body: ttk.Frame):
        message = "Arrange a score to compare instruments."
        if getattr(self, "_headless", False):
            try:
                from ocarina_gui.headless.widgets import HeadlessLabel
            except Exception:  # pragma: no cover - fallback to ttk.Label
                placeholder = ttk.Label(
                    body,
                    text=message,
                    style="Hint.TLabel",
                    anchor="w",
                    justify="left",
                    wraplength=360,
                )
                placeholder.grid(row=0, column=0, sticky="nw")
                return placeholder
            placeholder = HeadlessLabel(
                text=message,
                style="Hint.TLabel",
                anchor="w",
                justify="left",
                wraplength=360,
            )
            placeholder.grid(row=0, column=0, sticky="nw")
            return placeholder
        placeholder = ttk.Label(
            body,
            text=message,
            style="Hint.TLabel",
            anchor="w",
            justify="left",
            wraplength=360,
        )
        placeholder.grid(row=0, column=0, sticky="nw")
        return placeholder


__all__ = ["ArrangerSummaryControlsMixin"]
