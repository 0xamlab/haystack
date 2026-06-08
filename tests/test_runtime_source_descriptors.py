from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_source_descriptors = importlib.import_module("algenta.runtime_source_descriptors")
RuntimeValidationError = runtime_errors.RuntimeValidationError
normalize_api_source_payload = runtime_source_descriptors.normalize_api_source_payload
normalize_local_runtime_source = runtime_source_descriptors.normalize_local_runtime_source
normalize_runtime_connection = runtime_source_descriptors.normalize_runtime_connection
runtime_source_name = runtime_source_descriptors.runtime_source_name
source_ref_label = runtime_source_descriptors.source_ref_label


def test_runtime_source_name_strips_uuid_prefix_from_local_paths() -> None:
    source_name = runtime_source_name(
        "/tmp/123e4567-e89b-12d3-a456-426614174000_orders.csv",
        0,
    )

    assert source_name == "orders"


def test_source_ref_label_uses_sqlite_table_when_available() -> None:
    label = source_ref_label(
        {
            "connection_string": "sqlite+pysqlite:///tmp/warehouse.db",
            "table": "orders",
            "type": "sqlite",
        },
        0,
    )

    assert label == "warehouse.db#orders"


def test_normalize_local_runtime_source_rejects_remote_connectors() -> None:
    with pytest.raises(RuntimeValidationError) as excinfo:
        normalize_local_runtime_source(
            {
                "type": "postgres",
                "connection_string": "postgresql://warehouse/orders",
            }
        )

    assert excinfo.value.code == "unsupported_local_connector"


def test_normalize_runtime_connection_builds_sql_payload_from_structured_descriptor() -> None:
    connection = normalize_runtime_connection(
        {
            "type": "postgres",
            "host": "warehouse.internal",
            "port": 5432,
            "database": "analytics",
            "user": "reader",
            "password": "secret",
            "schema": "public",
            "table": "orders",
        }
    )

    assert connection == {
        "type": "sql",
        "provider": "postgres",
        "connection_string": "postgresql://reader:secret@warehouse.internal:5432/analytics",
        "schema": "public",
        "table": "orders",
        "query": "SELECT * FROM public.orders",
    }


def test_normalize_api_source_payload_wraps_connection_descriptors() -> None:
    payload = normalize_api_source_payload(
        {
            "name": "orders_pg",
            "type": "postgres",
            "host": "warehouse.internal",
            "database": "analytics",
            "table": "orders",
        },
        explicit_name=None,
    )

    assert payload["name"] == "orders_pg"
    assert payload["connection"] == {
        "name": "orders_pg",
        "type": "sql",
        "provider": "postgres",
        "connection_string": "postgresql://warehouse.internal:5432/analytics",
        "table": "orders",
        "query": "SELECT * FROM orders",
    }
