"""Persistence helpers for saving and loading Ocarina Arranger project archives."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Mapping, Tuple
import zipfile

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import GraceTransformSettings, TransformSettings
from viewmodels.arranger_models import ArrangerBudgetSettings, ArrangerGPSettings

from .project_models import LoadedProject, PreviewPlaybackSnapshot, ProjectSnapshot
from .project_service_gp import deserialize_gp_settings, serialize_gp_settings


_MANIFEST_NAME = "manifest.json"
_ORIGINAL_DIR = "original"
_EXPORTS_DIR = "exports"
_VERSION = 1


class ProjectPersistenceError(RuntimeError):
    """Raised when a project archive cannot be saved or loaded."""


class ProjectService:
    """Save and load project archives bundling song data and settings."""

    def save(self, snapshot: ProjectSnapshot, destination: Path) -> Path:
        destination = Path(destination)
        input_path = snapshot.input_path
        if not input_path.exists():
            raise ProjectPersistenceError(f"Input file not found: {input_path}")

        conversion = snapshot.conversion
        if conversion is not None:
            self._ensure_export_exists(conversion.output_xml_path)
            self._ensure_export_exists(conversion.output_mxl_path)
            self._ensure_export_exists(conversion.output_midi_path)
            for label, pdf_path in conversion.output_pdf_paths.items():
                try:
                    self._ensure_export_exists(pdf_path)
                except ProjectPersistenceError as exc:
                    raise ProjectPersistenceError(f"Missing exported PDF for {label}: {pdf_path}") from exc

        manifest = self._build_manifest(snapshot)
        destination.parent.mkdir(parents=True, exist_ok=True)

        compression = zipfile.ZIP_DEFLATED if getattr(zipfile, "zlib", None) is not None else zipfile.ZIP_STORED
        try:
            with zipfile.ZipFile(destination, "w", compression=compression) as archive:
                archive.writestr(
                    _MANIFEST_NAME,
                    json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
                )
                archive.write(input_path, arcname=f"{_ORIGINAL_DIR}/{input_path.name}")
                if conversion is not None:
                    for relative_name, source_path in self._iter_export_files(conversion):
                        archive.write(source_path, arcname=f"{_EXPORTS_DIR}/{relative_name}")
        except OSError as exc:
            raise ProjectPersistenceError(str(exc)) from exc

        return destination

    def load(self, archive_path: Path, extract_dir: Path | None = None) -> LoadedProject:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise ProjectPersistenceError(f"Project archive not found: {archive_path}")

        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                try:
                    manifest_data = json.loads(archive.read(_MANIFEST_NAME).decode("utf-8"))
                except KeyError as exc:  # pragma: no cover - corrupt archive defensive guard
                    raise ProjectPersistenceError("Project archive is missing its manifest") from exc

                working_directory = self._prepare_extract_dir(extract_dir)
                self._extract_archive(archive, working_directory)
        except OSError as exc:
            raise ProjectPersistenceError(str(exc)) from exc

        input_info = manifest_data.get("input", {})
        input_name = input_info.get("filename")
        if not input_name:
            raise ProjectPersistenceError("Project manifest missing input filename")

        settings_data = manifest_data.get("settings", {})
        settings = self._load_settings(settings_data)

        pdf_options_data = manifest_data.get("pdf_options")
        pdf_options = self._load_pdf_options(pdf_options_data)

        pitch_list = [str(entry) for entry in manifest_data.get("pitch_list", [])]
        pitch_entries = [str(entry) for entry in manifest_data.get("pitch_entries", [])]
        status_message = str(manifest_data.get("status_message", ""))

        input_path = working_directory / _ORIGINAL_DIR / input_name
        conversion = self._load_conversion(manifest_data.get("conversion"), working_directory)
        preview_settings = self._load_preview_settings(
            manifest_data.get("preview_settings")
        )

        arranger_payload = manifest_data.get("arranger")
        arranger_mode = self._load_arranger_mode(arranger_payload)
        arranger_strategy = self._load_arranger_strategy(arranger_payload)
        starred_instrument_ids = self._load_starred_instruments(arranger_payload)
        arranger_dp_slack_enabled = self._load_arranger_dp_slack(arranger_payload)
        arranger_budgets = self._load_arranger_budgets(arranger_payload)
        arranger_gp_settings = self._load_arranger_gp_settings(arranger_payload)

        return LoadedProject(
            archive_path=archive_path,
            working_directory=working_directory,
            input_path=input_path,
            settings=settings,
            pdf_options=pdf_options,
            pitch_list=pitch_list,
            pitch_entries=pitch_entries,
            status_message=status_message,
            conversion=conversion,
            preview_settings=preview_settings,
            arranger_mode=arranger_mode,
            arranger_strategy=arranger_strategy,
            starred_instrument_ids=starred_instrument_ids,
            arranger_dp_slack_enabled=arranger_dp_slack_enabled,
            arranger_budgets=arranger_budgets,
            arranger_gp_settings=arranger_gp_settings,
            grace_settings=settings.grace_settings,
        )

    def _build_manifest(self, snapshot: ProjectSnapshot) -> Dict[str, Any]:
        settings_payload = asdict(snapshot.settings)
        settings_payload["selected_part_ids"] = list(
            snapshot.settings.selected_part_ids
        )
        grace_payload = asdict(snapshot.settings.grace_settings.normalized())
        fractions = grace_payload.get("fractions")
        if isinstance(fractions, tuple):
            grace_payload["fractions"] = list(fractions)
        settings_payload["grace_settings"] = grace_payload

        manifest: Dict[str, Any] = {
            "version": _VERSION,
            "input": {"filename": snapshot.input_path.name},
            "settings": settings_payload,
            "pitch_list": list(snapshot.pitch_list),
            "pitch_entries": list(snapshot.pitch_entries),
            "status_message": snapshot.status_message,
        }
        arranger_payload = self._build_arranger_payload(snapshot)
        if arranger_payload:
            manifest["arranger"] = arranger_payload
        if snapshot.preview_settings:
            manifest["preview_settings"] = {
                side: {
                    "tempo_bpm": float(state.tempo_bpm),
                    "metronome_enabled": bool(state.metronome_enabled),
                    "loop_enabled": bool(state.loop_enabled),
                    "loop_start": float(state.loop_start_beat),
                    "loop_end": float(state.loop_end_beat),
                    "volume": float(state.volume),
                }
                for side, state in snapshot.preview_settings.items()
            }
        if snapshot.pdf_options is not None:
            pdf = snapshot.pdf_options
            manifest["pdf_options"] = {
                "page_size": pdf.page_size,
                "orientation": pdf.orientation,
                "columns": pdf.columns,
                "include_piano_roll": pdf.include_piano_roll,
                "include_staff": pdf.include_staff,
                "include_text": pdf.include_text,
                "include_fingerings": pdf.include_fingerings,
            }
        conversion = snapshot.conversion
        if conversion is not None:
            manifest["conversion"] = {
                "summary": conversion.summary,
                "shifted_notes": conversion.shifted_notes,
                "used_pitches": list(conversion.used_pitches),
                "exports": {
                    "xml": Path(conversion.output_xml_path).name,
                    "mxl": Path(conversion.output_mxl_path).name,
                    "midi": Path(conversion.output_midi_path).name,
                    "pdfs": {
                        label: f"pdf/{Path(path).name}"
                        for label, path in conversion.output_pdf_paths.items()
                    },
                },
            }
        return manifest

    def _build_arranger_payload(self, snapshot: ProjectSnapshot) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if snapshot.arranger_mode:
            payload["mode"] = snapshot.arranger_mode
        if snapshot.arranger_strategy:
            payload["strategy"] = snapshot.arranger_strategy
        if snapshot.starred_instrument_ids:
            payload["starred_instrument_ids"] = list(snapshot.starred_instrument_ids)
        if snapshot.arranger_dp_slack_enabled is not None:
            payload["dp_slack_enabled"] = bool(snapshot.arranger_dp_slack_enabled)
        if snapshot.arranger_budgets is not None:
            budgets = snapshot.arranger_budgets
            payload["budgets"] = {
                "max_octave_edits": int(budgets.max_octave_edits),
                "max_rhythm_edits": int(budgets.max_rhythm_edits),
                "max_substitutions": int(budgets.max_substitutions),
                "max_steps_per_span": int(budgets.max_steps_per_span),
            }
        if snapshot.arranger_gp_settings is not None:
            payload["gp_settings"] = serialize_gp_settings(snapshot.arranger_gp_settings)
        return payload

    def _load_preview_settings(
        self, data: Dict[str, Any] | None
    ) -> dict[str, PreviewPlaybackSnapshot]:
        if not data:
            return {}
        preview_settings: dict[str, PreviewPlaybackSnapshot] = {}
        for side, entry in data.items():
            try:
                tempo = float(entry.get("tempo_bpm", 120.0))
            except (TypeError, ValueError):
                tempo = 120.0
            try:
                loop_start = float(entry.get("loop_start", 0.0))
            except (TypeError, ValueError):
                loop_start = 0.0
            try:
                loop_end = float(entry.get("loop_end", loop_start))
            except (TypeError, ValueError):
                loop_end = loop_start
            loop_enabled = bool(entry.get("loop_enabled", False)) and loop_end > loop_start
            try:
                volume = float(entry.get("volume", 1.0))
            except (TypeError, ValueError):
                volume = 1.0
            volume = max(0.0, min(1.0, volume))
            preview_settings[str(side)] = PreviewPlaybackSnapshot(
                tempo_bpm=tempo,
                metronome_enabled=bool(entry.get("metronome_enabled", False)),
                loop_enabled=loop_enabled,
                loop_start_beat=loop_start,
                loop_end_beat=loop_end if loop_end > loop_start else loop_start,
                volume=volume,
            )
        return preview_settings

    def _iter_export_files(self, conversion: ConversionResult) -> Iterable[Tuple[str, Path]]:
        yield Path(conversion.output_xml_path).name, Path(conversion.output_xml_path)
        yield Path(conversion.output_mxl_path).name, Path(conversion.output_mxl_path)
        yield Path(conversion.output_midi_path).name, Path(conversion.output_midi_path)
        for path in conversion.output_pdf_paths.values():
            yield f"pdf/{Path(path).name}", Path(path)

    def _load_settings(self, data: Dict[str, Any]) -> TransformSettings:
        grace_settings = self._load_grace_settings(data.get("grace_settings"))
        return TransformSettings(
            prefer_mode=str(data.get("prefer_mode", "auto")),
            range_min=str(data.get("range_min", "")),
            range_max=str(data.get("range_max", "")),
            prefer_flats=bool(data.get("prefer_flats", True)),
            collapse_chords=bool(data.get("collapse_chords", True)),
            favor_lower=bool(data.get("favor_lower", False)),
            transpose_offset=int(data.get("transpose_offset", 0)),
            instrument_id=str(data.get("instrument_id", "")),
            selected_part_ids=self._load_selected_part_ids(data.get("selected_part_ids")),
            grace_settings=grace_settings,
        )

    def _load_pdf_options(self, data: Dict[str, Any] | None) -> PdfExportOptions | None:
        if data is None:
            return None
        return PdfExportOptions(
            page_size=str(data.get("page_size", "A4")),
            orientation=str(data.get("orientation", "portrait")),
            columns=data.get("columns"),
            include_piano_roll=bool(data.get("include_piano_roll", True)),
            include_staff=bool(data.get("include_staff", True)),
            include_text=bool(data.get("include_text", True)),
            include_fingerings=bool(data.get("include_fingerings", True)),
        )

    def _load_conversion(
        self, data: Dict[str, Any] | None, working_directory: Path
    ) -> ConversionResult | None:
        if data is None:
            return None

        exports = data.get("exports", {})
        exports_dir = working_directory / _EXPORTS_DIR
        xml_path = exports_dir / exports.get("xml", "")
        mxl_path = exports_dir / exports.get("mxl", "")
        midi_path = exports_dir / exports.get("midi", "")
        pdf_entries = exports.get("pdfs", {})
        pdf_paths = {
            label: str((exports_dir / rel_path).resolve())
            for label, rel_path in pdf_entries.items()
        }
        return ConversionResult(
            summary=data.get("summary", {}),
            shifted_notes=int(data.get("shifted_notes", 0)),
            used_pitches=[str(entry) for entry in data.get("used_pitches", [])],
            output_xml_path=str(xml_path.resolve()),
            output_mxl_path=str(mxl_path.resolve()),
            output_midi_path=str(midi_path.resolve()),
            output_pdf_paths=pdf_paths,
            output_folder=str((exports_dir).resolve()),
        )

    @staticmethod
    def _load_selected_part_ids(entries: Any) -> tuple[str, ...]:
        if entries in (None, ""):
            return ()
        normalized: list[str] = []
        seen: set[str] = set()
        if isinstance(entries, (list, tuple)):
            iterator = entries
        else:
            iterator = [entries]
        for entry in iterator:
            if entry is None:
                continue
            text = str(entry).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return tuple(normalized)

    def _load_grace_settings(self, data: Any) -> GraceTransformSettings:
        if isinstance(data, GraceTransformSettings):
            return data.normalized()
        if not isinstance(data, Mapping):
            return GraceTransformSettings()

        policy = str(data.get("policy", "tempo-weighted"))

        fractions_raw = data.get("fractions", ())
        fractions: list[float] = []
        if isinstance(fractions_raw, (list, tuple)):
            for value in fractions_raw:
                try:
                    fractions.append(float(value))
                except (TypeError, ValueError):
                    continue
        else:
            fractions = list(GraceTransformSettings().fractions)

        def _float(key: str, fallback: float) -> float:
            value = data.get(key, fallback)
            if value is None:
                return fallback
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        def _int(key: str, fallback: int) -> int:
            value = data.get(key, fallback)
            try:
                return int(value)
            except (TypeError, ValueError):
                return fallback

        def _bool(key: str, fallback: bool) -> bool:
            value = data.get(key, fallback)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                try:
                    return bool(int(value))
                except (TypeError, ValueError):
                    return fallback
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "t", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "f", "no", "off", ""}:
                    return False
            return fallback

        settings = GraceTransformSettings(
            policy=policy,
            fractions=tuple(fractions),
            max_chain=_int("max_chain", 3),
            anchor_min_fraction=_float("anchor_min_fraction", 0.25),
            fold_out_of_range=_bool("fold_out_of_range", True),
            drop_out_of_range=_bool("drop_out_of_range", True),
            slow_tempo_bpm=_float("slow_tempo_bpm", 60.0),
            fast_tempo_bpm=_float("fast_tempo_bpm", 132.0),
            grace_bonus=_float("grace_bonus", 0.25),
        )
        return settings.normalized()

    def _load_arranger_mode(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        mode = data.get("mode")
        return str(mode) if isinstance(mode, str) and mode else None

    def _load_arranger_strategy(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        strategy = data.get("strategy")
        return str(strategy) if isinstance(strategy, str) and strategy else None

    def _load_starred_instruments(self, data: Any) -> tuple[str, ...]:
        if not isinstance(data, dict):
            return ()
        return self._load_selected_part_ids(data.get("starred_instrument_ids"))

    def _load_arranger_dp_slack(self, data: Any) -> bool | None:
        if not isinstance(data, dict):
            return None
        raw_value = data.get("dp_slack_enabled")
        if isinstance(raw_value, bool):
            return raw_value
        if raw_value in (0, 1):
            return bool(raw_value)
        return None

    def _load_arranger_budgets(
        self, data: Any
    ) -> ArrangerBudgetSettings | None:
        if not isinstance(data, dict):
            return None
        raw_budgets = data.get("budgets")
        if not isinstance(raw_budgets, dict):
            return None
        try:
            budgets = ArrangerBudgetSettings(
                max_octave_edits=int(raw_budgets.get("max_octave_edits", 1)),
                max_rhythm_edits=int(raw_budgets.get("max_rhythm_edits", 1)),
                max_substitutions=int(raw_budgets.get("max_substitutions", 1)),
                max_steps_per_span=int(raw_budgets.get("max_steps_per_span", 3)),
            )
        except (TypeError, ValueError):
            return ArrangerBudgetSettings().normalized()
        return budgets.normalized()

    def _load_arranger_gp_settings(
        self, data: Any
    ) -> ArrangerGPSettings | None:
        if not isinstance(data, dict):
            return None
        raw_gp = data.get("gp_settings")
        if not isinstance(raw_gp, Mapping):
            return None
        defaults = ArrangerGPSettings()
        return deserialize_gp_settings(raw_gp, defaults)

    @staticmethod
    def _ensure_export_exists(path: str) -> None:
        if not Path(path).exists():
            raise ProjectPersistenceError(f"Export artifact missing: {path}")

    @staticmethod
    def _prepare_extract_dir(target: Path | None) -> Path:
        if target is not None:
            path = Path(target)
            path.mkdir(parents=True, exist_ok=True)
            return path
        tmp = tempfile.mkdtemp(prefix="ocarina_project_")
        return Path(tmp)

    def _extract_archive(self, archive: zipfile.ZipFile, target: Path) -> None:
        normalized_target = Path(target).resolve()
        for member in archive.infolist():
            normalized_name = member.filename.replace("\\", "/")
            member_path = PurePosixPath(normalized_name)

            if member_path.is_absolute() or any(part == ".." for part in member_path.parts):
                raise ProjectPersistenceError("Project archive contains unsafe path entry")

            destination = normalized_target.joinpath(*member_path.parts)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target_file:
                shutil.copyfileobj(source, target_file)


__all__ = [
    "LoadedProject",
    "ProjectPersistenceError",
    "ProjectService",
    "ProjectSnapshot",
    "PreviewPlaybackSnapshot",
]
