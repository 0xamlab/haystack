from __future__ import annotations

import json

from apps.api_server.connectors.elasticsearch_connector import ElasticsearchConnector


def test_connection_settings_normalize_url_and_require_api_key() -> None:
    settings = ElasticsearchConnector._connection_settings(
        {
            "url": "https://elastic.example.com:443/",
            "api_key": "secret-key",
        }
    )

    assert settings == {
        "base_url": "https://elastic.example.com:443",
        "api_key": "secret-key",
        "host": "elastic.example.com",
        "port": 443,
    }


def test_browse_sync_returns_visible_indices_only(monkeypatch) -> None:
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self) -> None:
            self.closed = False
            self.get_calls: list[tuple[str, dict[str, str]]] = []

        def close(self) -> None:
            self.closed = True

        def get(self, path: str, *, headers: dict[str, str], params: dict[str, str]):
            self.get_calls.append((path, headers, params))
            return _FakeResponse(
                [
                    {
                        "index": ".internal-hidden",
                        "health": "green",
                        "status": "open",
                        "docs.count": "1",
                        "store.size": "500b",
                    },
                    {
                        "index": "market_data_parts_aar",
                        "health": "green",
                        "status": "open",
                        "docs.count": "3542699",
                        "store.size": "1.1gb",
                    },
                ]
            )

    fake_client = _FakeClient()
    ElasticsearchConnector._clear_client_cache()
    monkeypatch.setattr(
        ElasticsearchConnector,
        "_connect_sync",
        staticmethod(lambda _settings: fake_client),
    )
    settings = ElasticsearchConnector._connection_settings(
        {
            "url": "https://elastic.example.com:443",
            "api_key": "secret-key",
        }
    )

    items = ElasticsearchConnector._browse_sync(settings, limit=5, include_hidden=False)

    assert items == [
        {
            "id": "market_data_parts_aar",
            "label": "market_data_parts_aar",
            "kind": "index",
            "selection": {"index": "market_data_parts_aar"},
            "health": "green",
            "status": "open",
            "docs_count": "3542699",
            "row_count": 3542699,
            "store_size": "1.1gb",
        }
    ]
    assert fake_client.get_calls == [
        (
            "/_cat/indices",
            {
                "Authorization": "ApiKey secret-key",
                "Accept": "application/json",
            },
            {
                "format": "json",
                "h": "index,health,status,docs.count,store.size",
            },
        )
    ]
    ElasticsearchConnector._clear_client_cache()
    assert fake_client.closed is True


def test_fetch_sync_executes_search_and_materializes_hits(monkeypatch) -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "hits": {
                    "hits": [
                        {
                            "_index": "market_data_parts_aar",
                            "_id": "doc-1",
                            "_score": 1.0,
                            "_source": {
                                "part_number": "PN-001",
                                "price": 12.5,
                            },
                        },
                        {
                            "_index": "market_data_parts_aar",
                            "_id": "doc-2",
                            "_score": 0.8,
                            "_source": {
                                "part_number": "PN-002",
                                "price": 13.0,
                            },
                        },
                    ]
                }
            }

    class _FakeClient:
        def __init__(self) -> None:
            self.closed = False
            self.post_calls: list[tuple[str, dict[str, object]]] = []

        def close(self) -> None:
            self.closed = True

        def post(self, path: str, *, headers: dict[str, str], json: dict[str, object]):
            self.post_calls.append((path, headers, json))
            return _FakeResponse()

    fake_client = _FakeClient()
    ElasticsearchConnector._clear_client_cache()
    monkeypatch.setattr(
        ElasticsearchConnector,
        "_connect_sync",
        staticmethod(lambda _settings: fake_client),
    )
    settings = ElasticsearchConnector._connection_settings(
        {
            "url": "https://elastic.example.com:443",
            "api_key": "secret-key",
        }
    )

    rows = ElasticsearchConnector._fetch_sync(
        settings,
        "market_data_parts_aar",
        {"query": {"match_all": {}}},
        2,
    )

    assert rows == [
        {
            "part_number": "PN-001",
            "price": 12.5,
            "_index": "market_data_parts_aar",
            "_id": "doc-1",
            "_score": 1.0,
        },
        {
            "part_number": "PN-002",
            "price": 13.0,
            "_index": "market_data_parts_aar",
            "_id": "doc-2",
            "_score": 0.8,
        },
    ]
    assert fake_client.post_calls == [
        (
            "/market_data_parts_aar/_search",
            {
                "Authorization": "ApiKey secret-key",
                "Accept": "application/json",
            },
            {"query": {"match_all": {}}, "size": 2},
        )
    ]
    ElasticsearchConnector._clear_client_cache()
    assert fake_client.closed is True


def test_query_body_accepts_json_string() -> None:
    body = ElasticsearchConnector._query_body(
        {
            "query": json.dumps(
                {
                    "query": {
                        "term": {
                            "vendor.keyword": "Acme",
                        }
                    }
                }
            )
        }
    )

    assert body == {"query": {"term": {"vendor.keyword": "Acme"}}}


def test_validate_sync_reuses_base_url_client_across_api_keys(monkeypatch) -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"version": {"number": "8.17.4"}}

    class _FakeClient:
        def __init__(self) -> None:
            self.closed = False
            self.get_calls: list[tuple[str, dict[str, str]]] = []

        def close(self) -> None:
            self.closed = True

        def get(self, path: str, *, headers: dict[str, str]):
            self.get_calls.append((path, headers))
            return _FakeResponse()

    ElasticsearchConnector._clear_client_cache()
    fake_client = _FakeClient()
    connect_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        ElasticsearchConnector,
        "_connect_sync",
        staticmethod(
            lambda settings: (
                connect_calls.append(dict(settings)),
                fake_client,
            )[1]
        ),
    )

    first = ElasticsearchConnector._connection_settings(
        {
            "url": "https://elastic.example.com:443",
            "api_key": "first-key",
        }
    )
    second = ElasticsearchConnector._connection_settings(
        {
            "url": "https://elastic.example.com:443",
            "api_key": "second-key",
        }
    )

    ElasticsearchConnector._validate_sync(first)
    ElasticsearchConnector._validate_sync(second)

    assert connect_calls == [
        {
            "base_url": "https://elastic.example.com:443",
            "api_key": "first-key",
            "host": "elastic.example.com",
            "port": 443,
        }
    ]
    assert fake_client.get_calls == [
        (
            "/",
            {
                "Authorization": "ApiKey first-key",
                "Accept": "application/json",
            },
        ),
        (
            "/",
            {
                "Authorization": "ApiKey second-key",
                "Accept": "application/json",
            },
        ),
    ]
    ElasticsearchConnector._clear_client_cache()
    assert fake_client.closed is True
