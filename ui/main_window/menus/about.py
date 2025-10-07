"""About menu integration for :class:`MenuActionsMixin`."""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from ocarina_gui.themes import apply_theme_to_toplevel
from shared.ttk import ttk

_LICENSE_FILENAME = "THIRD-PARTY-LICENSES"


def _license_file_candidates() -> list[Path]:
    """Return possible paths for the aggregated license file."""

    project_root = Path(__file__).resolve().parents[3]
    candidates: list[Path] = [project_root / _LICENSE_FILENAME]

    executable = getattr(sys, "executable", "")
    if executable:
        candidates.append(Path(executable).resolve().parent / _LICENSE_FILENAME)

    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        candidates.append(Path(meipass) / _LICENSE_FILENAME)

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates


def _load_license_text() -> str:
    """Read the license text from the first accessible candidate path."""

    last_os_error: OSError | None = None
    for candidate in _license_file_candidates():
        try:
            return candidate.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except OSError as exc:
            last_os_error = exc

    if last_os_error is not None:
        raise last_os_error

    raise FileNotFoundError(_LICENSE_FILENAME)


class AboutMenuMixin:
    """Provide commands for About menu actions."""

    _licenses_window: tk.Toplevel | None = None
    _licenses_text_widget: tk.Text | None = None

    def _show_licenses_window(self) -> None:
        """Display the aggregated third-party license information."""

        try:
            license_text = _load_license_text()
        except FileNotFoundError:
            messagebox.showerror(
                "Licenses Unavailable",
                "The third-party license file could not be found.",
                parent=self,
            )
            return
        except OSError:
            messagebox.showerror(
                "Licenses Unavailable",
                "The third-party license file could not be read.",
                parent=self,
            )
            return

        window = getattr(self, "_licenses_window", None)
        text_widget = getattr(self, "_licenses_text_widget", None)
        if isinstance(window, tk.Toplevel) and window.winfo_exists() and isinstance(
            text_widget, tk.Text
        ):
            text_widget.configure(state="normal")
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", license_text)
            text_widget.configure(state="disabled")
            text_widget.yview_moveto(0.0)
            window.deiconify()
            window.lift()
            with suppress(tk.TclError):
                window.focus_force()
            return

        window = tk.Toplevel(master=self)
        window.title("Third-Party Licenses")
        window.minsize(width=640, height=480)
        window.geometry("800x600")
        with suppress(tk.TclError):
            window.transient(self)

        apply_theme_to_toplevel(window)

        container = ttk.Frame(window, padding=16, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        text_widget = tk.Text(
            container,
            wrap="word",
            state="normal",
            highlightthickness=0,
            borderwidth=0,
        )
        text_widget.insert("1.0", license_text)
        text_widget.configure(state="disabled")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        window.bind("<Destroy>", self._on_licenses_window_destroy, add=True)
        window.bind("<Escape>", lambda _event: window.destroy())

        self._licenses_window = window
        self._licenses_text_widget = text_widget
        with suppress(tk.TclError):
            window.focus_force()

    def _on_licenses_window_destroy(self, event: tk.Event | None = None) -> None:
        widget = getattr(event, "widget", None)
        if widget is getattr(self, "_licenses_window", None):
            self._licenses_window = None
            self._licenses_text_widget = None


__all__ = ["AboutMenuMixin"]
