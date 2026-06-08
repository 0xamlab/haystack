from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_algenta_runtime_wrapper_loads_runtime_facade_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta.runtime"
        or module_name == "algenta.runtime_facade"
        or module_name == "algenta.runtime_execution_surface"
        or module_name.startswith("algenta.runtime_model_")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta.runtime" or module_name == "algenta.runtime_facade":
            sys.modules.pop(module_name, None)
        elif module_name == "algenta.runtime_execution_surface":
            sys.modules.pop(module_name, None)
        elif module_name.startswith("algenta.runtime_model_"):
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("algenta.runtime")

        assert "algenta.runtime_facade" not in sys.modules
        assert "algenta.runtime_model_query_output" not in sys.modules

        query_output_cls = module.QueryOutput

        assert query_output_cls.__name__ == "QueryOutput"
        assert "algenta.runtime" in sys.modules
        assert "algenta.runtime_facade" not in sys.modules
        assert "algenta.runtime_execution_surface" not in sys.modules
        assert "algenta.runtime_model_query_output" in sys.modules

        runtime_cls = module.Runtime

        assert runtime_cls.__name__ == "Runtime"
        assert "algenta.runtime_facade" in sys.modules
        assert "algenta.runtime_execution_surface" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta.runtime" or module_name == "algenta.runtime_facade":
                sys.modules.pop(module_name, None)
            elif module_name == "algenta.runtime_execution_surface":
                sys.modules.pop(module_name, None)
            elif module_name.startswith("algenta.runtime_model_"):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
