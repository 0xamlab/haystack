from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_local_registration = importlib.import_module("algenta.runtime_local_registration")
RuntimeValidationError = runtime_errors.RuntimeValidationError
register_local_source = runtime_local_registration.register_local_source


def _rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42, "region": "US"},
        {"product_line": "Apparel", "revenue": 28, "region": "US"},
        {"product_line": "Electronics", "revenue": 12, "region": "CA"},
    ]


def test_register_local_source_profiles_schema_and_numeric_fields() -> None:
    local_sources: dict[str, object] = {}

    registration = register_local_source(
        local_sources,
        _rows(),
        explicit_name="orders",
        started_at=time.perf_counter(),
    )

    assert registration.name == "orders"
    assert registration.row_count == 3
    assert registration.source_schema == {"fields": ["product_line", "revenue", "region"]}
    assert registration.dataset_id == registration.source_id
    source = local_sources["orders"]
    assert source.fields == ("product_line", "revenue", "region")
    assert source.numeric_fields == frozenset({"revenue"})
    assert source.dataset_id == registration.dataset_id
    assert source.schema_revision == registration.planner_schema_revision


def test_register_local_source_requires_input() -> None:
    with pytest.raises(RuntimeValidationError) as excinfo:
        register_local_source({}, None, explicit_name=None, started_at=time.perf_counter())

    assert excinfo.value.code == "missing_local_source"


def test_register_local_source_rejects_missing_path() -> None:
    missing_path = ROOT / "test_files" / "__missing_source__.csv"

    with pytest.raises(RuntimeValidationError) as excinfo:
        register_local_source(
            {},
            str(missing_path),
            explicit_name=None,
            started_at=time.perf_counter(),
        )

    assert excinfo.value.code == "invalid_local_source"
    assert excinfo.value.details["name"] == "__missing_source__"


def test_register_local_source_rejects_empty_inputs() -> None:
    with pytest.raises(RuntimeValidationError) as excinfo:
        register_local_source(
            {},
            [],
            explicit_name="orders",
            started_at=time.perf_counter(),
        )

    assert excinfo.value.code == "empty_source"
    assert excinfo.value.details["name"] == "orders"


def test_register_local_source_assigns_stable_generated_names() -> None:
    local_sources: dict[str, object] = {}

    first = register_local_source(
        local_sources,
        _rows(),
        explicit_name=None,
        started_at=time.perf_counter(),
    )
    second = register_local_source(
        local_sources,
        _rows(),
        explicit_name=None,
        started_at=time.perf_counter(),
    )

    assert first.name == "source0"
    assert second.name == "source1"
    assert set(local_sources) == {"source0", "source1"}
