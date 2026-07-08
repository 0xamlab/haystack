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


def test_algenta_map_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta" or module_name.startswith("algenta.")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta" or module_name.startswith("algenta."):
            sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("algenta.map")

        assert "algenta.map_models" not in sys.modules
        assert "algenta.map_parsing" not in sys.modules
        assert "algenta.map_matching" not in sys.modules
        assert "algenta.map_query" not in sys.modules

        map_data_fn = wrapper.map_data

        assert callable(map_data_fn)
        assert "algenta.map_matching" in sys.modules
        assert "algenta.map_models" not in sys.modules
        assert "algenta.map_parsing" not in sys.modules
        assert "algenta.map_query" not in sys.modules

        result = map_data_fn(
            [{"customer_id": "c1", "qty": 2}],
            [{"customer_id": "c1", "quantity": 2}],
            names=["sales", "orders"],
        )

        assert result.sources_analyzed == 2
        assert "algenta.map_models" in sys.modules
        assert "algenta.map_parsing" in sys.modules

        query_data_fn = wrapper.query_data

        assert callable(query_data_fn)
        assert "algenta.map_query" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta" or module_name.startswith("algenta."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
