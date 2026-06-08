from __future__ import annotations

from collections import deque

import httpx
import pytest

from apps.api_server.connectors.rest_connector import (
    RESTConnector,
    RESTPaginationError,
    fetch_rest_records_sync,
)


class _FakeSyncClient:
    def __init__(self, responses, calls):  # type: ignore[no-untyped-def]
        self._responses = responses
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None

    def get(self, url, headers=None, params=None):  # type: ignore[no-untyped-def]
        self._calls.append({"method": "GET", "url": url, "params": dict(params or {})})
        return self._responses.popleft()

    def post(self, url, headers=None, params=None, json=None):  # type: ignore[no-untyped-def]
        self._calls.append(
            {"method": "POST", "url": url, "params": dict(params or {}), "json": json}
        )
        return self._responses.popleft()


def _json_response(url: str, payload, *, headers=None) -> httpx.Response:  # type: ignore[no-untyped-def]
    return httpx.Response(
        200,
        json=payload,
        headers=headers,
        request=httpx.Request("GET", url),
    )


@pytest.mark.anyio
async def test_rest_connector_page_number_pagination_stops_when_next_link_disappears(monkeypatch):
    responses = deque(
        [
            _json_response(
                "https://example.test/items?page=1",
                [{"id": 1}, {"id": 2}],
                headers={"Link": '<https://example.test/items?page=2>; rel="next"'},
            ),
            _json_response("https://example.test/items?page=2", [{"id": 3}]),
        ]
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: _FakeSyncClient(responses, calls),
    )

    connector = RESTConnector(
        {
            "url": "https://example.test/items",
            "pagination": {
                "mode": "page_number",
                "page_param": "page",
                "start_page": 1,
                "next_link_rel": "next",
                "max_pages": 3,
            },
        }
    )

    records = await connector.fetch_data()

    assert [row["id"] for row in records] == [1, 2, 3]
    assert [call["params"]["page"] for call in calls] == [1, 2]


@pytest.mark.anyio
async def test_rest_connector_cursor_pagination_rejects_duplicate_cursor(monkeypatch):
    responses = deque(
        [
            _json_response(
                "https://example.test/items", {"items": [{"id": 1}], "next_cursor": "cursor-a"}
            ),
            _json_response(
                "https://example.test/items", {"items": [{"id": 2}], "next_cursor": "cursor-a"}
            ),
        ]
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: _FakeSyncClient(responses, calls),
    )

    connector = RESTConnector(
        {
            "url": "https://example.test/items",
            "data_path": "items",
            "pagination": {
                "mode": "cursor_path",
                "next_path": "next_cursor",
                "cursor_param": "cursor",
                "max_pages": 3,
            },
        }
    )

    with pytest.raises(RESTPaginationError, match="repeated a cursor token"):
        await connector.fetch_data()


@pytest.mark.anyio
async def test_rest_connector_cursor_pagination_follows_next_url_from_payload(monkeypatch):
    responses = deque(
        [
            _json_response(
                "https://pokeapi.test/api/v2/ability/?limit=2",
                {
                    "count": 4,
                    "next": "https://pokeapi.test/api/v2/ability/?limit=2&offset=2",
                    "previous": None,
                    "results": [{"name": "stench"}, {"name": "drizzle"}],
                },
            ),
            _json_response(
                "https://pokeapi.test/api/v2/ability/?limit=2&offset=2",
                {
                    "count": 4,
                    "next": None,
                    "previous": "https://pokeapi.test/api/v2/ability/?limit=2",
                    "results": [{"name": "speed-boost"}, {"name": "battle-armor"}],
                },
            ),
        ]
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: _FakeSyncClient(responses, calls),
    )

    connector = RESTConnector(
        {
            "url": "https://pokeapi.test/api/v2/ability/?limit=2",
            "data_path": "results",
            "pagination": {
                "mode": "cursor_path",
                "next_path": "next",
                "max_pages": 3,
            },
        }
    )

    records = await connector.fetch_data()

    assert [row["name"] for row in records] == [
        "stench",
        "drizzle",
        "speed-boost",
        "battle-armor",
    ]
    assert [call["url"] for call in calls] == [
        "https://pokeapi.test/api/v2/ability/?limit=2",
        "https://pokeapi.test/api/v2/ability/?limit=2&offset=2",
    ]


def test_fetch_rest_records_sync_fails_closed_when_max_pages_is_exhausted(monkeypatch):
    responses = deque(
        [
            _json_response("https://example.test/items?page=1", [{"id": 1}]),
            _json_response("https://example.test/items?page=2", [{"id": 2}]),
        ]
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: _FakeSyncClient(responses, calls),
    )

    with pytest.raises(RESTPaginationError, match="max_pages"):
        fetch_rest_records_sync(
            {
                "url": "https://example.test/items",
                "pagination": {
                    "mode": "page_number",
                    "page_param": "page",
                    "start_page": 1,
                    "max_pages": 2,
                },
            }
        )

    assert [call["params"]["page"] for call in calls] == [1, 2]


def test_fetch_rest_records_sync_raises_on_error_payload_with_http_200(monkeypatch):
    responses = deque(
        [
            _json_response(
                "https://example.test/items",
                {"Errors": [{"field": "version", "description": "Unsupported Version"}]},
            ),
        ]
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: _FakeSyncClient(responses, calls),
    )

    with pytest.raises(ValueError, match="Unsupported Version"):
        fetch_rest_records_sync(
            {
                "url": "https://example.test/items",
                "data_path": "results",
            }
        )


def test_fetch_rest_records_sync_rejects_invalid_data_path_before_network(monkeypatch):
    monkeypatch.setattr(
        "apps.api_server.connectors.rest_connector._sync_rest_client",
        lambda timeout: pytest.fail(f"network client should not be created for timeout={timeout}"),
    )

    with pytest.raises(ValueError, match="invalid identifier"):
        fetch_rest_records_sync(
            {
                "url": "https://example.test/items",
                "data_path": "results..invalid",
            }
        )
