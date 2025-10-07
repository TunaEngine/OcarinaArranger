from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SHIM_MODULE = "pytest_bdd._shim"

if _SHIM_MODULE not in sys.modules:
    shim_path = Path(__file__).resolve().parent / "pytest_bdd" / "_shim.py"
    if shim_path.exists():
        spec = importlib.util.spec_from_file_location(_SHIM_MODULE, shim_path)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[_SHIM_MODULE] = module
            spec.loader.exec_module(module)
