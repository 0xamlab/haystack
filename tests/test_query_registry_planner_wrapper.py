from apps.api_server.routers import query as query_router
from apps.api_server.routers import query_registry_planner


def test_query_wrapper_preserves_registry_planner_surface() -> None:
    assert query_router._planner_auth_scope_key is query_registry_planner.planner_auth_scope_key
    assert (
        query_router._run_cached_planner_method is query_registry_planner.run_cached_planner_method
    )
    assert query_router._get_registry_planner.__name__ == "_get_registry_planner"
    assert query_router._try_incremental_registry_planner_update.__name__ == (
        "_try_incremental_registry_planner_update"
    )
