"""Tests for test_resolve_api_contract: resolve_dataset.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-3/tests/test_resolve_api_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_resolve_api_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
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
            AssertionError(
                "dataset-scoped resolve should not read registry meta on a hot cache hit"
            )
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


