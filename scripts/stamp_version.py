"""Stamp the application version file based on a Git tag or ref name."""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERSION_FILE = PROJECT_ROOT / "app" / "VERSION"


def normalize_ref_name(ref_name: str) -> str:
    """Normalize a Git ref name to a bare semantic version string."""

    stripped = ref_name.strip()
    if stripped.startswith("v"):
        return stripped[1:]
    return stripped


def stamp_version(ref_name: str, output: Path) -> Path:
    """Write the normalized version derived from *ref_name* to *output*."""

    normalized = normalize_ref_name(ref_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{normalized}\n", encoding="utf-8")
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ref_name",
        help="Git ref name to stamp (e.g. 'v1.2.3').",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_VERSION_FILE,
        help="Path to the VERSION file that should be stamped.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stamp_version(args.ref_name, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
