"""Pytest configuration applied to the entire test suite."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _ensure_pytest_bdd_shim() -> None:
    """Make the in-repo ``pytest_bdd._shim`` module importable for tests."""

    module_name = "pytest_bdd._shim"
    if module_name in sys.modules:
        return

    shim_path = Path(__file__).resolve().parent / "pytest_bdd" / "_shim.py"
    if not shim_path.exists():
        return

    spec = importlib.util.spec_from_file_location(module_name, shim_path)
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    parent_name = module_name.rsplit(".", 1)[0]
    parent = sys.modules.get(parent_name)
    if parent is not None:
        package_path = getattr(parent, "__path__", None)
        if package_path is not None:
            shim_dir = str(shim_path.parent)
            if shim_dir not in package_path:
                try:
                    new_path = list(package_path)
                except TypeError:
                    new_path = list(package_path._path)  # pragma: no cover - defensive
                new_path.append(shim_dir)
                parent.__path__ = new_path


_ensure_pytest_bdd_shim()


# Ensure all BDD step definition modules load before feature parsing so
# pytest-bdd can match scenario text to the registered steps, regardless of
# which subset of tests is collected.
pytest_plugins = [
    "tests.e2e.steps.common",
    "tests.e2e.steps.conversion",
    "tests.e2e.steps.preview",
    "tests.e2e.steps.preview_controls",
    "tests.e2e.steps.projects",
    "tests.e2e.steps.transform",
    "tests.e2e.steps.updates_support",
    "tests.e2e.steps.window",
    "tests.e2e.steps.view_preferences",
]
