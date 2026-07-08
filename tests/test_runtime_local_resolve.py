from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_local_execution = importlib.import_module("algenta.runtime_local_execution")
runtime_local_resolve = importlib.import_module("algenta.runtime_local_resolve")
RuntimeValidationError = runtime_errors.RuntimeValidationError
LocalSource = runtime_local_execution.LocalSource
RankedFieldMatch = runtime_local_execution.RankedFieldMatch
infer_numeric_fields = runtime_local_execution.infer_numeric_fields
resolve_local_request = runtime_local_resolve.resolve_local_request


def _source() -> LocalSource:
    records = [
        {"product_line": "Electronics", "revenue": 10, "region": "US"},
        {"product_line": "Apparel", "revenue": 20, "region": "CA"},
        {"product_line": "Electronics", "revenue": 30, "region": "US"},
    ]
    fields = ("product_line", "revenue", "region")
    return LocalSource(
        name="orders",
        records=records,
        fields=fields,
        schema_revision="schema_v1",
        dataset_id="ds_123",
        numeric_fields=infer_numeric_fields(records, fields),
    )


def _resolve_aggregation(request: dict[str, object]) -> str:
    return str(request.get("aggregation", "sum"))


def _intent_signature(source_name: str, request: dict[str, object], schema_revision: str) -> str:
    return f"{source_name}:{schema_revision}:{request.get('metric', '')}"


def _plan_hash(plan) -> str:
    return f"plan:{plan.metric_column}:{plan.group_column or ''}"


def test_resolve_local_request_requires_metric() -> None:
    with pytest.raises(RuntimeValidationError) as excinfo:
        resolve_local_request(
            {"orders": _source()},
            {"group_by": "product_line"},
            started_at=time.perf_counter(),
            resolve_aggregation=_resolve_aggregation,
            intent_signature=_intent_signature,
            plan_hash=_plan_hash,
        )

    assert excinfo.value.code == "metric_required"


def test_resolve_local_request_returns_exact_plan_for_decisive_match() -> None:
    result = resolve_local_request(
        {"orders": _source()},
        {"metric": "revenue", "group_by": "product_line"},
        started_at=time.perf_counter(),
        resolve_aggregation=_resolve_aggregation,
        intent_signature=_intent_signature,
        plan_hash=_plan_hash,
    )

    assert result.validated is True
    assert result.clarification_required is False
    assert result.resolved_plan is not None
    assert result.resolved_plan.metric_column == "revenue"
    assert result.resolved_plan.group_column == "product_line"
    assert result.decision_path == "exact_spec"


def test_resolve_local_request_returns_clarification_for_ambiguous_metric(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_local_resolve,
        "rank_local_fields",
        lambda source, hint, *, numeric_only: [
            RankedFieldMatch("revenue", 0.84, ("schema similarity",), True),
            RankedFieldMatch("net_revenue", 0.80, ("schema similarity",), True),
        ],
    )
    monkeypatch.setattr(
        runtime_local_resolve,
        "build_local_candidates",
        lambda source, ranked, role: [{"source": source.name, "role": role}],
    )

    result = resolve_local_request(
        {"orders": _source()},
        {"metric": "sales"},
        started_at=time.perf_counter(),
        resolve_aggregation=_resolve_aggregation,
        intent_signature=_intent_signature,
        plan_hash=_plan_hash,
    )

    assert result.resolved_plan is None
    assert result.clarification_required is True
    assert result.rejection_reason is None
    assert result.candidates == [{"source": "orders", "role": "measure"}]


def test_resolve_local_request_rejects_unmatched_group(monkeypatch) -> None:
    def _rank(source, hint, *, numeric_only):
        if numeric_only:
            return [RankedFieldMatch("revenue", 1.0, ("exact field match",), True)]
        return []

    monkeypatch.setattr(runtime_local_resolve, "rank_local_fields", _rank)
    monkeypatch.setattr(
        runtime_local_resolve,
        "build_local_candidates",
        lambda source, ranked, role: [{"source": source.name, "role": role}],
    )

    result = resolve_local_request(
        {"orders": _source()},
        {"metric": "revenue", "group_by": "country"},
        started_at=time.perf_counter(),
        resolve_aggregation=_resolve_aggregation,
        intent_signature=_intent_signature,
        plan_hash=_plan_hash,
    )

    assert result.resolved_plan is None
    assert result.clarification_required is False
    assert result.rejection_reason == "schema_unresolved"
    assert result.explanation == ["No field matched group_by 'country'."]
