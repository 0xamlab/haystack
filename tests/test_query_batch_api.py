from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers.query_contract import QueryResponse

pytestmark = pytest.mark.anyio


@pytest.fixture
async def query_client(app, client):
    app.dependency_overrides[get_current_org] = lambda: {
        "org_id": "org_a",
        "role": "member",
        "user_id": "u1",
        "key_id": "k1",
    }
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _query_response(**overrides: Any) -> QueryResponse:
    return QueryResponse.model_validate(
        {
            "query_id": "query_1",
            "result": {"rows": []},
            "result_type": "table",
            "confidence": 0.98,
            "plan": ["resolve metric", "execute query"],
            "resolved_column": "otp_rate_pct",
            "resolved_role": "metric",
            "resolved_source": "otp_events",
            "row_count": 1,
            "candidates": [],
            "source_scores": {"otp_events": 0.98},
            "ambiguous": False,
            "exact_spec": True,
            "explanation": ["used exact spec"],
            "latency_ms": 12.5,
            "decision_path": "exact_spec",
            "plan_hash": "plan_1",
            "validated": True,
            "deterministic_scope": "exact",
            "confidence_source": "schema_truth",
            "request_id": "req_item",
            **overrides,
        }
    )


async def test_query_batch_preserves_order_applies_defaults_and_partial_failures(
    monkeypatch,
    query_client,
) -> None:
    async def _fake_query_sources(payload, request=None, auth=None):  # type: ignore[no-untyped-def]
        assert payload.dataset_id == "otp_events"
        assert payload.filter.time_filter == "last_year"
        assert payload.filter.conditions[0].dimension_hint == "status"
        assert payload.filter.conditions[0].op == "eq"
        assert payload.filter.conditions[0].value == "closed"
        assert payload.limit == 12
        assert payload.order == "desc"
        metric_hint = payload.metric.hint
        if metric_hint == "average_delay_minutes":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "metric_not_found",
                        "message": "Metric average_delay_minutes was not found.",
                    }
                },
            )
        return _query_response(request_id="req_overall", latency_ms=18.0)

    monkeypatch.setattr("apps.api_server.routers.query.query_sources", _fake_query_sources)

    response = await query_client.post(
        "/v1/query/batch",
        json={
            "defaults": {
                "dataset_id": "otp_events",
                "filter": {
                    "time_filter": "last_year",
                    "conditions": [
                        {"dimension_hint": "status", "op": "eq", "value": "closed"},
                    ],
                },
                "limit": 12,
                "order": "desc",
            },
            "queries": [
                {
                    "key": "overall_otp",
                    "request": {"metric": {"role": "metric", "hint": "otp_rate"}},
                },
                {
                    "key": "avg_delay",
                    "request": {"metric": {"role": "metric", "hint": "average_delay_minutes"}},
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    assert [item["key"] for item in body["results"]] == ["overall_otp", "avg_delay"]
    assert body["results"][0]["metadata"]["request_id"] == "req_overall"
    assert body["results"][0]["metadata"]["latency_ms"] == 18.0
    assert body["results"][0]["metadata"]["tokens_in"] is None
    assert body["results"][1]["error"]["code"] == "metric_not_found"
    assert body["results"][1]["data"] is None


async def test_query_batch_rejects_duplicate_keys(query_client) -> None:
    response = await query_client.post(
        "/v1/query/batch",
        json={
            "queries": [
                {"key": "dup", "request": {"metric": {"role": "metric"}}},
                {"key": "dup", "request": {"metric": {"role": "metric"}}},
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_query_batch"
