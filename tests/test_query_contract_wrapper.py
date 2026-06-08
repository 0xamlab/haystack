from apps.api_server.routers import query as query_router
from apps.api_server.routers import query_contract


def test_query_wrapper_preserves_contract_surface() -> None:
    for symbol_name in (
        "ALL_ROLES",
        "BASE_MEASURE",
        "CATEGORY",
        "COMPONENT",
        "ConstraintSpec",
        "CandidateColumn",
        "DERIVED_MEASURE",
        "FilterSpec",
        "IDENTIFIER",
        "JoinEdgeSpec",
        "JoinPathSpec",
        "METRIC",
        "MetricSpec",
        "QueryPayload",
        "QueryRequest",
        "QueryResponse",
        "RATIO",
        "ResolveRequest",
        "ResolveResponse",
        "ResolvedPlan",
        "TEXT",
        "TIME",
        "UNIT_MEASURE",
        "_DEFAULT_JOIN_PATH_HOPS",
        "_MAX_JOIN_PATH_HOPS",
        "_decision_contract_flags",
        "_http_error",
        "_query_plan_hash",
        "_select_count_anchor_column",
    ):
        assert getattr(query_router, symbol_name) is getattr(query_contract, symbol_name)
