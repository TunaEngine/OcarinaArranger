"""Automatic update menu integration for :class:`MenuActionsMixin`."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from contextlib import suppress
from tkinter import messagebox, ttk
from typing import Callable

from ocarina_gui.preferences import Preferences, save_preferences
from ocarina_gui.themes import apply_theme_to_toplevel
from services.update import ReleaseInfo, UpdateError, UpdateService, build_update_service
from services.update.constants import (
    UPDATE_CHANNEL_BETA,
    UPDATE_CHANNELS,
    UPDATE_CHANNEL_STABLE,
)
from services.update.recovery import consume_update_failure_notice

from ._logger import logger


def _summarise_release_notes(notes: str, *, max_chars: int = 800, max_lines: int = 15) -> str:
    normalised = notes.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalised:
        return ""

    lines = normalised.split("\n")
    if len(lines) > max_lines:
        normalised = "\n".join(lines[:max_lines]).rstrip()
        normalised += "\n…"

    if len(normalised) > max_chars:
        normalised = normalised[:max_chars].rstrip() + "…"
    return normalised


class _UpdateDownloadDialog(tk.Toplevel):
    """Modal progress indicator shown while updates download."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master=master)
        self.title("Downloading Update")
        self.resizable(False, False)
        with suppress(tk.TclError):
            self.transient(master)
        with suppress(tk.TclError):
            self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._disable_close)

        apply_theme_to_toplevel(self)

        message = ttk.Label(self, text="Downloading the latest update…", anchor="w")
        message.pack(fill="x", padx=20, pady=(20, 10))

        self._progress = ttk.Progressbar(self, mode="indeterminate", length=260)
        self._progress.pack(fill="x", padx=20, pady=(0, 20))
        with suppress(tk.TclError):
            self._progress.start(12)

        self._center_over_master(master)

    def _center_over_master(self, master: tk.Misc) -> None:
        try:
            self.update_idletasks()
            master.update_idletasks()
            master_x = master.winfo_rootx()
            master_y = master.winfo_rooty()
            master_width = master.winfo_width()
            master_height = master.winfo_height()
            width = self.winfo_width()
            height = self.winfo_height()
            x = master_x + (master_width - width) // 2
            y = master_y + (master_height - height) // 2
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            logger.debug("Unable to centre update progress dialog", exc_info=True)

    def _disable_close(self) -> None:
        pass

    def close(self) -> None:
        with suppress(tk.TclError):
            self._progress.stop()
        with suppress(tk.TclError):
            self.grab_release()
        self.destroy()


