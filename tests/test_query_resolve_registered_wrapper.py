from types import SimpleNamespace

import pytest

from apps.api_server.routers import query as query_router


@pytest.mark.anyio
async def test_query_wrapper_preserves_resolve_registered_delegate() -> None:
    query_router._RESOLVE_CACHE.clear()

    calls = {"planner": 0}
    scoped_entry = {
        "id": "src_1",
        "name": "Orders",
        "schema_revision": "schema_rev_1",
        "decision_mode": "deterministic_only",
    }

    async def _fake_get_registry_planner(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["planner"] += 1
        return SimpleNamespace(graph={}), False, "schema_rev_1"

    async def _fake_run_cached_planner_method(*args, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            steps=["planned"],
            metric_src="Orders",
            metric_col="amount",
            metric_role=query_router.DERIVED_MEASURE,
            metric_conf=0.97,
            error=None,
            group_col=None,
            group_src=None,
            join_hops=[],
            validation_notes=[],
        )

    original_scope_entries = query_router._resolve_scope_entries
    original_get_registry_planner = query_router._get_registry_planner
    original_run_cached_planner_method = query_router._run_cached_planner_method
    original_planner_query_confidence = query_router._planner_query_confidence
    original_planner_metric_candidate_payloads = query_router._planner_metric_candidate_payloads
    original_decision_contract_flags = query_router._decision_contract_flags
    original_resolved_plan_current_schema_revision = (
        query_router._resolved_plan_current_schema_revision
    )
    try:
        query_router._resolve_scope_entries = lambda **kwargs: ([scoped_entry], None)
        query_router._get_registry_planner = _fake_get_registry_planner
        query_router._run_cached_planner_method = _fake_run_cached_planner_method
        query_router._planner_query_confidence = lambda plan: 0.97
        query_router._planner_metric_candidate_payloads = lambda **kwargs: [
            {
                "source": "Orders",
                "column": "amount",
                "role": query_router.DERIVED_MEASURE,
                "magnitude": "medium",
                "formula": "qty x price",
                "confidence": 0.97,
                "score_components": {"planner_confidence": 0.97},
                "notes": ["planner-selected"],
            }
        ]
        query_router._decision_contract_flags = lambda *args, **kwargs: (True, False, None)
        query_router._resolved_plan_current_schema_revision = lambda **kwargs: "schema_rev_1"

        response = await query_router._resolve_registered_intent(
            query_router.ResolveRequest(
                metric={"role": query_router.DERIVED_MEASURE, "hint": "revenue"},
                aggregation="sum",
                allow_org_scope=True,
            ),
            auth={"org_id": "org_test", "role": "owner"},
            request_id="req_test",
        )
    finally:
        query_router._resolve_scope_entries = original_scope_entries
        query_router._get_registry_planner = original_get_registry_planner
        query_router._run_cached_planner_method = original_run_cached_planner_method
        query_router._planner_query_confidence = original_planner_query_confidence
        query_router._planner_metric_candidate_payloads = original_planner_metric_candidate_payloads
        query_router._decision_contract_flags = original_decision_contract_flags
        query_router._resolved_plan_current_schema_revision = (
            original_resolved_plan_current_schema_revision
        )
        query_router._RESOLVE_CACHE.clear()

    assert calls["planner"] == 1
    assert response.validated is True
    assert response.resolved_source == "Orders"
    assert response.schema_revision == "schema_rev_1"
    assert response.planner_mode == "registry_planner"
