from apps.api_server.routers import query as query_router
from apps.api_server.routers import query_profiling


def test_query_wrapper_preserves_profiling_surface() -> None:
    for symbol_name in (
        "_profile_arrow_table",
        "_profile_records",
        "_profile_records_and_arrow",
        "_relation_detect_sample_limit",
        "_try_numeric",
    ):
        assert getattr(query_router, symbol_name) is getattr(query_profiling, symbol_name)
