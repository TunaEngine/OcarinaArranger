from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_TTK_BOOTSTRAP_SPEC = importlib.util.find_spec("ttkbootstrap")
TTK_BOOTSTRAP_AVAILABLE = _TTK_BOOTSTRAP_SPEC is not None

if not TTK_BOOTSTRAP_AVAILABLE:
    collect_ignore_glob = [
        "e2e/*",
        "fingering/*",
        "ui/*",
        "unit/*",
        "viewmodels/*",
        "test_conversion_exports.py",
        "test_note_values.py",
        "test_pdf_export.py",
        "test_preview.py",
        "test_themes.py",
    ]


def _ensure_project_root_on_path() -> None:
    """Guarantee the repository root is discoverable for absolute imports."""

    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    tests_dir = root / "tests"
    tests_str = str(tests_dir)
    if tests_str not in sys.path:
        sys.path.insert(1, tests_str)


_ensure_project_root_on_path()


@pytest.fixture(autouse=True)
def _preferences_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """Isolate GUI preference writes so tests never touch real user data."""

    pref_dir = tmp_path_factory.mktemp("prefs")
    pref_path = pref_dir / "preferences.json"
    monkeypatch.setenv("OCARINA_GUI_PREFERENCES_PATH", str(pref_path))

    yield

    if pref_path.exists():
        try:
            pref_path.unlink()
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _fingering_config_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """Route fingering config persistence to a temporary location during tests."""

    config_dir = tmp_path_factory.mktemp("fingering_config")
    config_path = config_dir / "fingering_config.json"
    monkeypatch.setenv("OCARINA_GUI_FINGERING_CONFIG_PATH", str(config_path))

    yield

    if config_path.exists():
        try:
            config_path.unlink()
        except OSError:
            pass

