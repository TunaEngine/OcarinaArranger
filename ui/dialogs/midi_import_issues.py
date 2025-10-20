from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ocarina_tools.midi_import.models import MidiImportReport
from ocarina_gui.themes import apply_theme_to_toplevel
from shared.tkinter_geometry import center_window_over_parent


class MidiImportIssuesDialog(tk.Toplevel):
    """Modal dialog summarising lenient MIDI import recovery details."""

    def __init__(
        self,
        *,
        master: tk.Widget | None,
        report: MidiImportReport,
    ) -> None:
        if master is None:
            master = tk._default_root  # type: ignore[attr-defined]
        super().__init__(master=master)
        self.title("Lenient MIDI import details")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_theme_to_toplevel(self)

        container = ttk.Frame(self, padding=16, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        summary_label = ttk.Label(
            container,
            text=self._build_summary(report),
            wraplength=420,
            justify="left",
        )
        summary_label.grid(row=0, column=0, sticky="w")

        tree = ttk.Treeview(
            container,
            columns=("track", "tick", "offset", "detail"),
            show="headings",
            height=8,
        )
        tree.grid(row=1, column=0, sticky="nsew", pady=(12, 12))
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        headings = (
            ("track", "Track"),
            ("tick", "Tick"),
            ("offset", "Offset"),
            ("detail", "Issue"),
        )
        for key, title in headings:
            anchor = "e" if key in {"tick", "offset"} else "w"
            width = 80 if key != "detail" else 360
            tree.heading(key, text=title, anchor=anchor)
            tree.column(key, anchor=anchor, width=width, stretch=(key == "detail"))

        for issue in report.issues:
            tree.insert(
                "",
                "end",
                values=(
                    issue.track_index,
                    issue.tick,
                    issue.offset,
                    issue.detail,
                ),
            )

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

        footer = ttk.Frame(container, style="Panel.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(footer, text="Close", command=self._on_close).grid(row=0, column=0)

        center_window_over_parent(self, master)

    def _build_summary(self, report: MidiImportReport) -> str:
        issue_count = len(report.issues)
        track_count = len({issue.track_index for issue in report.issues})
        issue_text = "issue" if issue_count == 1 else "issues"
        track_text = "track" if track_count == 1 else "tracks"
        base = (
            f"Strict parsing failed; lenient mode recovered {issue_count} {issue_text} "
            f"across {track_count} {track_text}."
        )
        tempo = report.assumed_tempo_bpm
        beats, beat_type = report.assumed_time_signature
        extras = f" Assumed tempo {tempo} BPM · Time signature {beats}/{beat_type}."
        if report.synthetic_eot_tracks:
            synthetic = ", ".join(str(idx) for idx in report.synthetic_eot_tracks)
            extras += f" Synthetic end-of-track events added to tracks: {synthetic}."
        return base + extras

    def _on_close(self) -> None:
        self.grab_release()
        self.destroy()


def show_midi_import_issues(
    master: tk.Widget | None,
    report: MidiImportReport,
) -> None:
    """Display the lenient MIDI import report in a modal dialog."""

    dialog = MidiImportIssuesDialog(master=master, report=report)
    dialog.wait_window()


__all__ = ["MidiImportIssuesDialog", "show_midi_import_issues"]
