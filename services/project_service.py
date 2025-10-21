"""Persistence helpers for saving and loading Ocarina Arranger project archives."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
import zipfile

from .project_manifest import (
    build_manifest,
    iter_export_files,
    load_arranger_budgets,
    load_arranger_dp_slack,
    load_arranger_gp_settings,
    load_arranger_mode,
    load_arranger_strategy,
    load_conversion,
    load_pdf_options,
    load_preview_settings,
    load_settings,
    load_starred_instruments,
)
from .project_models import LoadedProject, PreviewPlaybackSnapshot, ProjectSnapshot


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

        manifest = build_manifest(snapshot, _VERSION)
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
                    for relative_name, source_path in iter_export_files(conversion):
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
        settings = load_settings(settings_data)

        pdf_options_data = manifest_data.get("pdf_options")
        pdf_options = load_pdf_options(pdf_options_data)

        pitch_list = [str(entry) for entry in manifest_data.get("pitch_list", [])]
        pitch_entries = [str(entry) for entry in manifest_data.get("pitch_entries", [])]
        status_message = str(manifest_data.get("status_message", ""))

        input_path = working_directory / _ORIGINAL_DIR / input_name
        conversion = load_conversion(
            manifest_data.get("conversion"), working_directory, _EXPORTS_DIR
        )
        preview_settings = load_preview_settings(manifest_data.get("preview_settings"))

        arranger_payload = manifest_data.get("arranger")
        arranger_mode = load_arranger_mode(arranger_payload)
        arranger_strategy = load_arranger_strategy(arranger_payload)
        starred_instrument_ids = load_starred_instruments(arranger_payload)
        arranger_dp_slack_enabled = load_arranger_dp_slack(arranger_payload)
        arranger_budgets = load_arranger_budgets(arranger_payload)
        arranger_gp_settings = load_arranger_gp_settings(arranger_payload)

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
            subhole_settings=settings.subhole_settings,
        )

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
