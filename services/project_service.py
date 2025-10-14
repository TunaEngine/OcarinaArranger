"""Persistence helpers for saving and loading Ocarina Arranger project archives."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Tuple
import zipfile

from ocarina_gui.conversion import ConversionResult
from ocarina_gui.pdf_export.types import PdfExportOptions
from ocarina_gui.settings import TransformSettings


_MANIFEST_NAME = "manifest.json"
_ORIGINAL_DIR = "original"
_EXPORTS_DIR = "exports"
_VERSION = 1


class ProjectPersistenceError(RuntimeError):
    """Raised when a project archive cannot be saved or loaded."""


@dataclass(frozen=True)
class ProjectSnapshot:
    """Aggregate of state required to persist a project archive."""

    input_path: Path
    settings: TransformSettings
    pdf_options: PdfExportOptions | None
    pitch_list: list[str]
    pitch_entries: list[str]
    status_message: str
    conversion: ConversionResult | None
    preview_settings: dict[str, "PreviewPlaybackSnapshot"] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedProject:
    """Deserialized project data extracted from an archive."""

    archive_path: Path
    working_directory: Path
    input_path: Path
    settings: TransformSettings
    pdf_options: PdfExportOptions | None
    pitch_list: list[str]
    pitch_entries: list[str]
    status_message: str
    conversion: ConversionResult | None
    preview_settings: dict[str, "PreviewPlaybackSnapshot"]


@dataclass(frozen=True)
class PreviewPlaybackSnapshot:
    """Persisted playback adjustments for a preview pane."""

    tempo_bpm: float = 120.0
    metronome_enabled: bool = False
    loop_enabled: bool = False
    loop_start_beat: float = 0.0
    loop_end_beat: float = 0.0


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
        )

    def _build_manifest(self, snapshot: ProjectSnapshot) -> Dict[str, Any]:
        settings_payload = asdict(snapshot.settings)
        settings_payload["selected_part_ids"] = list(
            snapshot.settings.selected_part_ids
        )

        manifest: Dict[str, Any] = {
            "version": _VERSION,
            "input": {"filename": snapshot.input_path.name},
            "settings": settings_payload,
            "pitch_list": list(snapshot.pitch_list),
            "pitch_entries": list(snapshot.pitch_entries),
            "status_message": snapshot.status_message,
        }
        if snapshot.preview_settings:
            manifest["preview_settings"] = {
                side: {
                    "tempo_bpm": float(state.tempo_bpm),
                    "metronome_enabled": bool(state.metronome_enabled),
                    "loop_enabled": bool(state.loop_enabled),
                    "loop_start": float(state.loop_start_beat),
                    "loop_end": float(state.loop_end_beat),
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
            preview_settings[str(side)] = PreviewPlaybackSnapshot(
                tempo_bpm=tempo,
                metronome_enabled=bool(entry.get("metronome_enabled", False)),
                loop_enabled=loop_enabled,
                loop_start_beat=loop_start,
                loop_end_beat=loop_end if loop_end > loop_start else loop_start,
            )
        return preview_settings

    def _iter_export_files(self, conversion: ConversionResult) -> Iterable[Tuple[str, Path]]:
        yield Path(conversion.output_xml_path).name, Path(conversion.output_xml_path)
        yield Path(conversion.output_mxl_path).name, Path(conversion.output_mxl_path)
        yield Path(conversion.output_midi_path).name, Path(conversion.output_midi_path)
        for path in conversion.output_pdf_paths.values():
            yield f"pdf/{Path(path).name}", Path(path)

    def _load_settings(self, data: Dict[str, Any]) -> TransformSettings:
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
