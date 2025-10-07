"""Generate the THIRD-PARTY-LICENSES file from installed distributions."""

from __future__ import annotations

import argparse
import pathlib
import re
from collections.abc import Iterable
from importlib import metadata

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_AND_CONTRIBUTORS_LINE = re.compile(
    r"\n[ \t]*and contributors(?=\s*(?:\n|$))", re.IGNORECASE
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "THIRD-PARTY-LICENSES"

_CANONICAL_MARKER_ENV = {
    "implementation_name": "cpython",
    "implementation_version": "3.11.0",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "platform_release": "",
    "platform_system": "Linux",
    "platform_version": "",
    "python_full_version": "3.11.0",
    "python_version": "3.11",
    "sys_platform": "linux",
}


def _marker_environment(extra: str | None) -> dict[str, str | None]:
    """Return the canonical environment used for marker evaluation."""

    env: dict[str, str | None] = dict(_CANONICAL_MARKER_ENV)
    env["extra"] = extra
    return env


def _read_runtime_requirements(path: pathlib.Path) -> list[str]:
    packages: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "test" in line.lower() and "dependenc" in line.lower():
                break
            continue
        req = Requirement(line)
        packages.append(req.name)
    return packages


def _resolve_distribution_names(package_names: Iterable[str]) -> list[str]:
    """Return canonical distribution names for the given runtime packages.

    The aggregated license file should only list the direct runtime dependencies
    declared in ``requirements.txt``.  Including transitive dependencies causes
    environment-specific drift (because transitive requirements can differ across
    platforms or installation methods) and breaks the determinism that the unit
    tests enforce.  Earlier revisions walked the dependency tree recursively,
    which meant the generated output could change whenever a dependency pulled
    in an extra package (for example ``brotli`` via Pillow).  By restricting the
    resolver to the explicit runtime requirements we keep the output stable and
    reproducible, while still normalising canonical distribution names and
    deduplicating entries.
    """

    resolved: list[str] = []
    seen: set[str] = set()
    for name in package_names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        canonical = dist.metadata.get("Name", dist.metadata["Name"])  # type: ignore[index]
        normalised = canonicalize_name(canonical.strip())
        if normalised in seen:
            continue
        seen.add(normalised)
        resolved.append(normalised)
    return sorted(resolved, key=str.casefold)


def _normalise_license_text(text: str) -> str:
    """Eliminate environment-specific wrapping in known license footers."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    def _merge_and_contributors(match: re.Match[str]) -> str:
        return " " + match.group(0).strip()

    return _AND_CONTRIBUTORS_LINE.sub(_merge_and_contributors, text)


def _should_include_license_file(relative_path: str) -> bool:
    """Return ``True`` for license files that belong to the distribution."""

    normalised = relative_path.replace("\\", "/")
    # Wheels for some packages (notably Pillow on Windows) vendor optional
    # native libraries inside a ``.libs`` directory, each with their own
    # ``*.dist-info`` metadata.  These artefacts cause environment-specific
    # drift when aggregated because Linux wheels do not include them.  Treat
    # any license files under ``*.libs`` as implementation details of the
    # main distribution and exclude them from the consolidated output so that
    # the generated file stays deterministic across platforms.
    segments = [segment for segment in normalised.split("/") if segment]
    if any(".libs" in part.lower() for part in segments):
        return False
    return True


def _collect_license_entries(dist_name: str) -> list[tuple[str, str]]:
    dist = metadata.distribution(dist_name)
    entries: list[tuple[str, str]] = []
    files = dist.files or []
    for entry in sorted(files, key=lambda item: str(item).lower()):
        if "license" not in entry.name.lower():
            continue
        if not _should_include_license_file(str(entry)):
            continue
        path = dist.locate_file(entry)
        if not path.is_file():
            continue
        raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
        text = _normalise_license_text(raw_text)
        if not text:
            continue
        entries.append((str(entry), text))
    metadata_license = dist.metadata.get("License")
    if not entries and metadata_license:
        entries.append(("METADATA:License", metadata_license.strip()))
    return entries


def _normalise_homepage(raw: str | None, dist: metadata.Distribution) -> str:
    """Return a stable homepage URL for the given distribution."""

    if raw:
        candidate = raw.strip()
        if candidate and candidate.lower() != "unknown":
            return candidate

    project_urls = dist.metadata.get_all("Project-URL") or []
    for entry in project_urls:
        if "," not in entry:
            continue
        label, url = entry.split(",", 1)
        if label.strip().lower() == "homepage":
            candidate = url.strip()
            if candidate:
                return candidate

    return "Unknown"


def _normalise_license_path(
    relative_path: str, dist: metadata.Distribution
) -> str:
    """Normalise metadata license file paths to avoid environment drift."""

    normalised = relative_path.replace(f"-{dist.version}", "").replace(
        f"_{dist.version}", ""
    )
    parts = normalised.replace("\\", "/").split("/")
    collapsed = [part for part in parts if part.lower() != "licenses"]
    if collapsed:
        first = collapsed[0]
        lower_first = first.lower()
        for suffix in (".dist-info", ".data"):
            if lower_first.endswith(suffix):
                collapsed[0] = canonicalize_name(dist.metadata["Name"]) + suffix
                break
    return "/".join(collapsed)


def build_license_file(requirements: pathlib.Path, output: pathlib.Path) -> None:
    runtime_packages = _read_runtime_requirements(requirements)
    distributions = _resolve_distribution_names(runtime_packages)
    sections: list[str] = ["=" * 80]
    for name in distributions:
        dist = metadata.distribution(name)
        entries = _collect_license_entries(name)
        if not entries:
            continue
        homepage = _normalise_homepage(dist.metadata.get("Home-page"), dist)
        header = [
            f"Package: {canonicalize_name(dist.metadata['Name'])}",
            f"Homepage: {homepage}".rstrip(),
        ]
        license_str = dist.metadata.get("License")
        if license_str:
            header.append(f"Declared License: {license_str.strip()}")
        sections.extend(header)
        for relative_path, text in entries:
            normalised_path = _normalise_license_path(relative_path, dist)
            sections.append("-" * 80)
            sections.append(f"Source: {normalised_path}")
            sections.append("")
            sections.append(text)
            sections.append("")
        sections.append("=" * 80)
    if sections[-1] != "=" * 80:
        sections.append("=" * 80)
    output.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        type=pathlib.Path,
        default=DEFAULT_REQUIREMENTS,
        help="Path to requirements.txt containing runtime dependencies.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="File path for the aggregated license output.",
    )
    args = parser.parse_args()
    build_license_file(args.requirements, args.output)


if __name__ == "__main__":
    main()

