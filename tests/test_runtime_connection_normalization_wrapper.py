from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_runtime_connection_normalization_wrapper_loads_leaf_modules_lazily() -> None:
    sys.modules.pop("algenta.runtime_connection_normalization", None)
    sys.modules.pop("algenta.runtime_connection_descriptors", None)
    sys.modules.pop("algenta.runtime_connection_sql", None)
    sys.modules.pop("algenta.runtime_source_naming", None)

    module = importlib.import_module("algenta.runtime_connection_normalization")

    assert "algenta.runtime_connection_descriptors" not in sys.modules
    assert "algenta.runtime_connection_sql" not in sys.modules
    assert "algenta.runtime_source_naming" not in sys.modules

    _ = module.runtime_api_source_name

    assert "algenta.runtime_source_naming" in sys.modules
    assert "algenta.runtime_connection_descriptors" not in sys.modules
    assert "algenta.runtime_connection_sql" not in sys.modules

    _ = module.normalize_runtime_connection

    assert "algenta.runtime_connection_descriptors" in sys.modules
    assert "algenta.runtime_connection_sql" not in sys.modules

    module.normalize_runtime_connection(
        {
            "type": "postgres",
            "host": "warehouse.internal",
            "database": "analytics",
            "table": "orders",
        }
    )

    assert "algenta.runtime_connection_sql" in sys.modules
