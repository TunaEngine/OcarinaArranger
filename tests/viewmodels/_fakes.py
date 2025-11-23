from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from adapters.file_dialog import FileDialogAdapter
from ocarina_gui.conversion import ConversionResult
from ocarina_gui.preview import PreviewData
from ocarina_gui.settings import TransformSettings
from ocarina_tools.parts import MusicXmlPartInfo
from services.project_service import LoadedProject, ProjectPersistenceError, ProjectSnapshot


class FakeDialogs(FileDialogAdapter):
    def __init__(
        self,
        *,
        open_path: Optional[str] = None,
        save_path: Optional[str] = None,
        project_open_path: Optional[str] = None,
        project_save_path: Optional[str] = None,
        gp_open_path: Optional[str] = None,
        gp_save_path: Optional[str] = None,
        part_selection: Sequence[str] | None | object = Ellipsis,
    ) -> None:
        self._open_path = open_path
        self._save_path = save_path
        self._project_open_path = project_open_path
        self._project_save_path = project_save_path
        self._gp_open_path = gp_open_path
        self._gp_save_path = gp_save_path
        self._part_selection = part_selection
        self._has_explicit_part_selection = part_selection is not Ellipsis
        self.open_calls: list[None] = []
        self.save_calls: list[str] = []
        self.project_open_calls: list[None] = []
        self.project_save_calls: list[str] = []
        self.gp_open_calls: list[None] = []
        self.gp_save_calls: list[str] = []
        self.part_selection_calls: list[
            tuple[tuple[MusicXmlPartInfo, ...], tuple[str, ...]]
        ] = []

    def ask_open_path(self) -> str | None:
        self.open_calls.append(None)
        return self._open_path

    def ask_save_path(self, suggested_name: str) -> str | None:
        self.save_calls.append(suggested_name)
        return self._save_path

    def ask_open_project_path(self) -> str | None:
        self.project_open_calls.append(None)
        return self._project_open_path

    def ask_save_project_path(self, suggested_name: str) -> str | None:
        self.project_save_calls.append(suggested_name)
        return self._project_save_path

    def ask_open_gp_preset_path(self) -> str | None:
        self.gp_open_calls.append(None)
        return self._gp_open_path

    def ask_save_gp_preset_path(self, suggested_name: str) -> str | None:
        self.gp_save_calls.append(suggested_name)
        return self._gp_save_path

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> Sequence[str] | None:
        snapshot = tuple(parts)
        self.part_selection_calls.append((snapshot, tuple(preselected)))
        if not self._has_explicit_part_selection:
            return tuple(preselected)
        if self._part_selection is None:
            return None
        return tuple(self._part_selection)


@dataclass
class StubScoreService:
    preview: Optional[PreviewData] = None
    conversion: Optional[ConversionResult] = None
    preview_error: Optional[Exception] = None
    convert_error: Optional[Exception] = None
    last_preview_settings: Optional[TransformSettings] = None
    last_convert_settings: Optional[TransformSettings] = None
    last_pdf_options: object | None = None
    part_metadata: tuple[MusicXmlPartInfo, ...] = ()
    part_metadata_calls: list[str] = field(default_factory=list)
    last_midi_mode: Optional[str] = None
    metadata_error: Optional[Exception] = None

    def build_preview(
        self, path: str, settings: TransformSettings, *, midi_mode: str = "auto"
    ) -> PreviewData:
        if self.preview_error:
            raise self.preview_error
        assert self.preview is not None
        self.last_preview_settings = settings
        self.last_midi_mode = midi_mode
        return self.preview

    def convert(
        self,
        path: str,
        output_xml_path: str,
        settings: TransformSettings,
        pdf_options,
        *,
        midi_mode: str = "auto",
        arranged_events=None,
        arranged_pulses_per_quarter: int | None = None,
    ) -> ConversionResult:
        if self.convert_error:
            raise self.convert_error
        assert self.conversion is not None
        self.last_convert_settings = settings
        self.last_midi_mode = midi_mode
        self.last_pdf_options = pdf_options
        return self.conversion

    def load_part_metadata(
        self, path: str, *, midi_mode: str = "auto"
    ) -> tuple[MusicXmlPartInfo, ...]:
        self.part_metadata_calls.append(path)
        self.last_midi_mode = midi_mode
        if self.metadata_error:
            raise self.metadata_error
        return self.part_metadata


@dataclass
class StubProjectService:
    saved_snapshots: list[ProjectSnapshot] = field(default_factory=list)
    last_destination: Optional[Path] = None
    load_result: Optional[LoadedProject] = None
    save_error: Optional[Exception] = None
    load_error: Optional[Exception] = None

    def save(self, snapshot: ProjectSnapshot, destination: Path) -> Path:
        if self.save_error:
            raise self.save_error
        self.saved_snapshots.append(snapshot)
        self.last_destination = destination
        return destination

    def load(self, archive_path: Path, extract_dir: Optional[Path] = None) -> LoadedProject:
        if self.load_error:
            raise ProjectPersistenceError(str(self.load_error))
        if self.load_result is None:
            raise ProjectPersistenceError("No project loaded")
        return self.load_result
