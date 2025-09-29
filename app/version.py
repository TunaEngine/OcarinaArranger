from __future__ import annotations

"""Application version helpers."""

from functools import lru_cache
import os
import subprocess
from importlib import resources

_FALLBACK_VERSION = "0.0.0-dev"


def _read_version_file() -> str | None:
    try:
        text = resources.files(__package__).joinpath("VERSION").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    version = text.strip()
    return version or None


def _version_from_env() -> str | None:
    env_version = os.environ.get("OCARINA_APP_VERSION") or os.environ.get("GITHUB_REF_NAME")
    if not env_version:
        return None
    return _normalize(env_version)


def _version_from_git() -> str | None:
    try:
        output = subprocess.check_output(
            ["git", "describe", "--tags", "--dirty"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return _normalize(output.strip())


def _normalize(raw_version: str) -> str:
    version = raw_version.strip()
    if version.startswith("v"):
        version = version[1:]
    return version


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Return the application version.

    The order of precedence is:
    1. Explicit environment variables (``OCARINA_APP_VERSION`` or ``GITHUB_REF_NAME``).
    2. Embedded ``VERSION`` file packaged with the app.
    3. ``git describe`` output when running from a source checkout.
    4. A fallback development version string.
    """

    for resolver in (_version_from_env, _read_version_file, _version_from_git):
        version = resolver()
        if version:
            return version
    return _FALLBACK_VERSION


__all__ = ["get_app_version"]
