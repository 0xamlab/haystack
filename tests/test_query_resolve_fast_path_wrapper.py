from apps.api_server.routers import query as query_router
from apps.api_server.routers import query_resolve_fast_path


def test_query_wrapper_preserves_resolve_fast_path_surface() -> None:
    for symbol_name in (
        "_dataset_candidate_payload",
        "_resolve_entry_ready",
        "_resolved_plan_current_schema_revision",
    ):
        assert getattr(query_router, symbol_name) is getattr(
            query_resolve_fast_path,
            symbol_name,
        )


def test_query_wrapper_preserves_resolve_scope_delegate() -> None:
    assert query_router._resolve_scope_entries.__name__ == "_resolve_scope_entries"


def test_query_wrapper_preserves_dataset_fast_path_delegate() -> None:
    assert query_router._resolve_single_dataset_fast_path.__name__ == (
        "_resolve_single_dataset_fast_path"
    )
