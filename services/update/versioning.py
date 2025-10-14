"""Helpers for comparing and classifying release versions."""

from __future__ import annotations

import re


__all__ = [
    "compare_versions",
    "is_version_newer",
    "is_prerelease_version",
    "should_offer_downgrade",
]


def compare_versions(current_version: str, candidate: str) -> int:
    """Compare ``candidate`` against ``current_version``.

    Returns ``1`` when ``candidate`` is newer, ``-1`` when it is older and ``0``
    when the versions are equivalent.  The function mirrors the behaviour of the
    previous :meth:`UpdateService._compare_versions` implementation including the
    same fallback semantics when ``packaging`` is unavailable.
    """

    if candidate == current_version:
        return 0

    try:
        from packaging.version import InvalidVersion, Version  # type: ignore
    except Exception:  # pragma: no cover - packaging not installed
        return _fallback_compare(current_version, candidate)

    try:
        candidate_version = Version(candidate)
        current_version_parsed = Version(current_version)
    except InvalidVersion:
        return _fallback_compare(current_version, candidate)

    if candidate_version == current_version_parsed:
        return 0
    if candidate_version > current_version_parsed:
        return 1
    return -1


def is_version_newer(current_version: str, candidate: str) -> bool:
    """Return ``True`` if ``candidate`` is newer than ``current_version``."""

    return compare_versions(current_version, candidate) > 0


def should_offer_downgrade(current_version: str, candidate: str) -> bool:
    """Return ``True`` when ``candidate`` represents a valid downgrade."""

    if is_prerelease_version(candidate):
        return False
    if not is_prerelease_version(current_version):
        return False
    return compare_versions(current_version, candidate) < 0


def is_prerelease_version(version: str) -> bool:
    """Return ``True`` when ``version`` represents a pre-release build."""

    try:
        from packaging.version import InvalidVersion, Version  # type: ignore
    except Exception:  # pragma: no cover - packaging not installed
        return _fallback_is_prerelease(version)

    try:
        parsed = Version(version)
    except InvalidVersion:
        return _fallback_is_prerelease(version)

    return bool(parsed.is_prerelease or getattr(parsed, "is_devrelease", False))


def _fallback_compare(current_version: str, candidate: str) -> int:
    def tokenize(version: str) -> list[tuple[int, object]]:
        tokens: list[tuple[int, object]] = []
        for raw in version.replace("-", ".").replace("+", ".").split("."):
            if not raw:
                continue
            if raw.isdigit():
                tokens.append((0, int(raw)))
            else:
                tokens.append((1, raw.lower()))
        return tokens

    current_tokens = tokenize(current_version)
    candidate_tokens = tokenize(candidate)
    length = max(len(current_tokens), len(candidate_tokens))
    for index in range(length):
        current_token = current_tokens[index] if index < len(current_tokens) else (0, 0)
        candidate_token = candidate_tokens[index] if index < len(candidate_tokens) else (0, 0)
        if candidate_token != current_token:
            return 1 if candidate_token > current_token else -1
    return 0


def _fallback_is_prerelease(version: str) -> bool:
    markers = ("dev", "alpha", "beta", "rc", "pre", "preview")
    tokens = [token for token in re.split(r"[.\-+_]", version.lower()) if token]
    for token in tokens:
        if any(token.startswith(marker) for marker in markers):
            return True
        if token[0] in {"a", "b"} and len(token) > 1 and token[1:].isdigit():
            return True
    return False
