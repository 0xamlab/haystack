"""Tests for test_resolve_api_contract: misc_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-3/tests/test_resolve_api_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_resolve_api_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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
            orders_entry
            if source_name == "Orders"
            else pos_entry
            if source_name == "POSNew"
            else None
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


@pytest.mark.anyio
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
        lambda org_id, source_id: orders_meta if source_id == "src_orders" else customers_meta,
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


@pytest.mark.anyio
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
    captured_log_response: list[bool] = []
    original_build_query_response = query_router._build_query_response

    def _capture_build_query_response(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_log_response.append(bool(kwargs.get("log_response", True)))
        return original_build_query_response(*args, **kwargs)

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
    monkeypatch.setattr(query_router, "_build_query_response", _capture_build_query_response)

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
    assert captured_log_response[-1] is False


@pytest.mark.anyio
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


