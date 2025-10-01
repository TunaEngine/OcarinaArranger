"""Constants shared across the update service modules."""

from __future__ import annotations

GITHUB_REPO = "TunaEngine/OcarinaArranger"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

WINDOWS_ARCHIVE_EXTENSIONS = (".zip",)
WINDOWS_EXECUTABLE_EXTENSIONS = (".exe",)
PREFERRED_EXECUTABLE_NAMES = {"ocarinaarranger.exe"}
DEFAULT_ARCHIVE_ENTRY_POINT = "OcarinaArranger/OcarinaArranger.exe"
UPDATE_FAILURE_MARKER_SUFFIX = ".update_failed.json"

MAX_ARCHIVE_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MiB
MAX_ARCHIVE_FILE_SIZE = 250 * 1024 * 1024  # 250 MiB per file
MAX_ARCHIVE_ENTRIES = 2000
MAX_COMPRESSION_RATIO = 100  # Uncompressed vs compressed bytes

LOCAL_RELEASE_ENV = "OCARINA_UPDATE_LOCAL_DIR"
INSTALL_ROOT_ENV = "OCARINA_UPDATE_INSTALL_ROOT"
