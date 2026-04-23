from __future__ import annotations

import io

import pandas as pd
import pytest

from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import query as query_router
from apps.api_server.services.auto_planner import JoinHop, QueryPlan


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
def auth_overrides(app):
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
    yield
    app.dependency_overrides.clear()
    query_router._RESOLVE_CACHE.clear()
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._GRAPH_NODE_CACHE.clear()
    query_router._DATASET_EXACT_COLUMN_CACHE.clear()
    query_router._DF_CACHE.clear()


def _ready_entry(source_id: str, name: str, schema_revision: str = "schema_rev_1") -> dict[str, str]:
    return {
        "id": source_id,
        "name": name,
        "schema_revision": schema_revision,
        "decision_mode": "deterministic_only",
        "visibility": "private",
        "owner_key_id": "key_resolve",
    }


def test_intent_signature_is_stable_for_equivalent_raw_text() -> None:
    payload_a = query_router._intent_signature_payload(
        dataset_id="ds_1",
        allow_org_scope=False,
        metric_role="derived_measure",
        metric_hint="",
        group_by=[],
        preferred_source=None,
        aggregation="sum",
        filter_spec=None,
        limit=5,
        order="desc",
        constraints=query_router.ConstraintSpec(),
        raw_text="revenue by product",
        schema_revision="schema_rev_1",
    )
    payload_b = query_router._intent_signature_payload(
        dataset_id="ds_1",
        allow_org_scope=False,
        metric_role="derived_measure",
        metric_hint="",
        group_by=[],
        preferred_source=None,
        aggregation="sum",
        filter_spec=None,
        limit=5,
        order="desc",
        constraints=query_router.ConstraintSpec(),
        raw_text="product revenue",
        schema_revision="schema_rev_1",
    )

    assert query_router._intent_signature(payload_a) == query_router._intent_signature(payload_b)


@pytest.mark.asyncio
async def test_resolve_requires_explicit_scope_when_multiple_datasets(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [
            _ready_entry("src_1", "Orders"),
            _ready_entry("src_2", "Customers"),
        ],
    )

    resp = await client.post(
        "/v1/resolve",
        json={"metric": {"role": "derived_measure", "hint": "revenue"}},
    )

    body = resp.json()
    assert resp.status_code == 422
    assert body["error"]["code"] == "dataset_scope_required"


@pytest.mark.asyncio
async def test_resolve_returns_cached_resolved_plan(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
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
            }
        ],
        "roles_summary": {"derived_measure": 1},
    }

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("dataset-scoped resolve should not list visible sources")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, dataset_id: _ready_entry("src_1", "Orders"),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("dataset-scoped resolve should not use org schema_revision")
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

    async def _planner_must_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("dataset-scoped resolve cache should not build registry planner")

    monkeypatch.setattr(query_router, "_get_registry_planner", _planner_must_not_run)
    monkeypatch.setattr(
        query_router,
        "resolve_metric_column",
        lambda *args, **kwargs: (
            "Orders",
            "amount",
            0.97,
            [
                {
                    "source": "Orders",
                    "column": "amount",
                    "role": "derived_measure",
                    "magnitude": "medium",
                    "formula": "qty x price",
                    "confidence": 0.97,
                    "score_components": {"typed_intent": 0.18},
                    "notes": ["planner"],
                }
            ],
        ),
    )

    request_body = {
        "dataset_id": "src_1",
        "metric": {"role": "derived_measure", "hint": "revenue"},
        "aggregation": "sum",
    }
    first = await client.post("/v1/resolve", json=request_body)
    second = await client.post("/v1/resolve", json=request_body)

    first_body = first.json()
    second_body = second.json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["validated"] is True
    assert first_body["resolved_plan"]["source_name"] == "Orders"
    assert second_body["plan"][0].startswith("Resolve cache HIT")
    assert first_body["intent_signature"] == second_body["intent_signature"]
    assert first_body["plan_hash"] == second_body["plan_hash"]
    assert first_body["planner_mode"] == "dataset_meta_fast_path"
    assert first_body["schema_revision"] == "source_rev_1"


