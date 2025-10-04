from __future__ import annotations

from collections import deque
from typing import Deque

from adapters.file_dialog import FileDialogAdapter


class FakeFileDialogAdapter(FileDialogAdapter):
    """Deterministic dialog stub that returns queued responses."""

    def __init__(self) -> None:
        self._open_paths: Deque[str | None] = deque()
        self._save_paths: Deque[str | None] = deque()
        self._open_project_paths: Deque[str | None] = deque()
        self._save_project_paths: Deque[str | None] = deque()

    def queue_open_path(self, path: str | None) -> None:
        self._open_paths.append(path)

    def queue_save_path(self, path: str | None) -> None:
        self._save_paths.append(path)

    def queue_open_project_path(self, path: str | None) -> None:
        self._open_project_paths.append(path)

    def queue_save_project_path(self, path: str | None) -> None:
        self._save_project_paths.append(path)

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
