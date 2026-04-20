from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.api_server.routers import datasets as datasets_router
from apps.api_server.routers import sources as sources_router
from apps.api_server.routers import triggers as triggers_router


@pytest.mark.asyncio
async def test_list_datasets_adds_canonical_pagination_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.datasets.ds.list_datasets",
        lambda _org_id: [
            {"dataset_id": "a", "name": "A", "schema_hash": "h1", "status": "ready", "model_tier": "schema"},
            {"dataset_id": "b", "name": "B", "schema_hash": "h2", "status": "ready", "model_tier": "base"},
            {"dataset_id": "c", "name": "C", "schema_hash": "h3", "status": "training", "model_tier": "none"},
        ],
    )

    payload = await datasets_router.list_datasets(
        auth={"org_id": "org_a"},
        page=2,
        limit=2,
    )

    assert payload["count"] == 1
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["limit"] == 2
    assert payload["pages"] == 2
    assert [item["dataset_id"] for item in payload["datasets"]] == ["c"]
    assert payload["datasets"][0]["decision_mode"] == "deterministic_only"


@pytest.mark.asyncio
async def test_list_sources_adds_canonical_pagination_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api_server.routers.sources.reg.list_sources",
        lambda _org_id: [
            {"id": "s1", "name": "Source 1", "row_count": 1, "visibility": "shared"},
            {"id": "s2", "name": "Source 2", "row_count": 2, "visibility": "shared"},
            {"id": "s3", "name": "Source 3", "row_count": 3, "visibility": "shared"},
        ],
    )

    response = await sources_router.list_sources(
        auth={"org_id": "org_a"},
        page=1,
        limit=2,
    )

    assert response["count"] == 2
    assert response["total"] == 3
    assert response["page"] == 1
    assert response["limit"] == 2
    assert response["pages"] == 2


@pytest.mark.asyncio
async def test_list_triggers_adds_canonical_pagination_fields() -> None:
    triggers_router._TRIGGER_STORE.clear()
    now = datetime.now(UTC).isoformat()
    triggers_router._TRIGGER_STORE.update(
        {
            "org_a:t1": {
                "trigger_id": "t1",
                "org_id": "org_a",
                "name": "Trigger 1",
                "status": "active",
                "condition": {
                    "source_id": "src_1",
                    "metric_hint": "revenue",
                    "threshold": 10.0,
                    "direction": "above",
                    "aggregation": "sum",
                },
                "description": None,
                "webhook_url": None,
                "execution_webhook_url": None,
                "auto_execute": False,
                "created_at": now,
                "last_checked_at": None,
                "last_fired_at": None,
                "last_result_summary": None,
            },
            "org_a:t2": {
                "trigger_id": "t2",
                "org_id": "org_a",
                "name": "Trigger 2",
                "status": "active",
                "condition": {
                    "source_id": "src_2",
                    "metric_hint": "cost",
                    "threshold": 5.0,
                    "direction": "below",
                    "aggregation": "sum",
                },
                "description": None,
                "webhook_url": None,
                "execution_webhook_url": None,
                "auto_execute": False,
                "created_at": now,
                "last_checked_at": None,
                "last_fired_at": None,
                "last_result_summary": None,
            },
        }
    )

    response = await triggers_router.list_triggers(
        auth={"org_id": "org_a"},
        status="all",
        page=1,
        limit=1,
    )

    assert response.count == 1
    assert response.total == 2
    assert response.page == 1
    assert response.limit == 1
    assert response.pages == 2
