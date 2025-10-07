"""Helpers that keep the optional pytest-bdd dependency truly optional.

The real project provides a ``pytest_bdd`` package that is normally imported
via setuptools entry points when ``pytest`` starts. In environments where the
dependency is unavailable we still want the test suite to run, but if the
package *is* installed locally (for example on a contributor's machine) we must
delegate to the genuine implementation rather than shadowing it with the shim.

This module centralises the logic that attempts to import the real package
while temporarily hiding the shim's location from ``sys.path``. Callers receive
the imported module when it exists or ``None`` when the dependency is missing.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

_SHIM_ROOT = Path(__file__).resolve().parents[1]
_FORCE_ENV_VAR = "PYTEST_BDD_FORCE_SHIM"


def _force_stub_enabled() -> bool:
    """Return ``True`` when callers request the shim, even if installed."""

    raw = os.environ.get(_FORCE_ENV_VAR)
    if raw is None:
        return False
    normalised = raw.strip().lower()
    if normalised in {"", "0", "false", "no"}:
        return False
    return True


def _normalise(path: str) -> Optional[Path]:
    """Return ``Path.resolve()`` for ``path`` while tolerating missing entries."""

    try:
        return Path(path).resolve()
    except (FileNotFoundError, RuntimeError, OSError):
        return None


def _filtered_sys_path(original: list[str]) -> list[str]:
    """Remove the shim's root directory from ``original`` and return a copy."""

    shim_root = _normalise(str(_SHIM_ROOT))
    filtered: list[str] = []
    for entry in original:
        resolved = _normalise(entry)
        if shim_root is not None and resolved == shim_root:
            continue
        filtered.append(entry)
    return filtered


def load_real_module(module_name: str) -> Optional[ModuleType]:
    """Attempt to import the real ``pytest_bdd`` module.

    The shim temporarily removes itself from ``sys.modules`` and ``sys.path``
    so the standard import machinery can discover a locally installed
    ``pytest-bdd`` distribution. If the import succeeds the caller receives the
    genuine module. Otherwise the shim is restored and ``None`` is returned.
    """

    if _force_stub_enabled():
        return None

    shim_module = sys.modules.get(module_name)
    original_sys_path = sys.path[:]
    sys.modules.pop(module_name, None)
    try:
        sys.path = _filtered_sys_path(original_sys_path)
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        module = None
        if shim_module is not None:
            sys.modules[module_name] = shim_module
    else:
        # ``import_module`` already placed the genuine module into
        # ``sys.modules``. Make sure the shim stays discoverable as the
        # ``pytest_bdd._shim`` submodule so call-sites (and our tests) can
        # import it even when the real dependency exists locally.
        shim_module = sys.modules.get(__name__)
        if shim_module is not None:
            sys.modules[f"{module_name}._shim"] = shim_module

            # Allow ``importlib`` to locate the shim by adding the shim's
            # directory to the real package's ``__path__``.  ``module.__path__``
            # may be a non-list (e.g. ``_NamespacePath``), so normalise it to a
            # list before appending the new entry.
            package_path = getattr(module, "__path__", None)
            if package_path is not None:
                extra_path = str(_SHIM_ROOT / module_name.replace(".", "/"))
                if extra_path not in package_path:
                    try:
                        new_path = list(package_path)
                    except TypeError:
                        new_path = list(package_path._path)  # pragma: no cover - defensive
                    new_path.append(extra_path)
                    module.__path__ = new_path
    finally:
        sys.path = original_sys_path

    return module

