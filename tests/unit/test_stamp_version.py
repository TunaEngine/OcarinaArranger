"""Tests for the release version stamping helper script."""

from pathlib import Path

import pytest

from scripts import stamp_version


class TestNormalizeRefName:
    def test_strips_single_leading_v(self):
        assert stamp_version.normalize_ref_name("v1.2.3") == "1.2.3"

    def test_returns_input_when_no_v_prefix(self):
        assert stamp_version.normalize_ref_name("1.2.3") == "1.2.3"

    def test_strips_surrounding_whitespace(self):
        assert stamp_version.normalize_ref_name("  v0.9.0  ") == "0.9.0"

    def test_only_strips_single_v_prefix(self):
        assert stamp_version.normalize_ref_name("vv1.0") == "v1.0"


class TestStampVersion:
    def test_writes_normalized_version_to_file(self, tmp_path: Path):
        output = tmp_path / "VERSION"

        stamp_version.stamp_version("v2.5.0", output)

        assert output.read_text(encoding="utf-8") == "2.5.0\n"

    def test_creates_parent_directories(self, tmp_path: Path):
        output = tmp_path / "nested" / "VERSION"

        stamp_version.stamp_version("1.0.1", output)

        assert output.read_text(encoding="utf-8") == "1.0.1\n"


class TestMain:
    def test_main_uses_default_output_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        fake_default = tmp_path / "VERSION"
        monkeypatch.setattr(stamp_version, "DEFAULT_VERSION_FILE", fake_default, raising=False)

        exit_code = stamp_version.main(["v0.1.0"])

        assert exit_code == 0
        assert fake_default.read_text(encoding="utf-8") == "0.1.0\n"
