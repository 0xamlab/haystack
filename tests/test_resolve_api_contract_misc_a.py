"""Tests for test_resolve_api_contract: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-3/tests/test_resolve_api_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_resolve_api_contract_helpers import *  # noqa: F401,F403


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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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
        lambda org_id, source_name: (
            _ready_entry(
                "src_1",
                "Orders",
                schema_revision="source_rev_current",
            )
            if source_name == "Orders"
            else None
        ),
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


@pytest.mark.anyio
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
        lambda org_id, source_id: (
            _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
            if source_id == "src_1"
            else None
        ),
    )
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


@pytest.mark.anyio
async def test_query_executes_resolved_plan_exact_path_with_generic_filter_conditions(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    auth_overrides,
) -> None:
    data = pd.DataFrame(
        {
            "amount": [10, 20, 30],
            "customer": ["A", "B", "C"],
            "status": ["closed", "closed", "open"],
            "delay_minutes": [5, 25, 40],
        }
    )
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
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
            {
                "name": "status",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
            {
                "name": "delay_minutes",
                "role": "base_measure",
                "formula": None,
                "is_numeric": True,
                "magnitude": "small",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"derived_measure": 1, "category": 2, "base_measure": 1},
    }

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: (
            _ready_entry("src_1", "Orders", schema_revision="source_rev_1")
            if source_id == "src_1"
            else None
        ),
    )
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
                "filter": {
                    "conditions": [
                        {"dimension_hint": "status", "op": "eq", "value": "closed"},
                        {"dimension_hint": "delay", "op": "gte", "value": 15},
                    ]
                },
                "schema_revision": "source_rev_1",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["result"] == [{"group": "B", "value": 20.0}]
    assert any("Filter `status eq 'closed'`" in step for step in body["plan"])
    assert any("Filter `delay_minutes gte 15`" in step for step in body["plan"])


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_verify_rejects_unresolvable_filter_dimension_hint_on_resolved_plan(
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
                "name": "status",
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

    resp = await client.post(
        "/v1/verify",
        json={
            "resolved_plan": {
                "source_name": "Orders",
                "metric_column": "amount",
                "aggregation": "sum",
                "filter": {
                    "conditions": [{"dimension_hint": "priority", "op": "eq", "value": "high"}]
                },
                "schema_revision": "source_rev_1",
            }
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["valid"] is False
    assert any("did not resolve" in error for error in body["errors"])


@pytest.mark.anyio
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


