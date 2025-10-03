"""Archive handling helpers for the update service."""

from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from services.update import constants
from services.update.models import UpdateError


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArchiveExtraction:
    """Describe the extracted archive contents and entry point."""

    root: Path
    entry_path: Path

    @property
    def relative_entry(self) -> Path:
        try:
            return self.entry_path.relative_to(self.root)
        except ValueError:
            try:
                root_resolved = self.root.resolve(strict=True)
                entry_resolved = self.entry_path.resolve(strict=True)
            except FileNotFoundError as exc:  # pragma: no cover - defensive guard
                raise UpdateError(
                    "Extracted update files were unexpectedly removed"
                ) from exc
            try:
                return entry_resolved.relative_to(root_resolved)
            except ValueError as exc:
                relative_via_samefile = _relative_path_via_samefile(
                    root_resolved, entry_resolved
                )
                if relative_via_samefile is not None:
                    return relative_via_samefile
                raise UpdateError(
                    "Executable entry is not located within the extracted archive"
                ) from exc


def _relative_path_via_samefile(root: Path, entry: Path) -> Path | None:
    """Compute ``entry`` relative to ``root`` using ``samefile`` semantics."""

    relative_parts: list[str] = []
    current = entry
    try:
        while True:
            if current.samefile(root):
                return Path(*reversed(relative_parts))
            parent = current.parent
            if parent == current:
                return None
            relative_parts.append(current.name)
            current = parent
    except OSError:
        return None


def extract_archive(archive_path: Path) -> Path:
    _LOGGER.info("Extracting update archive %s", archive_path)
    target_dir = Path(tempfile.mkdtemp(prefix="ocarina-update-unpacked-"))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            extract_zip_safely(archive, target_dir)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateError(f"Failed to extract update archive: {exc}") from exc
    _LOGGER.debug("Archive extracted to %s", target_dir)
    return target_dir


def locate_archive_entry(root: Path, entry_point: str | None) -> ArchiveExtraction:
    """Return an :class:`ArchiveExtraction` describing the executable inside ``root``."""

    if entry_point:
        _LOGGER.debug("Attempting to locate specified archive entry %s", entry_point)
        entry_path = resolve_entry_point(root, entry_point)
        if entry_path is not None:
            _LOGGER.info("Resolved configured entry point to %s", entry_path)
            return ArchiveExtraction(root, entry_path)

    default_entry = constants.DEFAULT_ARCHIVE_ENTRY_POINT
    if default_entry:
        _LOGGER.debug("Falling back to default archive entry %s", default_entry)
        entry_path = resolve_entry_point(root, default_entry)
        if entry_path is not None:
            _LOGGER.info("Resolved default entry point to %s", entry_path)
            return ArchiveExtraction(root, entry_path)

    executable = find_executable_in_directory(root)
    if executable is None:
        raise UpdateError("Update archive did not contain a Windows executable")
    _LOGGER.info("Auto-detected executable %s in archive", executable)
    return ArchiveExtraction(root, executable)
def resolve_entry_point(root: Path, entry_point: str) -> Path | None:
    normalised = entry_point.strip()
    if not normalised:
        return None
    components = [part for part in normalised.split("/") if part and part != "."]
    candidate = root.joinpath(*components).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if candidate.exists():
        _LOGGER.debug("Located archive entry candidate %s", candidate)
        return candidate
    return None


def extract_zip_safely(archive: zipfile.ZipFile, target_dir: Path) -> None:
    root = target_dir.resolve()
    total_bytes = 0
    processed_entries = 0
    for member in archive.infolist():
        name = member.filename
        if not name:
            continue
        processed_entries += 1
        if processed_entries > constants.MAX_ARCHIVE_ENTRIES:
            _LOGGER.error(
                "Archive entry count %s exceeded limit %s",
                processed_entries,
                constants.MAX_ARCHIVE_ENTRIES,
            )
            raise UpdateError("Update archive contained too many entries")
        path = Path(name)
        if path.is_absolute():
            raise UpdateError("Update archive contained an absolute path entry")
        destination = (root / path).resolve()
        try:
            destination.relative_to(root)
        except ValueError:
            raise UpdateError("Update archive contained an unsafe relative path")
        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if member.file_size > constants.MAX_ARCHIVE_FILE_SIZE:
            _LOGGER.error(
                "Archive member %s exceeded file size limit (%s > %s)",
                name,
                member.file_size,
                constants.MAX_ARCHIVE_FILE_SIZE,
            )
            raise UpdateError("Update archive contained an oversized file")
        if member.compress_size == 0 and member.file_size > 0:
            _LOGGER.error("Archive member %s reported zero compression size", name)
            raise UpdateError("Update archive contained a suspiciously compressed file")
        if (
            member.compress_size > 0
            and member.file_size > member.compress_size * constants.MAX_COMPRESSION_RATIO
        ):
            _LOGGER.error(
                "Archive member %s exceeded compression ratio limit (%s > %s)",
                name,
                member.file_size,
                member.compress_size * constants.MAX_COMPRESSION_RATIO,
            )
            raise UpdateError("Update archive exceeded safe compression ratio")
        total_bytes += member.file_size
        if total_bytes > constants.MAX_ARCHIVE_TOTAL_BYTES:
            _LOGGER.error(
                "Archive expanded to %s bytes which exceeds limit %s",
                total_bytes,
                constants.MAX_ARCHIVE_TOTAL_BYTES,
            )
            raise UpdateError("Update archive expanded beyond safe limits")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)
        _LOGGER.debug("Extracted archive member %s to %s", name, destination)

    _LOGGER.info(
        "Extracted %s entries totalling %s bytes", processed_entries, total_bytes
    )


def find_executable_in_directory(directory: Path) -> Path | None:
    candidates: list[Path] = []
    for extension in constants.WINDOWS_EXECUTABLE_EXTENSIONS:
        candidates.extend(
            path
            for path in directory.rglob(f"*{extension}")
            if path.is_file()
        )
    if not candidates:
        return None

    for candidate in candidates:
        if candidate.name.lower() in constants.PREFERRED_EXECUTABLE_NAMES:
            _LOGGER.debug("Selected preferred executable %s", candidate)
            return candidate

    def _sort_key(path: Path) -> tuple[int, str]:
        try:
            depth = len(path.relative_to(directory).parts)
        except ValueError:
            depth = len(path.parts)
        return (depth, path.name.lower())

    candidates.sort(key=_sort_key)
    chosen = candidates[0]
    _LOGGER.debug("Selected executable %s from archive", chosen)
    return chosen
