from apps.api_server.routers import query as query_router
from apps.api_server.routers import query_response_helpers


def test_query_wrapper_preserves_response_helper_surface() -> None:
    for symbol_name in (
        "_MAX_RESOLVE_CANDIDATES",
        "_MAX_RESOLVE_SOURCE_SCORES",
        "_build_query_response",
        "_build_resolve_response",
        "_compute_exact_confidence",
        "_dedupe_source_values",
        "_exact_plan_basis",
        "_immutable_plan_hash",
        "_normalize_candidates",
        "_normalize_constraint_spec",
        "_normalize_filter_spec",
        "_normalize_join_path",
        "_normalize_join_path_spec",
        "_resolve_to_query_response",
        "_resolved_source_set",
    ):
        assert getattr(query_router, symbol_name) is getattr(query_response_helpers, symbol_name)
