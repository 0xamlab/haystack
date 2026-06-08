from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))


def test_client_decision_surface_wrapper_loads_leaf_modules_lazily() -> None:
    modules = (
        "decision_engine.client_decision_surface",
        "decision_engine.client_query_surface",
        "decision_engine.client_simulation_surface",
        "decision_engine.client_source_surface",
    )
    preserved = {name: sys.modules[name] for name in modules if name in sys.modules}
    for module_name in modules:
        sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.client_decision_surface")

        assert "decision_engine.client_query_surface" not in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules

        assert wrapper.resolve.__name__ == "resolve"
        assert "decision_engine.client_query_surface" in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules

        assert wrapper.simulate.__name__ == "simulate"
        assert "decision_engine.client_simulation_surface" in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules

        assert wrapper.register_source.__name__ == "register_source"
        assert "decision_engine.client_source_surface" in sys.modules
    finally:
        for module_name in modules:
            sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_async_client_decision_surface_wrapper_loads_leaf_modules_lazily() -> None:
    modules = (
        "decision_engine.async_client_decision_surface",
        "decision_engine.async_client_query_surface",
        "decision_engine.async_client_simulation_surface",
        "decision_engine.async_client_source_surface",
    )
    preserved = {name: sys.modules[name] for name in modules if name in sys.modules}
    for module_name in modules:
        sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.async_client_decision_surface")

        assert "decision_engine.async_client_query_surface" not in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules

        assert wrapper.resolve.__name__ == "resolve"
        assert "decision_engine.async_client_query_surface" in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules

        assert wrapper.simulate.__name__ == "simulate"
        assert "decision_engine.async_client_simulation_surface" in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules

        assert wrapper.register_source.__name__ == "register_source"
        assert "decision_engine.async_client_source_surface" in sys.modules
    finally:
        for module_name in modules:
            sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
