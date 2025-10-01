"""Data models used by the update service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class ReleaseInfo:
    """Metadata describing an installer asset."""

    version: str
    asset_name: str
    download_url: str | None = None
    source_path: Path | None = None
    hash_value: str | None = None
    hash_url: str | None = None
    hash_path: Path | None = None
    release_notes: str | None = None
    entry_point: str | None = None


class UpdateError(RuntimeError):
    """Raised when an update cannot be downloaded or verified."""


@dataclass(frozen=True)
class InstallationPlan:
    """Describe how the downloaded update should be executed."""

    command: Tuple[str, ...]
    working_directory: Path | None = None
