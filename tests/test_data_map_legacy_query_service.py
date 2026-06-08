import pytest

from apps.api_server.routers import data_map as data_map_router
from apps.api_server.services.data_map_legacy_query import execute_legacy_query


def test_data_map_router_reexports_legacy_query_parser() -> None:
    intent = data_map_router._parse_query_intent("top 5 revenue by customers")

    assert intent["aggregation"] == "sum"
    assert intent["metric_hint"] == "revenue"
    assert intent["group_hint"] == "customer"
    assert intent["limit"] == 5


@pytest.mark.anyio
async def test_execute_legacy_query_uses_injected_loader() -> None:
    payload = data_map_router._LegacyQueryRequest(
        query="total revenue by customer",
        sources=[
            data_map_router.DataSource(
                name="Orders",
                records=[
                    {"customer": "A", "revenue": 10.0},
                    {"customer": "A", "revenue": 5.0},
                    {"customer": "B", "revenue": 7.0},
                ],
            )
        ],
        limit=10,
    )

    async def _load_source(src, _org_id):  # type: ignore[no-untyped-def]
        return src.records or []

    result = await execute_legacy_query(
        payload,
        org_id="org_123",
        load_source_fn=_load_source,
        semantic_similarity_fn=data_map_router._semantic_similarity,
    )

    assert result.metric_field == "revenue"
    assert result.group_field == "customer"
    assert result.result == [
        {"customer": "A", "revenue": 15.0, "count": 2},
        {"customer": "B", "revenue": 7.0, "count": 1},
    ]
