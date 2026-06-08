from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

models = importlib.import_module("decision_engine.models")


def test_dataset_detail_result_preserves_schema_alias_property() -> None:
    detail = models.DatasetDetailResult.model_validate(
        {
            "dataset": {"dataset_id": "ds_123", "dataset_name": "orders"},
            "schema": {"fields": ["amount"]},
        }
    )

    assert detail.schema == {"fields": ["amount"]}
    assert detail.schema_payload == {"fields": ["amount"]}


def test_dataset_connect_result_preserves_schema_alias_property() -> None:
    result = models.DatasetConnectResult.model_validate(
        {
            "status": "ready",
            "dataset_id": "ds_123",
            "schema": {"fields": ["amount"]},
        }
    )

    assert result.schema == {"fields": ["amount"]}
    assert result.schema_payload == {"fields": ["amount"]}
