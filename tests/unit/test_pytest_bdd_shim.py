from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

import pytest_bdd._shim as shim


def _clear_pytest_bdd_modules() -> None:
    for name in list(sys.modules):
        if name == "pytest_bdd" or name.startswith("pytest_bdd."):
            sys.modules.pop(name)


def test_stub_scaffolding_skips_when_dependency_absent(monkeypatch):
    monkeypatch.setenv("PYTEST_BDD_FORCE_SHIM", "1")
    _clear_pytest_bdd_modules()

    module = importlib.import_module("pytest_bdd")

    with pytest.raises(pytest.skip.Exception):
        module.scenarios()

    def sample() -> str:
        return "ok"

    assert module.given()(sample) is sample
    _clear_pytest_bdd_modules()


def test_delegates_to_real_module_when_available(tmp_path, monkeypatch):
    package_root = tmp_path / "real_lib"
    package_dir = package_root / "pytest_bdd"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(
        "called = []\n"
        "def given(func):\n"
        "    called.append(('given', func.__name__))\n"
        "    return func\n\n"
        "def when(func):\n"
        "    called.append(('when', func.__name__))\n"
        "    return func\n\n"
        "def then(func):\n"
        "    called.append(('then', func.__name__))\n"
        "    return func\n\n"
        "class parsers:\n"
        "    @staticmethod\n"
        "    def parse(pattern):\n"
        "        return f'parse:' + pattern\n\n"
        "def scenarios(*args, **kwargs):\n"
        "    called.append(('scenarios', args, tuple(sorted(kwargs.items()))))\n"
        "    return 'real-scenarios'\n"
    )
    (package_dir / "plugin.py").write_text(
        "def pytest_configure(config):\n"
        "    config.from_real_plugin = True\n"
    )

    monkeypatch.delenv("PYTEST_BDD_FORCE_SHIM", raising=False)
    monkeypatch.syspath_prepend(str(package_root))
    _clear_pytest_bdd_modules()

    module = importlib.import_module("pytest_bdd")

    def decorated() -> str:
        return "decorated"

    module.given(decorated)
    result = module.scenarios("feature")
    assert result == "real-scenarios"
    assert module.parsers.parse("value") == "parse:value"
    assert ("given", "decorated") in module.called

    plugin = importlib.import_module("pytest_bdd.plugin")
    config = SimpleNamespace()
    plugin.pytest_configure(config)
    assert getattr(config, "from_real_plugin", False) is True

    _clear_pytest_bdd_modules()