@pytest.mark.asyncio
async def test_resolve_dataset_fast_path_prefers_hot_source_cache(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    data = pd.DataFrame({"order_id": [1, 2], "amount": [10.0, 20.0]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "order_id",
                "role": "identifier",
                "formula": None,
                "is_numeric": True,
                "magnitude": "small",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 1, "derived_measure": 1},
    }

    async with query_router._CACHE_LOCK:
        query_router._SOURCE_CACHE["src_1"] = query_router._CachedSource(
            parquet_bytes=parquet_bytes,
            parquet_schema_meta=b"",
            profile={},
            mojo_profile={},
            relations=[],
            graph_nodes=query_router._graph_nodes_from_meta(schema_meta),
            schema_meta=schema_meta,
            mojo_profiling_status={},
            content_keyed=True,
        )

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [_ready_entry("src_1", "Orders")],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, dataset_id: _ready_entry("src_1", "Orders"),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("dataset-scoped resolve should not read registry meta on a hot cache hit")
        ),
    )

    response = await client.post(
        "/v1/resolve",
        json={
            "dataset_id": "src_1",
            "metric": {"role": "identifier", "hint": "order id"},
            "aggregation": "count",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["validated"] is True
    assert body["planner_mode"] == "dataset_meta_fast_path"
    assert body["schema_revision"] == "source_rev_1"
    assert body["resolved_plan"]["source_name"] == "Orders"


@pytest.mark.asyncio
async def test_resolve_dataset_fast_path_reuses_registry_graph_nodes_after_source_cache_eviction(
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "order_id",
                "role": "identifier",
                "formula": None,
                "is_numeric": True,
                "magnitude": "small",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 1, "derived_measure": 1},
    }
    calls = {"count": 0}
    original = query_router._graph_nodes_from_meta

    def _counting_graph_nodes(meta: dict) -> dict[str, query_router.ColumnNode]:
        calls["count"] += 1
        return original(meta)

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(query_router, "_graph_nodes_from_meta", _counting_graph_nodes)

    first_meta, first_nodes = await query_router._get_resolve_dataset_meta(
        org_id="org_resolve",
        dataset_id="src_1",
        schema_revision="source_rev_1",
    )
    second_meta, second_nodes = await query_router._get_resolve_dataset_meta(
        org_id="org_resolve",
        dataset_id="src_1",
        schema_revision="source_rev_1",
    )

    assert first_meta == schema_meta
    assert second_meta == schema_meta
    assert first_nodes == second_nodes
    assert first_nodes is second_nodes
    assert calls["count"] == 1


def test_find_exact_dataset_column_cached_reuses_lookup() -> None:
    query_router._DATASET_EXACT_COLUMN_CACHE.clear()
    schema_meta = {
        "columns": [
            {"name": "Order ID"},
            {"name": "Total Amount"},
        ]
    }
    calls = {"count": 0}
    original = query_router._normalize_hint_text

    def _counting_normalize(text: str) -> str:
        calls["count"] += 1
        return original(text)

    query_router._normalize_hint_text = _counting_normalize
    try:
        normalized_hint = original("Total Amount")
        first = query_router._find_exact_dataset_column_cached(
            org_id="org_resolve",
            dataset_id="src_1",
            schema_revision="source_rev_1",
            schema_meta=schema_meta,
            normalized_hint=normalized_hint,
        )
        second = query_router._find_exact_dataset_column_cached(
            org_id="org_resolve",
            dataset_id="src_1",
            schema_revision="source_rev_1",
            schema_meta=schema_meta,
            normalized_hint=normalized_hint,
        )
    finally:
        query_router._normalize_hint_text = original

    assert first == second == {"name": "Total Amount"}
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_query_rejects_stale_resolved_plan_schema_revision(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("owner resolved-plan validation should not list sources")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: _ready_entry(
            "src_1",
            "Orders",
            schema_revision="source_rev_current",
        )
        if source_name == "Orders"
        else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_current",
    )

    resp = await client.post(
        "/v1/query",
        json={
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "amount",
                "aggregation": "sum",
                "schema_revision": "source_rev_old",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 409
    assert body["error"]["code"] == "schema_revision_mismatch"


@pytest.mark.asyncio
async def test_query_executes_resolved_plan_exact_path(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
        if source_id == "src_1"
        else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: _ready_entry(
            "src_1",
            "Orders",
            schema_revision="source_rev_1",
        )
        if source_name == "Orders"
        else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("owner resolved-plan exact path should not list sources")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )

    resp = await client.post(
        "/v1/query",
        json={
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "amount",
                "group_column": "customer",
                "aggregation": "sum",
                "schema_revision": "source_rev_1",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["exact_spec"] is True
    assert body["validated"] is True
    assert body["decision_path"] == "exact_spec"
    assert body["result"] == [
        {"group": "B", "value": 20.0},
        {"group": "A", "value": 10.0},
    ]


@pytest.mark.asyncio
async def test_verify_accepts_resolved_plan_exact_path_with_source_schema_revision(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
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

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: _ready_entry(
            "src_1",
            "Orders",
            schema_revision="source_rev_1",
        )
        if source_name == "Orders"
        else None,
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

    resp = await client.post(
        "/v1/verify",
        json={
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "amount",
                "group_column": "customer",
                "aggregation": "sum",
                "schema_revision": "source_rev_1",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["valid"] is True
    assert body["verified"] is True
    assert body["schema_revision"] == "source_rev_1"
    assert body["resolved"]["source_name"] == "Orders"


@pytest.mark.asyncio
async def test_verify_accepts_count_on_non_numeric_exact_column(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "order_id",
                "role": "identifier",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "id",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 1},
    }

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: _ready_entry(
            "src_1",
            "Orders",
            schema_revision="source_rev_1",
        )
        if source_name == "Orders"
        else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )

    resp = await client.post(
        "/v1/verify",
        json={
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "order_id",
                "aggregation": "count",
                "schema_revision": "source_rev_1",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["valid"] is True
    assert body["verified"] is True
    assert body["resolved"]["metric_column"] == "order_id"


@pytest.mark.asyncio
async def test_resolve_org_scope_single_source_returns_source_schema_revision_for_query_handoff(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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
    source_entry = _ready_entry("src_1", "Orders", schema_revision="source_rev_1")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [source_entry],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: source_entry if source_name == "Orders" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: "org_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )

    class _PlannerStub:
        graph: dict[str, dict[str, object]] = {}

        def plan(self, **_kwargs):  # type: ignore[no-untyped-def]
            return QueryPlan(
                metric_src="Orders",
                metric_col="amount",
                metric_conf=0.97,
                metric_role="derived_measure",
                agg="sum",
                group_col="customer",
                group_src="Orders",
                group_conf=0.95,
                steps=["planner resolved Orders.amount by customer"],
            )

    async def _fake_get_registry_planner(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _PlannerStub(), False, "org_rev_1"

    monkeypatch.setattr(query_router, "_get_registry_planner", _fake_get_registry_planner)
    monkeypatch.setattr(
        query_router,
        "resolve_metric_column",
        lambda *args, **kwargs: (
            "Orders",
            "amount",
            0.97,
            [
                {
                    "source": "Orders",
                    "column": "amount",
                    "role": "derived_measure",
                    "magnitude": "medium",
                    "formula": "qty x price",
                    "confidence": 0.97,
                    "score_components": {"typed_intent": 0.18},
                    "notes": ["planner"],
                }
            ],
        ),
    )

    resolve_resp = await client.post(
        "/v1/resolve",
        json={
            "metric": {"role": "derived_measure", "hint": "revenue"},
            "group_by": ["customer"],
            "aggregation": "sum",
            "allow_org_scope": True,
        },
    )

    resolve_body = resolve_resp.json()
    assert resolve_resp.status_code == 200
    assert resolve_body["validated"] is True
    assert resolve_body["schema_revision"] == "source_rev_1"
    assert resolve_body["resolved_plan"]["schema_revision"] == "source_rev_1"
    assert resolve_body["resolved_plan"]["source_name"] == "Orders"

    query_resp = await client.post(
        "/v1/query",
        json={"resolved_plan": resolve_body["resolved_plan"]},
    )

    query_body = query_resp.json()
    assert query_resp.status_code == 200
    assert query_body["decision_path"] == "exact_spec"
    assert query_body["schema_revision"] == "source_rev_1"
    assert query_body["result"] == [
        {"group": "B", "value": 20.0},
        {"group": "A", "value": 10.0},
    ]


@pytest.mark.asyncio
async def test_resolve_high_confidence_registry_metric_does_not_reclarify_on_generic_candidate_gap(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    source_entry = _ready_entry("src_pos", "POSNew", schema_revision="source_rev_pos")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [source_entry],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: source_entry if source_name == "POSNew" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: "org_rev_pos",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_pos",
    )

    class _PlannerStub:
        graph = {
            "POSNew": {
                "EXT_PRICE": query_router.ColumnNode(
                    name="EXT_PRICE",
                    role="unit_measure",
                    is_numeric=True,
                    magnitude_class="medium",
                    fill_rate=1.0,
                ),
                "EXT_COST": query_router.ColumnNode(
                    name="EXT_COST",
                    role="unit_measure",
                    is_numeric=True,
                    magnitude_class="large",
                    fill_rate=1.0,
                    formula="EXT_COST = AAR_MARGIN_% + NBV",
                ),
                "SHIP_TO_COUNTRY": query_router.ColumnNode(
                    name="SHIP_TO_COUNTRY",
                    role="category",
                    is_numeric=False,
                    fill_rate=1.0,
                ),
            }
        }

        def plan(self, **_kwargs):  # type: ignore[no-untyped-def]
            return QueryPlan(
                metric_src="POSNew",
                metric_col="EXT_PRICE",
                metric_conf=0.855,
                metric_role="unit_measure",
                agg="sum",
                group_col="SHIP_TO_COUNTRY",
                group_src="POSNew",
                group_conf=1.0,
                steps=[
                    "[query_hints/registry] 'sales' → POSNew.EXT_PRICE  conf=0.855  role=unit_measure",
                    "[resolve_group] 'country ship' → POSNew.SHIP_TO_COUNTRY  score=1.194",
                ],
            )

    async def _fake_get_registry_planner(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _PlannerStub(), True, "org_rev_pos"

    monkeypatch.setattr(query_router, "_get_registry_planner", _fake_get_registry_planner)
    monkeypatch.setattr(
        query_router,
        "resolve_metric_column",
        lambda *args, **kwargs: (
            "POSNew",
            "EXT_COST",
            0.941,
            [
                {
                    "source": "POSNew",
                    "column": "EXT_COST",
                    "role": "unit_measure",
                    "magnitude": "large",
                    "formula": "EXT_COST = AAR_MARGIN_% + NBV",
                    "confidence": 0.941,
                    "score_components": {"planner_confidence": 0.941},
                    "notes": ["ambiguous-top2-gap:0.009"],
                },
                {
                    "source": "POSNew",
                    "column": "EXT_PRICE",
                    "role": "unit_measure",
                    "magnitude": "medium",
                    "formula": None,
                    "confidence": 0.932,
                    "score_components": {"planner_confidence": 0.932},
                    "notes": ["close-second-to:EXT_COST"],
                },
            ],
        ),
    )

    response = await client.post(
        "/v1/resolve",
        json={
            "metric": {"role": "derived_measure", "hint": "sales"},
            "group_by": ["ship to country"],
            "preferred_source": "POSNew",
            "aggregation": "sum",
            "allow_org_scope": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["validated"] is True
    assert body["clarification_required"] is False
    assert body["resolved_source"] == "POSNew"
    assert body["resolved_column"] == "EXT_PRICE"
    assert body["resolved_plan"]["metric_column"] == "EXT_PRICE"
    assert body["schema_revision"] == "source_rev_pos"
    assert body["candidates"][0]["column"] == "EXT_PRICE"
    assert "planner-authoritative-selection" in body["candidates"][0]["notes"]


@pytest.mark.asyncio
async def test_resolve_many_to_many_planner_join_path_is_marked_executable(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    orders_entry = _ready_entry("src_orders", "Orders", schema_revision="source_rev_orders")
    pos_entry = _ready_entry("src_pos", "POSNew", schema_revision="source_rev_pos")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [orders_entry, pos_entry],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        lambda org_id, source_name: (
            orders_entry if source_name == "Orders" else pos_entry if source_name == "POSNew" else None
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: "org_rev_orders_pos",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (
            "source_rev_orders" if source_id == "src_orders" else "source_rev_pos"
        ),
    )

    class _PlannerStub:
        graph = {
            "Orders": {
                "EXT_PRICE": query_router.ColumnNode(
                    name="EXT_PRICE",
                    role="derived_measure",
                    is_numeric=True,
                    magnitude_class="medium",
                    fill_rate=1.0,
                ),
            },
            "POSNew": {
                "INVENTORY_TYPE": query_router.ColumnNode(
                    name="INVENTORY_TYPE",
                    role="category",
                    is_numeric=False,
                    fill_rate=1.0,
                ),
            },
        }

        def plan(self, **_kwargs):  # type: ignore[no-untyped-def]
            return QueryPlan(
                metric_src="Orders",
                metric_col="EXT_PRICE",
                metric_conf=0.963,
                metric_role="derived_measure",
                agg="sum",
                group_col="INVENTORY_TYPE",
                group_src="POSNew",
                group_conf=1.732,
                join_conf=0.259,
                path_confidence=0.259,
                join_hops=[
                    JoinHop(
                        left_source="Orders",
                        right_source="POSNew",
                        left_key="PART_NUMBER",
                        right_key="PART_NUMBER",
                        confidence=0.676,
                        cardinality="many_to_many",
                    )
                ],
                validation_notes=["ambiguous join candidates between Orders and POSNew"],
                steps=[
                    "[query_hints/registry] 'sales' → Orders.EXT_PRICE  conf=0.963  role=derived_measure",
                    "[resolve_group/source_hint_exact] 'pos inventory type' → POSNew.INVENTORY_TYPE  score=1.732",
                    "[join_path] hop 1: Orders.PART_NUMBER ↔ POSNew.PART_NUMBER  conf=0.676  card=many_to_many",
                ],
            )

    async def _fake_get_registry_planner(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _PlannerStub(), True, "org_rev_orders_pos"

    monkeypatch.setattr(query_router, "_get_registry_planner", _fake_get_registry_planner)
    monkeypatch.setattr(
        query_router,
        "resolve_metric_column",
        lambda *args, **kwargs: (
            "Orders",
            "EXT_PRICE",
            0.963,
            [
                {
                    "source": "Orders",
                    "column": "EXT_PRICE",
                    "role": "derived_measure",
                    "magnitude": "medium",
                    "formula": "qty * price",
                    "confidence": 0.963,
                    "score_components": {"planner_confidence": 0.963},
                    "notes": ["planner-authoritative-selection"],
                }
            ],
        ),
    )

    response = await client.post(
        "/v1/resolve",
        json={
            "metric": {"role": "derived_measure", "hint": "sales"},
            "group_by": ["pos inventory type"],
            "preferred_source": "Orders",
            "aggregation": "sum",
            "allow_org_scope": True,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["validated"] is True
    assert body["clarification_required"] is False
    assert body["resolved_plan"]["join_path"]["reject_on_fanout"] is False
    assert body["resolved_plan"]["join_path"]["edges"][0]["allow_many_to_many"] is True
    assert body["resolved_plan"]["join_path"]["edges"][0]["expected_cardinality"] == "many_to_many"


@pytest.mark.asyncio
async def test_query_exact_join_path_owner_loads_named_join_sources_without_listing_registry(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    orders = pd.DataFrame({"customer_id": ["A", "B"], "amount": [10.0, 20.0]})
    customers = pd.DataFrame({"customer_id": ["A", "B"], "customer_name": ["Acme", "Beta"]})
    orders_buf = io.BytesIO()
    customers_buf = io.BytesIO()
    orders.to_parquet(orders_buf, index=False)
    customers.to_parquet(customers_buf, index=False)

    orders_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "customer_id",
                "role": "identifier",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 1, "derived_measure": 1},
    }
    customers_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "customer_id",
                "role": "identifier",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
            {
                "name": "customer_name",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 1, "category": 1},
    }

    def _get_source_entry_by_name(org_id: str, source_name: str) -> dict[str, str] | None:
        if source_name == "Orders":
            return _ready_entry("src_orders", "Orders", schema_revision="schema_rev_join")
        if source_name == "Customers":
            return _ready_entry("src_customers", "Customers", schema_revision="schema_rev_join")
        return None

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("owner exact join path should not list visible sources")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        _get_source_entry_by_name,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: "schema_rev_join",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_connections",
        lambda org_id: [
            {
                "source_a_name": "Orders",
                "source_b_name": "Customers",
                "col_a": "customer_id",
                "col_b": "customer_id",
                "confidence": 0.95,
                "cardinality": "one_to_one",
            }
        ],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: (
            orders_buf.getvalue() if source_id == "src_orders" else customers_buf.getvalue()
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: (
            orders_meta if source_id == "src_orders" else customers_meta
        ),
    )

    response = await client.post(
        "/v1/query",
        json={
            "source_name": "Orders",
            "metric_column": "amount",
            "group_column": "customer_name",
            "aggregation": "sum",
            "join_path": {
                "base_source": "Orders",
                "group_source": "Customers",
                "edges": [
                    {
                        "left_source": "Orders",
                        "left_key": "customer_id",
                        "right_source": "Customers",
                        "right_key": "customer_id",
                    }
                ],
            },
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["exact_spec"] is True
    assert body["validated"] is True
    assert body["result"] == [
        {"group": "Beta", "value": 20.0},
        {"group": "Acme", "value": 10.0},
    ]


@pytest.mark.asyncio
async def test_query_resolved_plan_owner_cache_hit_skips_visibility_listing(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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
    lookup_calls = {"count": 0}

    def _get_source_entry_by_name(org_id: str, source_name: str) -> dict[str, str] | None:
        lookup_calls["count"] += 1
        if source_name != "Orders":
            return None
        return _ready_entry("src_1", "Orders", schema_revision="source_rev_1")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("owner resolved-plan cache hit should not list visible sources")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry_by_name",
        _get_source_entry_by_name,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )

    request_body = {
        "resolved_plan": {
            "source_name": "Orders",
            "metric_column": "amount",
            "aggregation": "sum",
            "schema_revision": "source_rev_1",
        }
    }
    first = await client.post("/v1/query", json=request_body)
    second = await client.post("/v1/query", json=request_body)

    first_body = first.json()
    second_body = second.json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["result"] == 30.0
    assert second_body["result"] == 30.0
    assert any(step.startswith("Result cache HIT") for step in second_body["plan"])
    assert lookup_calls["count"] >= 1


@pytest.mark.asyncio
async def test_query_dataset_scoped_exact_path_uses_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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
    source_revision_calls = {"count": 0}
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (
            source_revision_calls.__setitem__("count", source_revision_calls["count"] + 1)
            or "source_rev_1"
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)
    assert source_revision_calls["count"] == 2


@pytest.mark.asyncio
async def test_query_dataset_scoped_exact_path_uses_cached_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
    dataset_entry["source_schema_revision"] = "source_rev_cached"

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("cached source schema revision should be used")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)


@pytest.mark.asyncio
async def test_query_dataset_scoped_exact_count_uses_metadata_fast_path(
    monkeypatch: pytest.MonkeyPatch,
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
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
    dataset_entry["source_schema_revision"] = "source_rev_cached"
    dataset_entry["row_count"] = 2

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("cached source schema revision should be used")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("metadata fast path should not load parquet")
        ),
    )
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert any("metadata fast path" in step for step in first.plan)
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)


@pytest.mark.asyncio
async def test_resolve_count_uses_dataset_scoped_anchor_when_metric_lookup_fails(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "Cage Code",
                "role": "identifier",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
            {
                "name": "Company Name",
                "role": "identifier",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"identifier": 2},
    }

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [_ready_entry("src_1", "Catalog")],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, dataset_id: _ready_entry("src_1", "Catalog"),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("dataset-scoped resolve should not use org schema_revision")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )

    async def _planner_must_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("dataset-scoped count resolve should not build registry planner")

    monkeypatch.setattr(query_router, "_get_registry_planner", _planner_must_not_run)
    monkeypatch.setattr(
        query_router,
        "resolve_metric_column",
        lambda *args, **kwargs: ("", "", 0.0, []),
    )

    resp = await client.post(
        "/v1/resolve",
        json={
            "dataset_id": "src_1",
            "metric": {"role": "identifier", "hint": "Cage Code"},
            "aggregation": "count",
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["validated"] is True
    assert body["resolved_plan"]["source_name"] == "Catalog"
    assert body["resolved_plan"]["metric_column"] == "Cage Code"
    assert body["resolved_role"] == "identifier"
    assert any("COUNT anchor fallback" in step for step in body["plan"])
    assert body["planner_mode"] == "dataset_meta_fast_path"
    assert body["schema_revision"] == "source_rev_1"


@pytest.mark.asyncio
async def test_resolve_dataset_scoped_exact_metric_and_group_skip_registry_planner(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    schema_meta = {
        "row_count": 3,
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

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: [_ready_entry("src_1", "Orders")],
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, dataset_id: _ready_entry("src_1", "Orders"),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("dataset-scoped resolve should not use org schema_revision")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: "source_rev_1",
    )

    async def _planner_must_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("dataset-scoped exact resolve should not build registry planner")

    monkeypatch.setattr(query_router, "_get_registry_planner", _planner_must_not_run)

    resp = await client.post(
        "/v1/resolve",
        json={
            "dataset_id": "src_1",
            "metric": {"role": "derived_measure", "hint": "amount"},
            "group_by": ["customer"],
            "aggregation": "sum",
            "include_explanation": True,
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["validated"] is True
    assert body["planner_mode"] == "dataset_meta_fast_path"
    assert body["resolved_plan"]["source_name"] == "Orders"
    assert body["resolved_plan"]["metric_column"] == "amount"
    assert body["resolved_plan"]["group_column"] == "customer"
    assert body["resolved_role"] == "derived_measure"
    assert any("Metric exact match: Orders.amount" in step for step in body["plan"])
    assert any("Group exact match: Orders.customer" in step for step in body["plan"])
    assert body["schema_revision"] == "source_rev_1"
