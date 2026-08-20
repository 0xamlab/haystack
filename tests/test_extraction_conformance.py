"""Cross-language extraction conformance: Python side.

Locks the shared aligned-column-extraction and typed-field-inference contract
against tests/conformance/extraction_vectors.json. The TS SDK asserts the SAME
literals (packages/ts-sdk/src/extraction_conformance.test.ts), so a pass in
both languages proves byte-identical behavior — pairwise/preserve alignment,
filter-before-alignment, limit truncation, input_hash, error codes/details,
and typed-field inference.

Sources are seeded with a pinned schema_revision/dataset_id from the vectors
because connect()-time schema revision derivation is not yet cross-language
identical; input_hash parity is asserted over the pinned revision.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from algenta import Runtime
from algenta.runtime_errors import RuntimeValidationError

_VECTORS_PATH = Path(__file__).parent.parent / "packages" / "ts-sdk" / "conformance" / "extraction_vectors.json"
_VECTORS = json.loads(_VECTORS_PATH.read_text())


def _seeded_runtime(source_key: str) -> tuple[Runtime, dict[str, Any]]:
    spec = _VECTORS["sources"][source_key]
    runtime = Runtime(mode="local")
    runtime.connect([dict(record) for record in spec["records"]], name=spec["name"])
    source = runtime._local_sources[spec["name"]]
    runtime._local_sources[spec["name"]] = dataclasses.replace(
        source,
        schema_revision=spec["schema_revision"],
        dataset_id=spec["dataset_id"],
    )
    return runtime, spec


def _extract_kwargs(case: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if "filter" in case:
        kwargs["filter"] = case["filter"]
    if "limit" in case:
        kwargs["limit"] = case["limit"]
    if "null_policy" in case:
        kwargs["null_policy"] = case["null_policy"]
    return kwargs


@pytest.mark.parametrize("case", _VECTORS["extract"], ids=lambda c: c["name"])
def test_extract_columns_conformance(case: dict[str, Any]) -> None:
    runtime, spec = _seeded_runtime(case["source"])
    got = runtime.extract_columns(spec["name"], case["columns"], **_extract_kwargs(case))
    assert got.columns == case["expected"]["columns"]
    assert got.row_count == case["expected"]["row_count"]
    assert got.input_hash == case["expected"]["input_hash"]
    assert got.source_name == spec["name"]
    assert got.schema_revision == spec["schema_revision"]
    assert got.alignment == "rowwise"


@pytest.mark.parametrize("case", _VECTORS["extract_errors"], ids=lambda c: c["name"])
def test_extract_columns_error_conformance(case: dict[str, Any]) -> None:
    runtime, _spec = _seeded_runtime(case["source"])
    with pytest.raises(RuntimeValidationError) as excinfo:
        runtime.extract_columns(case["source_name"], case["columns"], **_extract_kwargs(case))
    assert excinfo.value.code == case["error_code"]
    assert excinfo.value.details == case["details"]


@pytest.mark.parametrize("case", _VECTORS["typed_fields"], ids=lambda c: c["name"])
def test_typed_fields_conformance(case: dict[str, Any]) -> None:
    runtime = Runtime(mode="local")
    registration = runtime.connect([dict(record) for record in case["records"]], name="typed_probe")
    assert registration.typed_fields == case["expected"]
    assert registration.source_schema is not None
    assert registration.source_schema["typed_fields"] == case["expected"]
    # The existing fields array must stay untouched alongside typed_fields.
    assert registration.source_schema["fields"] == [entry["name"] for entry in case["expected"]]


def test_extract_columns_requires_local_mode() -> None:
    runtime = Runtime(mode="api", api_key="de_test_extract")
    with pytest.raises(RuntimeValidationError) as excinfo:
        runtime.extract_columns("anything", ["revenue"])
    assert excinfo.value.code == "extract_requires_local_mode"


def test_extract_columns_unknown_source_without_connections() -> None:
    runtime = Runtime(mode="local")
    with pytest.raises(RuntimeValidationError) as excinfo:
        runtime.extract_columns("anything", ["revenue"])
    assert excinfo.value.code == "unknown_source"
    assert excinfo.value.details == {"requested": "anything", "available": []}
