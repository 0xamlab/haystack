from apps.api_server.routers import query as query_router


def test_query_wrapper_find_exact_dataset_column_uses_router_normalizer() -> None:
    original = query_router._normalize_hint_text
    query_router._normalize_hint_text = lambda value: "forced"
    try:
        match = query_router._find_exact_dataset_column(
            {"columns": [{"name": "Order ID"}]},
            "forced",
        )
    finally:
        query_router._normalize_hint_text = original

    assert match == {"name": "Order ID"}
