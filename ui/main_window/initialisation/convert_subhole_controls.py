from __future__ import annotations

import re
import tkinter as tk

from ocarina_gui.settings import SubholeTransformSettings


_PAIR_PATTERN = re.compile(r"[;,\n]+")


class ArrangerSubholeControlsMixin:
    """Manage Tk variables controlling subhole comfort settings."""

    def _initialize_subhole_controls(self, state) -> None:
        subhole_state = getattr(state, "subhole_settings", SubholeTransformSettings())
        if not isinstance(subhole_state, SubholeTransformSettings):
            subhole_state = SubholeTransformSettings()
        normalized = subhole_state.normalized()
        defaults = SubholeTransformSettings().normalized()

        self.subhole_max_changes = tk.StringVar(
            master=self,
            value=self._format_decimal(normalized.max_changes_per_second, precision=2),
        )
        self.subhole_max_subhole_changes = tk.StringVar(
            master=self,
            value=self._format_decimal(
                normalized.max_subhole_changes_per_second, precision=2
            ),
        )
        self.subhole_pair_limits = tk.StringVar(
            master=self,
            value=self._format_pair_limits(normalized.pair_limits),
        )
        self._subhole_defaults = defaults
        self._subhole_setting_vars: dict[str, tk.Variable] = {
            "max_changes_per_second": self.subhole_max_changes,
            "max_subhole_changes_per_second": self.subhole_max_subhole_changes,
            "pair_limits": self.subhole_pair_limits,
        }
        self._suspend_subhole_trace = False

    def _register_subhole_setting_vars(self) -> None:
        for var in self._subhole_setting_vars.values():
            self._register_convert_setting_var(var)

    def _register_subhole_traces(self) -> None:
        for key, var in self._subhole_setting_vars.items():
            var.trace_add(
                "write",
                lambda *_args, subhole_key=key: self._on_subhole_setting_changed(
                    subhole_key
                ),
            )

    def _collect_subhole_settings(self) -> SubholeTransformSettings:
        defaults = getattr(self, "_subhole_defaults", SubholeTransformSettings())
        if not hasattr(self, "_subhole_setting_vars"):
            return defaults

        def _float_from_var(var: tk.Variable, fallback: float) -> float:
            try:
                raw = var.get()
            except (tk.TclError, AttributeError):
                return fallback
            if raw in (None, ""):
                return fallback
            try:
                return float(raw)
            except (TypeError, ValueError):
                return fallback

        max_changes = _float_from_var(
            self.subhole_max_changes, defaults.max_changes_per_second
        )
        max_subhole_changes = _float_from_var(
            self.subhole_max_subhole_changes,
            defaults.max_subhole_changes_per_second,
        )

        entries: list[tuple[int, int, float, float]] = []
        try:
            raw_pairs = str(self.subhole_pair_limits.get() or "")
        except (tk.TclError, AttributeError):
            raw_pairs = ""

        for chunk in _PAIR_PATTERN.split(raw_pairs):
            entry = chunk.strip()
            if not entry:
                continue
            if "=" in entry:
                pair_part, value_part = entry.split("=", 1)
            elif ":" in entry:
                pair_part, value_part = entry.split(":", 1)
            else:
                continue
            pair_text = pair_part.strip()
            details = value_part.strip()
            if "@" in details:
                rate_text, ease_text = details.split("@", 1)
            else:
                rate_text, ease_text = details, ""
            if "-" in pair_text:
                first_text, second_text = pair_text.split("-", 1)
            elif " " in pair_text:
                first_text, second_text = pair_text.split(None, 1)
            elif "," in pair_text:
                first_text, second_text = pair_text.split(",", 1)
            else:
                continue
            try:
                first = int(first_text.strip())
                second = int(second_text.strip())
            except ValueError:
                continue
            if first == second:
                continue
            try:
                max_hz = float(rate_text.strip())
            except ValueError:
                continue
            if max_hz <= 0:
                continue
            ease = 1.0
            if ease_text.strip():
                try:
                    ease_candidate = float(ease_text.strip())
                except ValueError:
                    ease_candidate = 1.0
                if ease_candidate >= 0:
                    ease = ease_candidate
            ordered = tuple(sorted((first, second)))
            entries.append((ordered[0], ordered[1], max_hz, ease))

        candidate = SubholeTransformSettings(
            max_changes_per_second=max_changes,
            max_subhole_changes_per_second=max_subhole_changes,
            pair_limits=tuple(entries) if entries else defaults.pair_limits,
        )
        return candidate

    def _on_subhole_setting_changed(self, _key: str) -> None:
        if getattr(self, "_suspend_subhole_trace", False):
            return
        settings = self._collect_subhole_settings().normalized()
        self._viewmodel.update_settings(subhole_settings=settings)

    def _apply_subhole_settings_vars(self, settings: SubholeTransformSettings) -> None:
        normalized = settings.normalized()
        self._suspend_subhole_trace = True
        try:
            self.subhole_max_changes.set(
                self._format_decimal(normalized.max_changes_per_second, precision=2)
            )
            self.subhole_max_subhole_changes.set(
                self._format_decimal(
                    normalized.max_subhole_changes_per_second, precision=2
                )
            )
            self.subhole_pair_limits.set(
                self._format_pair_limits(normalized.pair_limits)
            )
        finally:
            self._suspend_subhole_trace = False

    def reset_subhole_settings(self) -> None:
        defaults = SubholeTransformSettings().normalized()
        self._viewmodel.update_settings(subhole_settings=defaults)
        self._apply_subhole_settings_vars(defaults)

    def _sync_subhole_settings_from_state(
        self, subhole_settings: SubholeTransformSettings | None
    ) -> None:
        active = subhole_settings or SubholeTransformSettings()
        self._apply_subhole_settings_vars(active)

    def _format_pair_limits(
        self, pair_limits: tuple[tuple[int, int, float, float], ...]
    ) -> str:
        if not pair_limits:
            return ""
        formatted: list[str] = []
        for first, second, max_hz, ease in pair_limits:
            if ease == 1.0:
                formatted.append(
                    f"{first}-{second}={self._format_decimal(max_hz, precision=2)}"
                )
            else:
                formatted.append(
                    f"{first}-{second}={self._format_decimal(max_hz, precision=2)}@"
                    f"{self._format_decimal(ease, precision=2)}"
                )
        return ", ".join(formatted)


__all__ = ["ArrangerSubholeControlsMixin"]
