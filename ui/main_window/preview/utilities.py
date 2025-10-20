from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox
from typing import Optional

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preferences import DEFAULT_ARRANGER_MODE
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from viewmodels.arranger_models import ArrangerGPSettings, gp_settings_warning
from ocarina_gui.scrolling import move_canvas_to_pixel_fraction
from services.project_service import PreviewPlaybackSnapshot

logger = logging.getLogger(__name__)


class PreviewUtilitiesMixin:
    """Shared helpers for preview state management and filesystem access."""

    @staticmethod
    def _coerce_tk_bool(value: object, *, default: bool | None = None) -> bool:
        """Best-effort coercion of Tkinter variable values to real booleans."""

        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            try:
                return bool(int(value))
            except (TypeError, ValueError):
                pass
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "yes", "on"}:
                return True
            if normalized in {"0", "false", "f", "no", "off", ""}:
                return False
        if default is not None:
            return default
        raise ValueError(f"Cannot interpret {value!r} as a boolean")

    def _sync_viewmodel_settings(self) -> None:
        self._viewmodel.update_settings(
            input_path=self.input_path.get(),
            prefer_mode=self.prefer_mode.get(),
            prefer_flats=self.prefer_flats.get(),
            collapse_chords=self.collapse_chords.get(),
            favor_lower=self.favor_lower.get(),
            range_min=self.range_min.get(),
            range_max=self.range_max.get(),
            transpose_offset=self._transpose_applied_offset,
            instrument_id=getattr(self, "_selected_instrument_id", ""),
            arranger_mode=(
                self.arranger_mode.get()
                if hasattr(self, "arranger_mode")
                else DEFAULT_ARRANGER_MODE
            ),
            arranger_gp_settings=(
                self._collect_arranger_gp_settings()
                if hasattr(self, "_collect_arranger_gp_settings")
                else ArrangerGPSettings()
            ),
            grace_settings=(
                self._collect_grace_settings()
                if hasattr(self, "_collect_grace_settings")
                else GraceTransformSettings()
            ),
            lenient_midi_import=self.lenient_midi_import.get()
            if hasattr(self, "lenient_midi_import")
            else True,
        )
        preview_settings: dict[str, PreviewPlaybackSnapshot] = {}
        applied_by_side = getattr(self, "_preview_applied_settings", {})
        seeded_sides = getattr(self, "_preview_settings_seeded", set())
        for side, applied in applied_by_side.items():
            if not isinstance(applied, dict):
                continue
            try:
                tempo = float(applied.get("tempo", 120.0))
            except (TypeError, ValueError):
                tempo = 120.0
            try:
                loop_start = float(applied.get("loop_start", 0.0))
            except (TypeError, ValueError):
                loop_start = 0.0
            try:
                loop_end = float(applied.get("loop_end", loop_start))
            except (TypeError, ValueError):
                loop_end = loop_start
            try:
                loop_enabled_flag = self._coerce_tk_bool(
                    applied.get("loop_enabled", False)
                )
            except (TypeError, ValueError):
                loop_enabled_flag = bool(applied.get("loop_enabled", False))
            loop_enabled = loop_enabled_flag and loop_end > loop_start
            try:
                met_enabled = self._coerce_tk_bool(applied.get("metronome", False))
            except (TypeError, ValueError):
                met_enabled = bool(applied.get("metronome", False))
            if side not in seeded_sides:
                if (
                    abs(tempo - 120.0) < 1e-6
                    and not met_enabled
                    and not loop_enabled
                    and abs(loop_start) < 1e-6
                    and abs(loop_end - loop_start) < 1e-6
                ):
                    continue
            playback = self._preview_playback.get(side)
            if playback is not None:
                baseline_volume = float(playback.state.volume) * 100.0
            else:
                baseline_volume = 100.0
            try:
                stored_volume = float(applied.get("volume", baseline_volume))
            except (TypeError, ValueError):
                stored_volume = baseline_volume
            stored_volume = max(0.0, min(100.0, stored_volume))
            preview_settings[str(side)] = PreviewPlaybackSnapshot(
                tempo_bpm=tempo,
                metronome_enabled=met_enabled,
                loop_enabled=loop_enabled,
                loop_start_beat=loop_start,
                loop_end_beat=loop_end if loop_end > loop_start else loop_start,
                volume=stored_volume / 100.0,
            )
        self._viewmodel.update_preview_settings(preview_settings)

    def _current_convert_settings_snapshot(self) -> dict[str, object]:
        try:
            transpose = int(self.transpose_offset.get())
        except (tk.TclError, ValueError, AttributeError):
            transpose = getattr(self, "_transpose_applied_offset", 0)
        def _safe_int(var: tk.Variable, fallback: int) -> int:
            try:
                return int(var.get())
            except Exception:
                return fallback

        def _safe_float(var: tk.Variable) -> float | None:
            try:
                value = var.get()
            except Exception:
                return None
            if value is None:
                return None
            if isinstance(value, (int, float)):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
            text = str(value).strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None

        gp_defaults = ArrangerGPSettings()
        grace_defaults = GraceTransformSettings().normalized()

        def _gp_snapshot() -> dict[str, object]:
            if not hasattr(self, "arranger_gp_generations"):
                return {
                    "generations": gp_defaults.generations,
                    "population_size": gp_defaults.population_size,
                    "time_budget_seconds": gp_defaults.time_budget_seconds,
                    "archive_size": gp_defaults.archive_size,
                    "random_program_count": gp_defaults.random_program_count,
                    "crossover_rate": gp_defaults.crossover_rate,
                    "mutation_rate": gp_defaults.mutation_rate,
                    "log_best_programs": gp_defaults.log_best_programs,
                    "random_seed": gp_defaults.random_seed,
                    "playability_weight": gp_defaults.playability_weight,
                    "fidelity_weight": gp_defaults.fidelity_weight,
                    "tessitura_weight": gp_defaults.tessitura_weight,
                    "program_size_weight": gp_defaults.program_size_weight,
                    "contour_weight": gp_defaults.contour_weight,
                    "lcs_weight": gp_defaults.lcs_weight,
                    "apply_program_preference": gp_defaults.apply_program_preference,
                }

            def _safe_rate(var: tk.Variable, fallback: float) -> float:
                value = _safe_float(var)
                if value is None:
                    return fallback
                if value < 0.0:
                    return 0.0
                if value > 1.0:
                    return 1.0
                return value

            def _safe_weight(var: tk.Variable, fallback: float) -> float:
                value = _safe_float(var)
                if value is None or value < 0:
                    return fallback
                return value

            def _safe_choice(var: tk.Variable | str | None, fallback: str) -> str:
                try:
                    if hasattr(var, "get"):
                        text = str(var.get() or "").strip().lower()
                    else:
                        text = str(var or "").strip().lower()
                except Exception:
                    return fallback
                return text or fallback

            snapshot = {
                "generations": _safe_int(self.arranger_gp_generations, gp_defaults.generations),
                "population_size": _safe_int(
                    self.arranger_gp_population, gp_defaults.population_size
                ),
                "time_budget_seconds": _safe_float(self.arranger_gp_time_budget),
                "archive_size": _safe_int(
                    self.arranger_gp_archive_size, gp_defaults.archive_size
                ),
                "random_program_count": _safe_int(
                    self.arranger_gp_random_programs, gp_defaults.random_program_count
                ),
                "crossover_rate": _safe_rate(
                    self.arranger_gp_crossover, gp_defaults.crossover_rate
                ),
                "mutation_rate": _safe_rate(
                    self.arranger_gp_mutation, gp_defaults.mutation_rate
                ),
                "log_best_programs": _safe_int(
                    self.arranger_gp_log_best, gp_defaults.log_best_programs
                ),
                "random_seed": _safe_int(
                    self.arranger_gp_random_seed, gp_defaults.random_seed
                ),
                "playability_weight": _safe_weight(
                    self.arranger_gp_playability_weight, gp_defaults.playability_weight
                ),
                "fidelity_weight": _safe_weight(
                    self.arranger_gp_fidelity_weight, gp_defaults.fidelity_weight
                ),
                "tessitura_weight": _safe_weight(
                    self.arranger_gp_tessitura_weight, gp_defaults.tessitura_weight
                ),
                "program_size_weight": _safe_weight(
                    self.arranger_gp_program_size_weight, gp_defaults.program_size_weight
                ),
                "contour_weight": _safe_weight(
                    self.arranger_gp_contour_weight, gp_defaults.contour_weight
                ),
                "lcs_weight": _safe_weight(
                    self.arranger_gp_lcs_weight, gp_defaults.lcs_weight
                ),
                "pitch_weight": _safe_weight(
                    self.arranger_gp_pitch_weight, gp_defaults.pitch_weight
                ),
                "fidelity_priority_weight": _safe_weight(
                    self.arranger_gp_fidelity_priority_weight,
                    gp_defaults.fidelity_priority_weight,
                ),
                "range_clamp_penalty": _safe_weight(
                    self.arranger_gp_range_clamp_penalty,
                    gp_defaults.range_clamp_penalty,
                ),
                "range_clamp_melody_bias": _safe_weight(
                    self.arranger_gp_range_clamp_melody_bias,
                    gp_defaults.range_clamp_melody_bias,
                ),
                "melody_shift_weight": _safe_weight(
                    self.arranger_gp_melody_shift_weight,
                    gp_defaults.melody_shift_weight,
                ),
                "rhythm_simplify_weight": _safe_weight(
                    getattr(
                        self,
                        "arranger_gp_rhythm_simplify_weight",
                        gp_defaults.rhythm_simplify_weight,
                    ),
                    gp_defaults.rhythm_simplify_weight,
                ),
                "apply_program_preference": _safe_choice(
                    getattr(
                        self,
                        "arranger_gp_apply_preference",
                        gp_defaults.apply_program_preference,
                    ),
                    gp_defaults.apply_program_preference,
                ),
            }
            try:
                settings = ArrangerGPSettings(**snapshot)
            except TypeError:
                settings = ArrangerGPSettings()
            warning_var = getattr(self, "arranger_gp_warning", None)
            if warning_var is not None:
                warning_var.set(gp_settings_warning(settings))
            return snapshot

        def _grace_snapshot() -> dict[str, object]:
            if not hasattr(self, "_collect_grace_settings"):
                settings = grace_defaults
            else:
                try:
                    settings = self._collect_grace_settings().normalized()
                except Exception:
                    settings = grace_defaults
            return {
                "policy": settings.policy,
                "fractions": list(settings.fractions),
                "max_chain": settings.max_chain,
                "anchor_min_fraction": settings.anchor_min_fraction,
                "fold_out_of_range": settings.fold_out_of_range,
                "drop_out_of_range": settings.drop_out_of_range,
                "slow_tempo_bpm": settings.slow_tempo_bpm,
                "fast_tempo_bpm": settings.fast_tempo_bpm,
                "grace_bonus": settings.grace_bonus,
            }

        return {
            "prefer_mode": self.prefer_mode.get(),
            "prefer_flats": bool(self.prefer_flats.get()),
            "collapse_chords": bool(self.collapse_chords.get()),
            "favor_lower": bool(self.favor_lower.get()),
            "range_min": self.range_min.get(),
            "range_max": self.range_max.get(),
            "instrument_id": getattr(self, "_selected_instrument_id", ""),
            "transpose_offset": transpose,
            "arranger_mode": getattr(self, "arranger_mode", None).get()
            if hasattr(self, "arranger_mode")
            else DEFAULT_ARRANGER_MODE,
            "arranger_dp_slack": (
                bool(self.arranger_dp_slack.get()) if hasattr(self, "arranger_dp_slack") else False
            ),
            "arranger_budgets": (
                (
                    _safe_int(self.arranger_budget_octave, 1),
                    _safe_int(self.arranger_budget_rhythm, 1),
                    _safe_int(self.arranger_budget_substitution, 1),
                    _safe_int(self.arranger_budget_total, 3),
                )
                if hasattr(self, "arranger_budget_octave")
                else (1, 1, 1, 3)
            ),
            "arranger_gp_settings": _gp_snapshot(),
            "grace_settings": _grace_snapshot(),
            "lenient_midi_import": (
                bool(self.lenient_midi_import.get())
                if hasattr(self, "lenient_midi_import")
                else True
            ),
        }

    def _record_preview_import(self) -> None:
        path = self._viewmodel.state.input_path.strip()
        if not path:
            return
        normalized = os.path.abspath(path)
        self._last_imported_path = normalized
        self._last_import_settings = self._current_convert_settings_snapshot()
        if hasattr(self, "_update_reimport_button_state"):
            self._update_reimport_button_state()

    def _zoom_all(self, delta: int) -> None:
        try:
            if self.roll_orig:
                self.roll_orig.set_zoom(delta)
            if self.roll_arr:
                self.roll_arr.set_zoom(delta)
        except Exception:
            pass

    def _hzoom_all(self, multiplier: float) -> None:
        try:
            if self.roll_orig:
                self.roll_orig.set_time_zoom(multiplier)
            if self.roll_arr:
                self.roll_arr.set_time_zoom(multiplier)
            if self.staff_orig:
                self.staff_orig.set_time_zoom(multiplier)
            if self.staff_arr:
                self.staff_arr.set_time_zoom(multiplier)
            self._resync_views()
        except Exception:
            pass

    def _resync_views(self) -> None:
        try:
            if self.roll_orig and self.staff_orig:
                fraction = self.roll_orig.canvas.xview()[0]
                move_canvas_to_pixel_fraction(self.staff_orig.canvas, fraction)
            if self.roll_arr and self.staff_arr:
                fraction = self.roll_arr.canvas.xview()[0]
                move_canvas_to_pixel_fraction(self.staff_arr.canvas, fraction)
        except Exception:
            pass

    def _current_settings(self) -> TransformSettings:
        self._sync_viewmodel_settings()
        return self._viewmodel.settings()

    def _require_input_path(self, error_message: str) -> Optional[str]:
        self._sync_viewmodel_settings()
        path = self._viewmodel.state.input_path.strip()
        if not path or not os.path.exists(path):
            messagebox.showerror("Error", error_message)
            return None
        return path

    def _note_sort_key(self, note_name: str) -> tuple[float, str]:
        try:
            midi = float(self._parse_note_safe(note_name))
        except Exception:
            return (float("inf"), note_name)
        return (midi, note_name)

    def _parse_note_safe(self, note_name: str) -> int:
        from ocarina_tools import parse_note_name

        return parse_note_name(note_name)

    def _open_path(self, path: str) -> None:
        logger.info("Attempting to open path with system handler", extra={"path": path})
        if not os.path.exists(path):
            logger.warning(
                "Skipping open path because it does not exist",
                extra={"path": path},
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                try:
                    subprocess.Popen(["xdg-open", path])
                except Exception:
                    webbrowser.open("file://" + os.path.abspath(path))
        except Exception:
            logger.warning(
                "System open failed; notifying user manually",
                exc_info=True,
                extra={"path": path},
            )
            messagebox.showinfo(
                "Open location",
                f"Saved to {path}\n(Open it with your default handler.)",
            )

    def _after_conversion(self, result: ConversionResult) -> None:
        logger.info(
            "Preparing conversion success dialog",
            extra={
                "xml_path": str(result.output_xml_path),
                "mxl_path": str(result.output_mxl_path),
                "midi_path": str(result.output_midi_path),
                "shifted_notes": result.shifted_notes,
            },
        )
        self.pitch_list = list(result.used_pitches)
        self._viewmodel.state.pitch_list = list(result.used_pitches)
        self._viewmodel.state.status_message = "Converted OK."
        self.status.set("Converted OK.")
        pdf_lines = []
        for size, path in result.output_pdf_paths.items():
            pdf_lines.append(f"- {size} PDF: {path}")
        pdf_text = "\n".join(pdf_lines)
        message = (
            "Done!\n\n"
            f"Export folder: {result.output_folder}\n\n"
            f"Saved:\n- {result.output_xml_path}\n- {result.output_mxl_path}\n- {result.output_midi_path}\n\n"
            f"Range: {result.summary['range_names']['min']} to {result.summary['range_names']['max']}\n"
            f"Notes shifted (lower-bias): {result.shifted_notes}"
        )
        if pdf_text:
            message += f"\nPDF exports:\n{pdf_text}"
        self._open_path(result.output_folder)
        messagebox.showinfo("Success", message)

    def _teardown_playback(self) -> None:
        logger.info("Tearing down preview playback handles")
        self._cancel_playback_loop()
        for playback in self._preview_playback.values():
            try:
                playback.stop()
            except Exception:
                logger.exception("Failed stopping preview playback during teardown")
