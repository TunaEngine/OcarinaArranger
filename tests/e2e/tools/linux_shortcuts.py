"""Register keybindings and imperative actions for Linux automation."""

from __future__ import annotations

import logging
import os
from typing import Callable, Iterable

from ocarina_gui.app import App

logger = logging.getLogger(__name__)


def select_tab(app: App, label: str) -> bool:
    notebook = getattr(app, "_notebook", None)
    if notebook is None:
        logger.error("Notebook is not available; cannot select %s tab", label)
        return False
    target = label.strip().lower()
    logger.info("Selecting notebook tab via Linux automation: %s", target)
    try:
        total = notebook.index("end")
    except Exception:
        total = 0
    for index in range(total):
        try:
            text = str(notebook.tab(index, "text")).strip().lower()
        except Exception:
            continue
        if text == target:
            try:
                notebook.select(index)
            except Exception:
                logger.exception("Unable to select tab %s", label)
                return False
            else:
                break
    else:
        if target in {"original", "arranged"}:
            try:
                app._ensure_preview_tab_initialized(target)
                app._select_preview_tab(target)
            except Exception:
                logger.exception("Failed to select preview tab %s", target)
                return False
        else:
            logger.warning("Requested notebook tab %s does not exist", target)
            return False
    try:
        app._maybe_auto_render_selected_preview()
    except Exception:
        logger.debug("Auto-render preview hook failed after selecting %s", target)
    app.update_idletasks()
    return True


def activate_theme(app: App, theme_id: str) -> None:
    logger.info("Applying theme via Linux automation: %s", theme_id)
    try:
        app.activate_theme_menu(theme_id)
    except Exception:
        logger.exception("Failed to activate theme %s via automation", theme_id)
    finally:
        app.update_idletasks()


def open_instrument_editor(app: App) -> None:
    logger.info("Opening instrument editor via Linux automation")
    try:
        app.open_instrument_layout_editor()
    except Exception:
        logger.exception("Instrument Layout Editor automation failed")
    else:
        app.update_idletasks()


def open_licenses(app: App) -> None:
    logger.info("Opening licenses window via Linux automation")
    try:
        app._show_licenses_window()
    except Exception:
        logger.exception("Licenses automation failed")
    else:
        app.update_idletasks()


def _install_shortcut(app: App, sequences: Iterable[str], action: Callable[[], None]) -> None:
    def _handler(_event) -> str:
        try:
            action()
        except Exception:  # pragma: no cover - defensive diagnostics
            logger.exception(
                "Linux automation shortcut %s raised an exception",
                ",".join(sequences),
            )
        return "break"

    for seq in sequences:
        try:
            app.bind_all(seq, _handler, add="+")
        except Exception:  # pragma: no cover - defensive diagnostics
            logger.exception("Failed to bind Linux automation shortcut %s", seq)


def install_shortcuts(app: App) -> None:
    enabled = os.environ.get("OCARINA_E2E_SHORTCUTS", "").strip().lower()
    if enabled not in {"1", "true", "yes"}:
        return

    _install_shortcut(
        app,
        ("<Control-Alt-Shift-l>", "<Control-Alt-Shift-L>"),
        lambda: activate_theme(app, "light"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-d>", "<Control-Alt-Shift-D>"),
        lambda: activate_theme(app, "dark"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-c>", "<Control-Alt-Shift-C>"),
        lambda: select_tab(app, "convert"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-f>", "<Control-Alt-Shift-F>"),
        lambda: select_tab(app, "fingerings"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-o>", "<Control-Alt-Shift-O>"),
        lambda: select_tab(app, "original"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-a>", "<Control-Alt-Shift-A>"),
        lambda: select_tab(app, "arranged"),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-i>", "<Control-Alt-Shift-I>"),
        lambda: open_instrument_editor(app),
    )
    _install_shortcut(
        app,
        ("<Control-Alt-Shift-p>", "<Control-Alt-Shift-P>"),
        lambda: open_licenses(app),
    )


__all__ = [
    "activate_theme",
    "install_shortcuts",
    "open_instrument_editor",
    "open_licenses",
    "select_tab",
]

