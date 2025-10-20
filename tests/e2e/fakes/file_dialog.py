from __future__ import annotations

from collections import deque
from typing import Deque, Sequence

from adapters.file_dialog import FileDialogAdapter
from ocarina_tools.parts import MusicXmlPartInfo


class FakeFileDialogAdapter(FileDialogAdapter):
    """Deterministic dialog stub that returns queued responses."""

    def __init__(self) -> None:
        self._open_paths: Deque[str | None] = deque()
        self._save_paths: Deque[str | None] = deque()
        self._open_project_paths: Deque[str | None] = deque()
        self._save_project_paths: Deque[str | None] = deque()
        self._open_gp_preset_paths: Deque[str | None] = deque()
        self._save_gp_preset_paths: Deque[str | None] = deque()
        self._part_selections: Deque[Sequence[str] | None] = deque()

    def queue_open_path(self, path: str | None) -> None:
        self._open_paths.append(path)

    def queue_save_path(self, path: str | None) -> None:
        self._save_paths.append(path)

    def queue_open_project_path(self, path: str | None) -> None:
        self._open_project_paths.append(path)

    def queue_save_project_path(self, path: str | None) -> None:
        self._save_project_paths.append(path)

    def queue_open_gp_preset_path(self, path: str | None) -> None:
        self._open_gp_preset_paths.append(path)

    def queue_save_gp_preset_path(self, path: str | None) -> None:
        self._save_gp_preset_paths.append(path)

    def queue_part_selection(self, selection: Sequence[str] | None) -> None:
        self._part_selections.append(selection)

    def ask_open_path(self) -> str | None:
        if not self._open_paths:
            raise AssertionError("No queued open paths for FakeFileDialogAdapter")
        return self._open_paths.popleft()

    def ask_save_path(self, suggested_name: str) -> str | None:  # noqa: ARG002 - protocol compatibility
        if not self._save_paths:
            raise AssertionError("No queued save paths for FakeFileDialogAdapter")
        return self._save_paths.popleft()

    def ask_open_project_path(self) -> str | None:
        if not self._open_project_paths:
            raise AssertionError("No queued project-open paths for FakeFileDialogAdapter")
        return self._open_project_paths.popleft()

    def ask_save_project_path(self, suggested_name: str) -> str | None:  # noqa: ARG002 - protocol compatibility
        if not self._save_project_paths:
            raise AssertionError("No queued project-save paths for FakeFileDialogAdapter")
        return self._save_project_paths.popleft()

    def ask_open_gp_preset_path(self) -> str | None:
        if not self._open_gp_preset_paths:
            raise AssertionError("No queued GP preset paths for FakeFileDialogAdapter")
        return self._open_gp_preset_paths.popleft()

    def ask_save_gp_preset_path(self, suggested_name: str) -> str | None:  # noqa: ARG002 - protocol compatibility
        if not self._save_gp_preset_paths:
            raise AssertionError("No queued GP preset save paths for FakeFileDialogAdapter")
        return self._save_gp_preset_paths.popleft()

    def ask_select_parts(
        self,
        parts: Sequence[MusicXmlPartInfo],
        preselected: Sequence[str],
    ) -> Sequence[str] | None:
        if not self._part_selections:
            return tuple(preselected)
        return self._part_selections.popleft()
