from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_intent = importlib.import_module("algenta.runtime_intent")
runtime_models = importlib.import_module("algenta.runtime_models")
ResolvedPlan = runtime_models.ResolvedPlan
intent_signature = runtime_intent.intent_signature
merge_runtime_request = runtime_intent.merge_runtime_request
parse_raw_text = runtime_intent.parse_raw_text
plan_hash = runtime_intent.plan_hash
resolve_aggregation = runtime_intent.resolve_aggregation


def test_parse_raw_text_extracts_metric_aggregation_and_grouping() -> None:
    parsed = parse_raw_text("average revenue by region")

    assert parsed == {
        "aggregation": "mean",
        "metric": "revenue",
        "group_by": "region",
    }


def test_resolve_aggregation_prefers_explicit_value() -> None:
    resolved = resolve_aggregation(
        {
            "aggregation": "COUNT",
            "raw_text": "average revenue by region",
        }
    )

    assert resolved == "count"


def test_merge_runtime_request_fills_from_raw_text_without_overwriting_explicit_values() -> None:
    merged = merge_runtime_request(
        {"raw_text": "average revenue by region", "metric": "gross_margin"},
        {"group_by": "country"},
    )

    assert merged["metric"] == "gross_margin"
    assert merged["group_by"] == "country"
    assert merged["aggregation"] == "mean"


def test_intent_signature_normalizes_equivalent_requests() -> None:
    first = intent_signature(
        "orders",
        {
            "metric": "Revenue",
            "group_by": "Product Line",
            "order": "DESC",
            "constraints": {},
            "filter": {},
        },
        "schema_v1",
    )
    second = intent_signature(
        "orders",
        {
            "metric": "revenue",
            "group_by": "product_line",
            "order": "desc",
            "constraints": {},
            "filter": {},
        },
        "schema_v1",
    )

    assert first == second


def test_plan_hash_uses_serialized_plan_shape() -> None:
    first = ResolvedPlan(
        source_name="orders",
        metric_column="revenue",
        aggregation="sum",
        group_column="product_line",
        schema_revision="schema_v1",
    )
    second = ResolvedPlan(
        source_name="orders",
        metric_column="revenue",
        aggregation="sum",
        group_column="product_line",
        schema_revision="schema_v1",
    )

    assert plan_hash(first) == plan_hash(second)
