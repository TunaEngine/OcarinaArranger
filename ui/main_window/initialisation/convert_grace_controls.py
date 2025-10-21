from __future__ import annotations

import tkinter as tk

from domain.arrangement.config import FAST_WINDWAY_SWITCH_WEIGHT_MAX
from ocarina_gui.settings import GraceTransformSettings


class ArrangerGraceControlsMixin:
    """Encapsulate Tk variable management for grace note settings."""

    def _initialize_grace_controls(self, state) -> None:
        grace_state = getattr(state, "grace_settings", GraceTransformSettings())
        if not isinstance(grace_state, GraceTransformSettings):
            grace_state = GraceTransformSettings()
        grace_state = grace_state.normalized()
        default_grace = GraceTransformSettings().normalized()
        fractions = tuple(grace_state.fractions) or default_grace.fractions
        if len(fractions) < 3:
            fractions = fractions + default_grace.fractions[len(fractions) :]
        fractions = fractions[:3]

        self.grace_policy = tk.StringVar(master=self, value=grace_state.policy)
        self.grace_fraction_primary = tk.DoubleVar(
            master=self,
            value=fractions[0] if fractions else default_grace.fractions[0],
        )
        self.grace_fraction_secondary = tk.DoubleVar(
            master=self,
            value=fractions[1] if len(fractions) > 1 else default_grace.fractions[1],
        )
        self.grace_fraction_tertiary = tk.DoubleVar(
            master=self,
            value=fractions[2] if len(fractions) > 2 else default_grace.fractions[2],
        )
        self.grace_max_chain = tk.IntVar(master=self, value=grace_state.max_chain)
        self.grace_anchor_min_fraction = tk.StringVar(
            master=self,
            value=self._format_decimal(grace_state.anchor_min_fraction),
        )
        self.grace_fold_out_of_range = tk.BooleanVar(
            master=self, value=grace_state.fold_out_of_range
        )
        self.grace_drop_out_of_range = tk.BooleanVar(
            master=self, value=grace_state.drop_out_of_range
        )
        self.grace_slow_tempo = tk.StringVar(
            master=self,
            value=self._format_decimal(grace_state.slow_tempo_bpm, precision=1),
        )
        self.grace_fast_tempo = tk.StringVar(
            master=self,
            value=self._format_decimal(grace_state.fast_tempo_bpm, precision=1),
        )
        self.grace_bonus = tk.StringVar(
            master=self, value=self._format_decimal(grace_state.grace_bonus)
        )
        self.grace_fast_windway_switch_weight = tk.StringVar(
            master=self,
            value=self._format_decimal(grace_state.fast_windway_switch_weight),
        )
        self._grace_fraction_displays: dict[str, tk.StringVar] = {
            "fraction_0": tk.StringVar(
                master=self,
                value=self._format_decimal(self.grace_fraction_primary.get()),
            ),
            "fraction_1": tk.StringVar(
                master=self,
                value=self._format_decimal(self.grace_fraction_secondary.get()),
            ),
            "fraction_2": tk.StringVar(
                master=self,
                value=self._format_decimal(self.grace_fraction_tertiary.get()),
            ),
        }
        self._grace_setting_vars: dict[str, tk.Variable] = {
            "policy": self.grace_policy,
            "fraction_0": self.grace_fraction_primary,
            "fraction_1": self.grace_fraction_secondary,
            "fraction_2": self.grace_fraction_tertiary,
            "max_chain": self.grace_max_chain,
            "anchor_min_fraction": self.grace_anchor_min_fraction,
            "fold_out_of_range": self.grace_fold_out_of_range,
            "drop_out_of_range": self.grace_drop_out_of_range,
            "slow_tempo_bpm": self.grace_slow_tempo,
            "fast_tempo_bpm": self.grace_fast_tempo,
            "grace_bonus": self.grace_bonus,
            "fast_windway_switch_weight": self.grace_fast_windway_switch_weight,
        }
        self._suspend_grace_trace = False

    def _register_grace_setting_vars(self) -> None:
        for var in self._grace_setting_vars.values():
            self._register_convert_setting_var(var)

    def _register_grace_traces(self) -> None:
        for key, var in self._grace_setting_vars.items():
            var.trace_add(
                "write",
                lambda *_args, grace_key=key: self._on_grace_setting_changed(grace_key),
            )

    def _collect_grace_settings(self) -> GraceTransformSettings:
        defaults = GraceTransformSettings()
        if not hasattr(self, "_grace_setting_vars"):
            return defaults

        try:
            policy = str(self.grace_policy.get() or defaults.policy).strip()
        except (tk.TclError, AttributeError):
            policy = defaults.policy

        fractions: list[float] = []
        for key in ("fraction_0", "fraction_1", "fraction_2"):
            var = self._grace_setting_vars.get(key)
            if var is None:
                continue
            try:
                value = float(var.get())
            except (tk.TclError, TypeError, ValueError, AttributeError):
                continue
            fractions.append(value)
        if not fractions:
            fractions = list(defaults.fractions)

        def _int_from_var(var: tk.Variable, fallback: int) -> int:
            try:
                return int(var.get())
            except (tk.TclError, TypeError, ValueError, AttributeError):
                return fallback

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

        def _bool_from_var(var: tk.Variable, fallback: bool) -> bool:
            try:
                raw = var.get()
            except (tk.TclError, AttributeError):
                return fallback
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, (int, float)):
                try:
                    return bool(int(raw))
                except (TypeError, ValueError):
                    return fallback
            if isinstance(raw, str):
                lowered = raw.strip().lower()
                if lowered in {"1", "true", "yes"}:
                    return True
                if lowered in {"0", "false", "no"}:
                    return False
            return fallback

        max_chain = _int_from_var(self.grace_max_chain, defaults.max_chain)
        anchor_min = _float_from_var(
            self.grace_anchor_min_fraction, defaults.anchor_min_fraction
        )
        fold = _bool_from_var(self.grace_fold_out_of_range, defaults.fold_out_of_range)
        drop = _bool_from_var(self.grace_drop_out_of_range, defaults.drop_out_of_range)
        slow_tempo = _float_from_var(self.grace_slow_tempo, defaults.slow_tempo_bpm)
        fast_tempo = _float_from_var(self.grace_fast_tempo, defaults.fast_tempo_bpm)
        grace_bonus = _float_from_var(self.grace_bonus, defaults.grace_bonus)
        fast_switch_weight = _float_from_var(
            self.grace_fast_windway_switch_weight,
            defaults.fast_windway_switch_weight,
        )

        return GraceTransformSettings(
            policy=policy or defaults.policy,
            fractions=tuple(fractions[:3]) or defaults.fractions,
            max_chain=max_chain,
            anchor_min_fraction=max(anchor_min, 0.0),
            fold_out_of_range=fold,
            drop_out_of_range=drop,
            slow_tempo_bpm=max(0.0, slow_tempo),
            fast_tempo_bpm=max(0.0, fast_tempo),
            grace_bonus=max(0.0, grace_bonus),
            fast_windway_switch_weight=max(
                0.0, min(FAST_WINDWAY_SWITCH_WEIGHT_MAX, fast_switch_weight)
            ),
        )

    def _on_grace_setting_changed(self, key: str) -> None:
        if getattr(self, "_suspend_grace_trace", False):
            return
        settings = self._collect_grace_settings()
        if key in getattr(self, "_grace_fraction_displays", {}):
            var = self._grace_setting_vars.get(key)
            if var is not None:
                try:
                    value = float(var.get())
                except (tk.TclError, TypeError, ValueError, AttributeError):
                    value = 0.0
                self._update_grace_fraction_display(key, value)
        self._viewmodel.update_settings(grace_settings=settings)

    def _update_grace_fraction_display(self, key: str, value: float) -> None:
        display = getattr(self, "_grace_fraction_displays", {}).get(key)
        if display is not None:
            display.set(self._format_decimal(value))

    def _apply_grace_settings_vars(self, settings: GraceTransformSettings) -> None:
        normalized = settings.normalized()
        defaults = GraceTransformSettings().normalized()
        fractions = tuple(normalized.fractions or defaults.fractions)
        if len(fractions) < 3:
            fractions = fractions + defaults.fractions[len(fractions) :]
        fractions = fractions[:3]
        self._suspend_grace_trace = True
        try:
            self.grace_policy.set(normalized.policy)
            self.grace_fraction_primary.set(fractions[0])
            self.grace_fraction_secondary.set(fractions[1])
            self.grace_fraction_tertiary.set(fractions[2])
            self.grace_max_chain.set(normalized.max_chain)
            self.grace_anchor_min_fraction.set(
                self._format_decimal(normalized.anchor_min_fraction)
            )
            self.grace_fold_out_of_range.set(normalized.fold_out_of_range)
            self.grace_drop_out_of_range.set(normalized.drop_out_of_range)
            self.grace_slow_tempo.set(
                self._format_decimal(normalized.slow_tempo_bpm, precision=1)
            )
            self.grace_fast_tempo.set(
                self._format_decimal(normalized.fast_tempo_bpm, precision=1)
            )
            self.grace_bonus.set(self._format_decimal(normalized.grace_bonus))
            self.grace_fast_windway_switch_weight.set(
                self._format_decimal(normalized.fast_windway_switch_weight)
            )
            self._update_grace_fraction_display("fraction_0", fractions[0])
            self._update_grace_fraction_display("fraction_1", fractions[1])
            self._update_grace_fraction_display("fraction_2", fractions[2])
        finally:
            self._suspend_grace_trace = False

    def reset_grace_settings(self) -> None:
        defaults = GraceTransformSettings().normalized()
        self._viewmodel.update_settings(grace_settings=defaults)
        self._apply_grace_settings_vars(defaults)

    def _sync_grace_settings_from_state(
        self, grace_settings: GraceTransformSettings | None
    ) -> None:
        active = grace_settings or GraceTransformSettings()
        self._apply_grace_settings_vars(active)


__all__ = ["ArrangerGraceControlsMixin"]
