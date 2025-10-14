from __future__ import annotations

import tkinter as tk


class PreviewTransposeMixin:
    """Manage transpose controls and state synchronisation."""

    def _on_transpose_value_changed(self, *_args: object) -> None:
        if self._suspend_transpose_update:
            return
        self._update_transpose_apply_cancel_state()

    def _apply_transpose_offset(self) -> None:
        try:
            value = int(self.transpose_offset.get())
        except (tk.TclError, ValueError):
            self._update_transpose_apply_cancel_state(valid=False)
            return
        if value == self._transpose_applied_offset:
            self._update_transpose_apply_cancel_state()
            return
        previous = self._transpose_applied_offset
        self._transpose_applied_offset = value
        self._viewmodel.update_settings(transpose_offset=value)
        outcome = self.render_previews()
        try:
            if hasattr(outcome, "wait"):
                result = outcome.wait()
            else:
                result = outcome
        except Exception:
            self._transpose_applied_offset = previous
            self._viewmodel.update_settings(transpose_offset=previous)
            self._suspend_transpose_update = True
            try:
                self.transpose_offset.set(previous)
            finally:
                self._suspend_transpose_update = False
            raise
        if result.is_err():
            self._transpose_applied_offset = previous
            self._viewmodel.update_settings(transpose_offset=previous)
            self._suspend_transpose_update = True
            try:
                self.transpose_offset.set(previous)
            finally:
                self._suspend_transpose_update = False
        self._update_transpose_apply_cancel_state()

    def _cancel_transpose_offset(self) -> None:
        value = self._transpose_applied_offset
        self._suspend_transpose_update = True
        try:
            self.transpose_offset.set(value)
        finally:
            self._suspend_transpose_update = False
        self._update_transpose_apply_cancel_state()

    def _set_transpose_controls_enabled(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        for spinbox in list(self._transpose_spinboxes):
            try:
                exists = getattr(spinbox, "winfo_exists", None)
                if callable(exists):
                    if not int(exists()):
                        self._transpose_spinboxes.remove(spinbox)
                        continue
                spinbox.state(state)
            except tk.TclError:
                self._transpose_spinboxes.remove(spinbox)
            except AttributeError:
                try:
                    spinbox.state(state)
                except Exception:
                    self._transpose_spinboxes.remove(spinbox)
        for widget in (self._transpose_apply_button, self._transpose_cancel_button):
            if widget is None:
                continue
            try:
                widget.state(state)
            except Exception:
                continue
        if enabled:
            self._update_transpose_apply_cancel_state()

    def _update_transpose_apply_cancel_state(
        self,
        *,
        value: int | None = None,
        valid: bool = True,
    ) -> None:
        apply_button = self._transpose_apply_button
        cancel_button = self._transpose_cancel_button
        if apply_button is None or cancel_button is None:
            return
        widgets = (apply_button, cancel_button)
        if not valid:
            for widget in widgets:
                try:
                    widget.state(["disabled"])
                except Exception:
                    continue
            return
        if value is None:
            try:
                value = int(self.transpose_offset.get())
            except (tk.TclError, ValueError):
                for widget in widgets:
                    try:
                        widget.state(["disabled"])
                    except Exception:
                        continue
                return
        changed = value != self._transpose_applied_offset
        blocked = any(
            playback.state.is_rendering or playback.state.is_playing
            for playback in self._preview_playback.values()
        )
        if blocked or not changed:
            for widget in widgets:
                try:
                    widget.state(["disabled"])
                except Exception:
                    continue
            return
        for widget in widgets:
            try:
                widget.state(["!disabled"])
            except Exception:
                continue
