from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Iterable

from services.project_service import (
    LoadedProject,
    ProjectPersistenceError,
    ProjectSnapshot,
)


@dataclass(slots=True)
class SaveCall:
    snapshot: ProjectSnapshot
    destination: Path


@dataclass(slots=True)
class LoadCall:
    path: Path
    extract_dir: Path | None


@dataclass(slots=True)
class FakeProjectService:
    """Deterministic stand-in for :class:`ProjectService`."""

    save_calls: list[SaveCall] = field(default_factory=list)
    load_calls: list[LoadCall] = field(default_factory=list)
    _save_results: Deque[Path | Exception] = field(default_factory=deque)
    _load_results: Deque[LoadedProject | Exception] = field(default_factory=deque)
    _saved_snapshots: list[tuple[ProjectSnapshot, Path]] = field(default_factory=list)

    def queue_save_result(self, result: Path | Exception) -> None:
        self._save_results.append(result)

    def queue_load_result(self, result: LoadedProject | Exception) -> None:
        self._load_results.append(result)

    def saved_destinations(self) -> Iterable[Path]:
        return (destination for _snapshot, destination in self._saved_snapshots)

    def save(self, snapshot: ProjectSnapshot, destination: Path) -> Path:
        destination = Path(destination)
        self.save_calls.append(SaveCall(snapshot=snapshot, destination=destination))
        self._saved_snapshots.append((snapshot, destination))
        if self._save_results:
            outcome = self._save_results.popleft()
            if isinstance(outcome, Exception):
                raise outcome
            return Path(outcome)
        return destination

    def load(self, path: Path, extract_dir: Path | None = None) -> LoadedProject:
        archive_path = Path(path)
        self.load_calls.append(LoadCall(path=archive_path, extract_dir=extract_dir))
        if self._load_results:
            outcome = self._load_results.popleft()
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        if not self._saved_snapshots:
            raise ProjectPersistenceError("No project snapshots available in fake service")

        snapshot, saved_destination = self._saved_snapshots[-1]
        working_directory = saved_destination.parent / f"{saved_destination.stem}_work"
        input_path = working_directory / snapshot.input_path.name

        return LoadedProject(
            archive_path=archive_path,
            working_directory=working_directory,
            input_path=input_path,
            settings=snapshot.settings,
            pdf_options=snapshot.pdf_options,
            pitch_list=list(snapshot.pitch_list),
            pitch_entries=list(snapshot.pitch_entries),
            status_message=snapshot.status_message,
            conversion=snapshot.conversion,
            preview_settings=dict(snapshot.preview_settings),
        )

