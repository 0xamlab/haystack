from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_algenta_mojo_wrapper_loads_runtime_module_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta.mojo"
        or module_name == "algenta.mojo_runtime"
        or module_name == "algenta.mojo_entrypoints"
        or module_name == "algenta.mojo_errors"
    }
    for module_name in list(sys.modules):
        if module_name == "algenta.mojo":
            sys.modules.pop(module_name, None)
        elif module_name == "algenta.mojo_runtime":
            sys.modules.pop(module_name, None)
        elif module_name == "algenta.mojo_entrypoints":
            sys.modules.pop(module_name, None)
        elif module_name == "algenta.mojo_errors":
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("algenta.mojo")

        assert "algenta.mojo_runtime" not in sys.modules

        libraries_fn = module.libraries

        assert callable(libraries_fn)
        assert "algenta.mojo_runtime" not in sys.modules
        assert "algenta.mojo_entrypoints" in sys.modules

        runtime_cls = module.MojoRuntime

        assert runtime_cls.__name__ == "MojoRuntime"
        assert "algenta.mojo_runtime" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta.mojo":
                sys.modules.pop(module_name, None)
            elif module_name == "algenta.mojo_runtime":
                sys.modules.pop(module_name, None)
            elif module_name == "algenta.mojo_entrypoints":
                sys.modules.pop(module_name, None)
            elif module_name == "algenta.mojo_errors":
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
