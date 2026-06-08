from __future__ import annotations

import pytest

from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import query as query_router

pytestmark = pytest.mark.anyio


class _RedisStub:
    async def incr(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def expire(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return b"0"

    async def set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def setex(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def incrby(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def ping(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return True

    async def hgetall(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return {}

    async def hset(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def aclose(self) -> None:
        return None


@pytest.fixture
async def verify_client(app, client):
    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        }

    async def _fake_redis() -> _RedisStub:
        return _RedisStub()

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        query_router._RESOLVE_CACHE.clear()
        query_router._RESULT_CACHE.clear()
        query_router._SOURCE_CACHE.clear()
        query_router._GRAPH_NODE_CACHE.clear()
        query_router._DATASET_EXACT_COLUMN_CACHE.clear()
        query_router._DF_CACHE.clear()


def _ready_entry(
    source_id: str, name: str, schema_revision: str = "schema_rev_1"
) -> dict[str, str]:
    return {
        "id": source_id,
        "name": name,
        "schema_revision": schema_revision,
        "decision_mode": "deterministic_only",
        "visibility": "private",
        "owner_key_id": "key_resolve",
    }


async def test_verify_passes_dataset_scope_into_resolved_plan_revision_lookup(
    monkeypatch: pytest.MonkeyPatch,
    verify_client,
) -> None:
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "customer",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"derived_measure": 1, "category": 1},
    }
    seen: dict[str, str | None] = {"dataset_id": None}

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: (
            _ready_entry(
                "src_1",
                "Orders",
                schema_revision="source_rev_1",
            )
            if source_name == "Orders"
            else None
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: "org_schema_rev",
    )

    def _capture_schema_revision(**kwargs):  # type: ignore[no-untyped-def]
        seen["dataset_id"] = kwargs.get("dataset_id")
        return "source_rev_1"

    monkeypatch.setattr(
        query_router,
        "_resolved_plan_current_schema_revision",
        _capture_schema_revision,
    )

    response = await verify_client.post(
        "/v1/verify",
        json={
            "dataset_id": "src_1",
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "amount",
                "group_column": "customer",
                "aggregation": "sum",
                "schema_revision": "source_rev_1",
            },
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["valid"] is True
    assert body["verified"] is True
    assert seen["dataset_id"] == "src_1"
