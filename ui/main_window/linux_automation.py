"""Linux automation helpers for the main window."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


class LinuxAutomationMixin:
    """Process Linux E2E automation commands when environment variables are set."""

    _linux_command_file: Path | None
    _linux_status_file: Path | None
    _linux_command_job: str | None
    _linux_command_counter: int

    def _setup_linux_automation(self) -> None:
        if getattr(self, "_headless", False):
            return

        command_env = os.environ.get("OCARINA_E2E_COMMAND_FILE")
        status_env = os.environ.get("OCARINA_E2E_STATUS_FILE")
        sample_env = os.environ.get("OCARINA_E2E_SAMPLE_XML")
        shortcuts_env = os.environ.get("OCARINA_E2E_SHORTCUTS", "")

        self._linux_command_file = Path(command_env).expanduser() if command_env else None
        self._linux_status_file = Path(status_env).expanduser() if status_env else None
        self._linux_command_job = None
        self._linux_command_counter = 0

        if self._linux_status_file is not None:
            self._write_linux_status(preview="pending")

        if self._linux_command_file is not None:
            try:
                self._linux_command_file.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.exception(
                    "Unable to prepare Linux automation command directory: %s",
                    self._linux_command_file,
                )
            else:
                self._linux_command_job = self.after(200, self._poll_linux_command_file)

        if shortcuts_env.strip().lower() in {"1", "true", "yes"}:
            self.after(200, self._install_linux_shortcuts)

        if sample_env:
            sample_path = Path(sample_env).expanduser()
            if sample_path.exists():
                self.after(600, lambda: self._prime_linux_preview(sample_path))
            else:
                logger.warning("Linux automation sample MusicXML missing: %s", sample_path)
                self._write_linux_status(preview="error", detail="sample-missing")

    def _teardown_linux_automation(self) -> None:
        job = getattr(self, "_linux_command_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                logger.debug("Failed to cancel Linux automation poll job", exc_info=True)
        self._linux_command_job = None

    # ------------------------------------------------------------------
    # Command processing
    # ------------------------------------------------------------------
    def _poll_linux_command_file(self) -> None:
        path = self._linux_command_file
        if path is None:
            return

        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = ""
        except Exception:
            logger.exception("Failed to read Linux automation command file")
            content = ""

        commands = [line.strip() for line in content.splitlines() if line.strip()]
        if commands:
            try:
                path.write_text("", encoding="utf-8")
            except Exception:
                logger.exception("Unable to reset Linux automation command file")

        for command in commands:
            status = "handled"
            detail: str | None = None
            try:
                handled = self._dispatch_linux_command(command)
                if handled is False:
                    status = "ignored"
            except Exception as exc:  # pragma: no cover - defensive diagnostics
                logger.exception("Linux automation command failed: %s", command)
                status = "error"
                detail = str(exc)
            self._linux_command_counter += 1
            self._write_linux_status(
                last_command=command,
                last_command_status=status,
                last_command_error=detail,
                last_command_timestamp=time.time(),
                last_command_counter=self._linux_command_counter,
            )

        self._linux_command_job = self.after(200, self._poll_linux_command_file)

    def _dispatch_linux_command(self, command: str) -> bool:
        normalized = command.strip()
        if not normalized:
            return False
        if normalized == "open_instrument_layout":
            self.open_instrument_layout_editor()
            self.update_idletasks()
            return True
        if normalized == "open_licenses":
            self._show_licenses_window()
            self.update_idletasks()
            return True
        if normalized.startswith("select_tab:"):
            _, _, label = normalized.partition(":")
            return self._automation_select_tab(label or "convert")
        if normalized.startswith("set_theme:"):
            _, _, theme = normalized.partition(":")
            theme_id = (theme or "").strip().lower()
            if theme_id in {"light", "dark"}:
                self.activate_theme_menu(theme_id)
                self.update_idletasks()
                return True
            logger.warning("Unsupported Linux automation theme request: %s", command)
            return False
        logger.warning("Unsupported Linux automation command: %s", command)
        return False

    def _automation_select_tab(self, label: str) -> bool:
        notebook = getattr(self, "_notebook", None)
        if notebook is None:
            logger.error("Notebook is not available; cannot select tab %s", label)
            return False
        target = label.strip().lower()
        if not target:
            target = "convert"

        if target in {"original", "arranged"}:
            self._ensure_preview_tab_initialized(target)
            self._select_preview_tab(target)
        else:
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
                        logger.exception("Unable to select notebook tab %s", label)
                        return False
                    break
            else:
                logger.warning("Requested notebook tab %s does not exist", target)
                return False

        try:
            self._maybe_auto_render_selected_preview()
        except Exception:
            logger.debug("Auto-render preview hook failed after selecting %s", target, exc_info=True)
        self.update_idletasks()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _write_linux_status(self, **updates: object) -> None:
        status_file = getattr(self, "_linux_status_file", None)
        if status_file is None:
            return
        try:
            existing: dict[str, object] = {}
            if status_file.exists():
                payload = status_file.read_text(encoding="utf-8")
                if payload:
                    existing = json.loads(payload)
            cleaned = {key: value for key, value in updates.items() if value is not None}
            removals = [key for key, value in updates.items() if value is None]
            existing.update(cleaned)
            for key in removals:
                existing.pop(key, None)
            status_file.write_text(json.dumps(existing), encoding="utf-8")
        except json.JSONDecodeError:
            logger.debug("Status file %s contained invalid JSON", status_file)
        except Exception:  # pragma: no cover - defensive diagnostics
            logger.exception("Failed to write Linux automation status file to %s", status_file)

    def _install_linux_shortcuts(self) -> None:
        mappings: Iterable[tuple[Iterable[str], Callable[[], None]]] = (
            (("<Control-Alt-Shift-l>", "<Control-Alt-Shift-L>"), lambda: self.activate_theme_menu("light")),
            (("<Control-Alt-Shift-d>", "<Control-Alt-Shift-D>"), lambda: self.activate_theme_menu("dark")),
            (("<Control-Alt-Shift-c>", "<Control-Alt-Shift-C>"), lambda: self._automation_select_tab("convert")),
            (("<Control-Alt-Shift-f>", "<Control-Alt-Shift-F>"), lambda: self._automation_select_tab("fingerings")),
            (("<Control-Alt-Shift-o>", "<Control-Alt-Shift-O>"), lambda: self._automation_select_tab("original")),
            (("<Control-Alt-Shift-a>", "<Control-Alt-Shift-A>"), lambda: self._automation_select_tab("arranged")),
            (("<Control-Alt-Shift-i>", "<Control-Alt-Shift-I>"), self.open_instrument_layout_editor),
            (("<Control-Alt-Shift-p>", "<Control-Alt-Shift-P>"), self._show_licenses_window),
        )

        for sequences, action in mappings:
            handler = self._make_linux_shortcut_handler(action)
            for sequence in sequences:
                try:
                    self.bind_all(sequence, handler, add="+")
                except Exception:
                    logger.exception("Failed to bind Linux automation shortcut %s", sequence)

    def _make_linux_shortcut_handler(self, action: Callable[[], None]) -> Callable[[object], str]:
        def _handler(_event: object) -> str:
            try:
                action()
            except Exception:  # pragma: no cover - defensive diagnostics
                logger.exception("Linux automation shortcut raised an exception")
            return "break"

        return _handler

    def _prime_linux_preview(self, sample_path: Path) -> None:
        logger.info("Priming Linux automation preview with %s", sample_path)
        previous = getattr(self, "_suppress_preview_error_dialogs", False)
        try:
            self._suppress_preview_error_dialogs = True
            viewmodel = getattr(self, "_viewmodel", None)
            if viewmodel is None:
                raise RuntimeError("Main window does not expose a viewmodel")
            viewmodel.update_settings(input_path=str(sample_path))
            sync_controls = getattr(self, "_sync_controls_from_state", None)
            if callable(sync_controls):
                sync_controls()
            outcome = self.render_previews()
            if hasattr(outcome, "wait"):
                try:
                    result = outcome.wait()
                except Exception as exc:  # pragma: no cover - defensive diagnostics
                    logger.exception(
                        "Preview rendering worker raised during Linux automation"
                    )
                    self._write_linux_status(preview="error", detail=str(exc))
                    return
            else:
                result = outcome
        except Exception as exc:  # pragma: no cover - defensive diagnostics
            logger.exception("Failed to render preview data for Linux automation")
            self._write_linux_status(preview="error", detail=str(exc))
            return
        finally:
            self._suppress_preview_error_dialogs = previous

        if hasattr(result, "is_err") and result.is_err():
            detail = getattr(result, "error", "<unknown error>")
            logger.error("Preview rendering failed during Linux automation: %s", detail)
            self._write_linux_status(preview="error", detail=str(detail))
            return

        logger.info("Preview data seeded successfully for Linux automation")
        self._write_linux_status(preview="ready")


__all__ = ["LinuxAutomationMixin"]
