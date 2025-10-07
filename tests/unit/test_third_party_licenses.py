from __future__ import annotations

import sys
from pathlib import Path

import pytest
from packaging.markers import Marker
from scripts.build_third_party_licenses import (
    _marker_environment,
    _normalise_license_text,
    _should_include_license_file,
)


EXPECTED_PACKAGES = ("packaging", "pillow", "simpleaudio", "ttkbootstrap")


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="`THIRD-PARTY-LICENSES` generation script is not supported on Windows",
)
def test_third_party_license_file_lists_runtime_packages():
    licenses_path = Path("THIRD-PARTY-LICENSES")
    assert licenses_path.exists(), "Expected aggregated license file to exist"

    contents = licenses_path.read_text(encoding="utf-8")
    for package_name in EXPECTED_PACKAGES:
        assert f") {package_name} " in contents


def test_normalises_and_contributors_wrapping():
    original = "Copyright © 1995-2011 by Fredrik Lundh\n    and contributors"
    expected = "Copyright © 1995-2011 by Fredrik Lundh and contributors"
    assert _normalise_license_text(original) == expected


@pytest.mark.parametrize(
    "separator",
    ("----", "--------", "--------------------------------"),
)
def test_pillow_vendor_sections_are_stripped(separator: str):
    raw = f"License intro\n{separator}\n\nAny Section\nVendor license text\n"
    assert _normalise_license_text(raw, "Pillow") == "License intro"


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