class UpdateMenuMixin:
    _preferences: Preferences | None
    _auto_update_enabled_var: tk.BooleanVar | None
    _update_channel_var: tk.StringVar | None
    _update_channel_choices: list[tuple[str, str]]
    _update_check_in_progress: bool

    def _setup_auto_update_menu(self, preferences: object) -> None:
        """Initialise the auto-update toggle state from stored preferences."""

        initial_value = False
        if isinstance(preferences, Preferences):
            stored_value = getattr(preferences, "auto_update_enabled", None)
            if stored_value is True:
                initial_value = True
            elif stored_value is False:
                initial_value = False

        try:
            self._auto_update_enabled_var = tk.BooleanVar(master=self, value=initial_value)
        except tk.TclError:
            # Headless initialisation paths can fail to construct Tk variables; fall back to None.
            logger.debug("Auto-update toggle unavailable in headless mode", exc_info=True)
            self._auto_update_enabled_var = None

        channel_value = UPDATE_CHANNEL_STABLE
        if isinstance(preferences, Preferences):
            stored_channel = getattr(preferences, "update_channel", None)
            if isinstance(stored_channel, str) and stored_channel in UPDATE_CHANNELS:
                channel_value = stored_channel

        try:
            self._update_channel_var = tk.StringVar(master=self, value=channel_value)
        except tk.TclError:
            logger.debug("Update channel selector unavailable in headless mode", exc_info=True)
            self._update_channel_var = None

        self._update_channel_choices = [
            ("Stable Releases", UPDATE_CHANNEL_STABLE),
            ("Beta Releases", UPDATE_CHANNEL_BETA),
        ]

        self._update_check_in_progress = False
        self._notify_update_failure_if_present()

    def _on_auto_update_toggled(self) -> None:
        """Persist the user's auto-update preference when the menu toggles."""

        enabled = self.auto_update_enabled
        if hasattr(self, "_preferences") and isinstance(self._preferences, Preferences):
            self._preferences.auto_update_enabled = enabled
            try:
                save_preferences(self._preferences)
            except Exception:
                logger.debug("Failed to persist auto-update preference", exc_info=True)

    @property
    def auto_update_enabled(self) -> bool:
        """Return ``True`` when automatic updates should run on startup."""

        var = getattr(self, "_auto_update_enabled_var", None)
        if isinstance(var, tk.Variable):
            try:
                raw_value = var.get()
            except Exception:
                logger.debug("Unable to read auto-update toggle state", exc_info=True)
            else:
                if isinstance(raw_value, str):
                    return raw_value.lower() in {"1", "true", "yes", "on"}
                return bool(raw_value)
        preferences = getattr(self, "_preferences", None)
        if isinstance(preferences, Preferences):
            if preferences.auto_update_enabled is True:
                return True
        return False

    @property
    def update_channel(self) -> str:
        """Return the selected update channel."""

        var = getattr(self, "_update_channel_var", None)
        if isinstance(var, tk.Variable):
            try:
                raw_value = var.get()
            except Exception:
                logger.debug("Unable to read update channel state", exc_info=True)
            else:
                if isinstance(raw_value, str):
                    lowered = raw_value.strip().lower()
                    if lowered in UPDATE_CHANNELS:
                        return lowered

        preferences = getattr(self, "_preferences", None)
        if isinstance(preferences, Preferences):
            stored_channel = getattr(preferences, "update_channel", None)
            if isinstance(stored_channel, str) and stored_channel in UPDATE_CHANNELS:
                return stored_channel

        return UPDATE_CHANNEL_STABLE

    def _on_update_channel_changed(self) -> None:
        channel = self.update_channel
        if hasattr(self, "_preferences") and isinstance(self._preferences, Preferences):
            self._preferences.update_channel = channel
            try:
                save_preferences(self._preferences)
            except Exception:
                logger.debug("Failed to persist update channel preference", exc_info=True)

    def _check_for_updates_command(self) -> None:
        """Trigger a manual update check from the Tools menu."""

        if not sys.platform.startswith("win"):
            self._show_update_info(
                "Check for Updates",
                "Manual update checks are only available on Windows builds.",
            )
            return

        if getattr(self, "_update_check_in_progress", False):
            self._show_update_info("Check for Updates", "An update check is already running.")
            return

        service = build_update_service(channel=self.update_channel)
        if service is None:
            self._show_update_error(
                "Check for Updates",
                "Unable to check for updates right now. Please try again later.",
            )
            return

        self._update_check_in_progress = True

        thread = threading.Thread(
            target=self._run_manual_update_check,
            args=(service,),
            name="ocarina-update-manual",
            daemon=True,
        )
        thread.start()

    def start_automatic_update_check(self) -> None:
        """Run the automatic update check when the application starts."""

        if not sys.platform.startswith("win"):
            return
        if not self.auto_update_enabled:
            return
        if getattr(self, "_update_check_in_progress", False):
            return

        service = build_update_service(channel=self.update_channel)
        if service is None:
            return

        self._update_check_in_progress = True

        thread = threading.Thread(
            target=self._run_automatic_update_check,
            args=(service,),
            name="ocarina-update-auto",
            daemon=True,
        )
        thread.start()

    def _run_manual_update_check(self, service: UpdateService) -> None:
        try:
            release = service.get_available_release()
        except UpdateError as exc:
            self._schedule_update_dialog("Check for Updates", str(exc), error=True)
            return
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Manual update check failed")
            self._schedule_update_dialog(
                "Check for Updates",
                "Unable to check for updates right now. Please try again later.",
                error=True,
            )
            return

        if release is None:
            self._schedule_update_dialog(
                "Check for Updates",
                "You're already running the latest version.",
                error=False,
            )
            return

        self._schedule_update_prompt(service, release)

    def _run_automatic_update_check(self, service: UpdateService) -> None:
        try:
            release = service.get_available_release()
        except UpdateError as exc:
            logger.warning("Automatic update check failed: %s", exc)
            self._mark_update_check_complete()
            return
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Automatic update check failed")
            self._mark_update_check_complete()
            return

        if release is None:
            self._mark_update_check_complete()
            return

        self._schedule_update_prompt(service, release)

    def _schedule_update_prompt(self, service: UpdateService, release: ReleaseInfo) -> None:
        def _prompt() -> None:
            prompt_message = self._build_update_prompt_message(release)
            try:
                should_install = messagebox.askyesno(
                    "Update Available",
                    prompt_message,
                    parent=self,
                )
            except Exception:
                logger.debug("Unable to display update confirmation dialog", exc_info=True)
                should_install = False

            if not should_install:
                self._complete_update_check()
                return

            try:
                messagebox.showinfo(
                    "Update Available",
                    "Downloading update. The application will close once installation begins.",
                    parent=self,
                )
            except Exception:
                logger.debug("Unable to display update start dialog", exc_info=True)

            self._start_update_install(service, release)

        self._invoke_on_ui_thread(_prompt)

    def _start_update_install(self, service: UpdateService, release: ReleaseInfo) -> None:
        progress_dialog: dict[str, _UpdateDownloadDialog | None] = {"dialog": None}

        def _open_progress_dialog() -> None:
            try:
                dialog = _UpdateDownloadDialog(self)
            except Exception:
                logger.debug("Unable to display update progress dialog", exc_info=True)
            else:
                progress_dialog["dialog"] = dialog

        self._invoke_on_ui_thread(_open_progress_dialog)

        def _close_progress_dialog() -> None:
            dialog = progress_dialog.pop("dialog", None)
            if dialog is None:
                return
            try:
                dialog.close()
            except Exception:
                logger.debug("Unable to close update progress dialog", exc_info=True)

        def _install() -> None:
            try:
                service.download_and_install(release)
            except UpdateError as exc:
                self._invoke_on_ui_thread(_close_progress_dialog)
                self._schedule_update_dialog("Update Failed", str(exc), error=True)
            except Exception:  # pragma: no cover - defensive guard
                logger.exception("Manual update installation failed")
                self._invoke_on_ui_thread(_close_progress_dialog)
                self._schedule_update_dialog(
                    "Update Failed",
                    "An unexpected error occurred while installing the update.",
                    error=True,
                )
            else:
                self._invoke_on_ui_thread(_close_progress_dialog)
                self._mark_update_check_complete()

        thread = threading.Thread(
            target=_install,
            name="ocarina-update-install",
            daemon=True,
        )
        thread.start()

    def _build_update_prompt_message(self, release: ReleaseInfo) -> str:
        message = f"Version {release.version} is available. Download and install now?"
        if release.release_notes:
            notes = _summarise_release_notes(release.release_notes)
            if notes:
                message = f"{message}\n\nRelease notes:\n{notes}"
        return message

    def _schedule_update_dialog(self, title: str, message: str, *, error: bool) -> None:
        def _show() -> None:
            try:
                if error:
                    messagebox.showerror(title, message, parent=self)
                else:
                    messagebox.showinfo(title, message, parent=self)
            except Exception:
                logger.debug("Unable to display update dialog", exc_info=True)
            finally:
                self._complete_update_check()

        self._invoke_on_ui_thread(_show)

    def _show_update_info(self, title: str, message: str) -> None:
        try:
            messagebox.showinfo(title, message, parent=self)
        except Exception:
            logger.debug("Unable to display update info dialog", exc_info=True)

    def _show_update_error(self, title: str, message: str) -> None:
        try:
            messagebox.showerror(title, message, parent=self)
        except Exception:
            logger.debug("Unable to display update error dialog", exc_info=True)

    def _mark_update_check_complete(self) -> None:
        def _done() -> None:
            self._complete_update_check()

        self._invoke_on_ui_thread(_done)

    def _complete_update_check(self) -> None:
        self._update_check_in_progress = False

    def _notify_update_failure_if_present(self) -> None:
        if not sys.platform.startswith("win"):
            return

        try:
            notice = consume_update_failure_notice()
        except Exception:
            logger.debug("Unable to read update failure notice", exc_info=True)
            return

        if not notice:
            return

        reason, advice = notice
        message = (
            "Ocarina Arranger could not install the previous update."
            f"\n\nReason: {reason}"
        )
        if advice:
            message += f"\n\n{advice}"

        try:
            messagebox.showerror("Update Failed", message, parent=self)
        except Exception:
            logger.debug("Unable to display update failure notice", exc_info=True)

    def _invoke_on_ui_thread(self, callback: Callable[[], None]) -> None:
        if threading.current_thread() is threading.main_thread():
            callback()
            return

        try:
            self.after(0, callback)
        except Exception:
            # ``after`` may be unavailable in headless tests; invoke immediately.
            callback()
