from __future__ import annotations

from importlib import metadata
from pathlib import Path

from packaging.markers import Marker
from scripts.build_third_party_licenses import (
    _marker_environment,
    _normalise_license_text,
    _should_include_license_file,
    build_license_file,
)
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


EXPECTED_PACKAGES = ("packaging", "pillow", "simpleaudio", "ttkbootstrap")


def _load_runtime_requirements(path: Path) -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "test" in line.lower() and "dependenc" in line.lower():
                break
            continue
        req = Requirement(line)
        requirements[canonicalize_name(req.name)] = req
    return requirements


def test_third_party_license_file_lists_runtime_packages(tmp_path):
    requirements = _load_runtime_requirements(Path("requirements.txt"))
    licenses_path = Path("THIRD-PARTY-LICENSES")
    assert licenses_path.exists(), "Expected aggregated license file to exist"

    contents = licenses_path.read_text(encoding="utf-8")
    for package_name in EXPECTED_PACKAGES:
        assert f"Package: {package_name}" in contents
    assert "Package: pytest" not in contents

    for package_name in EXPECTED_PACKAGES:
        canonical = canonicalize_name(package_name)
        requirement = requirements[canonical]
        try:
            dist = metadata.distribution(canonical)
        except metadata.PackageNotFoundError as exc:  # pragma: no cover - defensive
            raise AssertionError(
                "Runtime dependency"
                f" {package_name!r} is missing. Run `pip install -r requirements.txt` "
                "to sync your environment before regenerating THIRD-PARTY-LICENSES."
            ) from exc
        if requirement.specifier:
            assert requirement.specifier.contains(
                dist.version, prereleases=True
            ), (
                f"Installed {package_name}=={dist.version} does not satisfy the pinned"
                f" requirement `{requirement}`. Run `pip install -r requirements.txt`"
                " to align the environment before rebuilding THIRD-PARTY-LICENSES."
            )

    output_path = tmp_path / "licenses.txt"
    build_license_file(Path("requirements.txt"), output_path)
    regenerated = output_path.read_text(encoding="utf-8")
    assert regenerated == contents


def test_normalises_and_contributors_wrapping():
    original = "Copyright © 1995-2011 by Fredrik Lundh\n    and contributors"
    expected = "Copyright © 1995-2011 by Fredrik Lundh and contributors"
    assert _normalise_license_text(original) == expected


def test_marker_environment_skips_windows_only_dependencies():
    windows_only = Marker("sys_platform == 'win32'")
    linux_only = Marker("sys_platform == 'linux'")

    env = _marker_environment(extra=None)

    assert not windows_only.evaluate(env)
    assert linux_only.evaluate(env)


def test_vendor_licenses_under_private_libs_directory_are_ignored():
    assert _should_include_license_file("Pillow-10.4.0.dist-info/LICENSE")
    assert _should_include_license_file("LICENSE")
    assert not _should_include_license_file("Pillow.libs/brotli-1.1.0.dist-info/LICENSE")
    assert not _should_include_license_file(
        "pillow.libs.data/purelib/brotli-1.1.0.dist-info/LICENSE"
    )
