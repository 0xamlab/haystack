from __future__ import annotations

from apps.api_server.connectors.neo4j_connector import Neo4jConnector


def test_connection_settings_strip_auth_from_uri_and_use_embedded_credentials() -> None:
    settings = Neo4jConnector._connection_settings(
        {
            "uri": "neo4j+s://neo4j:secret@graph.example.com:7687",
            "database": "neo4j",
        }
    )

    assert settings == {
        "uri": "neo4j+s://graph.example.com:7687",
        "username": "neo4j",
        "password": "secret",
        "database": "neo4j",
        "host": "graph.example.com",
        "port": "7687",
    }


def test_browse_sync_returns_labels_and_relationship_types(monkeypatch) -> None:
    class _FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, int]]] = []

        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run(self, query: str, parameters: dict[str, int]):
            self.calls.append((query, parameters))
            return [
                {"item_kind": "label", "item_value": "Airport"},
                {"item_kind": "label", "item_value": "Flight"},
                {"item_kind": "relationship_type", "item_value": "ROUTES_TO"},
            ]

    class _FakeDriver:
        def __init__(self) -> None:
            self.closed = False
            self.session_calls: list[dict[str, str]] = []
            self.session_obj = _FakeSession()

        def session(self, **kwargs):
            self.session_calls.append(kwargs)
            return self.session_obj

        def close(self) -> None:
            self.closed = True

    Neo4jConnector._clear_driver_cache()
    fake_driver = _FakeDriver()
    monkeypatch.setattr(
        Neo4jConnector,
        "_connect_sync",
        staticmethod(lambda settings: fake_driver),
    )
    settings = Neo4jConnector._connection_settings(
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "secret",
            "database": "neo4j",
        }
    )

    items = Neo4jConnector._browse_sync(settings, limit=3)

    assert items == [
        {
            "id": "label:Airport",
            "label": "Airport",
            "kind": "label",
            "selection": {"label": "Airport"},
        },
        {
            "id": "label:Flight",
            "label": "Flight",
            "kind": "label",
            "selection": {"label": "Flight"},
        },
        {
            "id": "relationship_type:ROUTES_TO",
            "label": "ROUTES_TO",
            "kind": "relationship_type",
            "selection": {"relationship_type": "ROUTES_TO"},
        },
    ]
    assert fake_driver.session_calls == [{"database": "neo4j"}]
    assert fake_driver.session_obj.calls == [(Neo4jConnector._BROWSE_QUERY, {"limit": 3})]
    Neo4jConnector._clear_driver_cache()
    assert fake_driver.closed is True


def test_fetch_sync_executes_query_with_parameters_and_limit(monkeypatch) -> None:
    class _FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run(self, query: str, parameters: dict[str, object]):
            self.calls.append((query, parameters))
            return [
                {"name": "JFK", "legs": 12},
                {"name": "LAX", "legs": 9},
                {"name": "ATL", "legs": 8},
            ]

    class _FakeDriver:
        def __init__(self) -> None:
            self.closed = False
            self.session_obj = _FakeSession()

        def session(self, **_kwargs):
            return self.session_obj

        def close(self) -> None:
            self.closed = True

    Neo4jConnector._clear_driver_cache()
    fake_driver = _FakeDriver()
    monkeypatch.setattr(
        Neo4jConnector,
        "_connect_sync",
        staticmethod(lambda settings: fake_driver),
    )
    settings = Neo4jConnector._connection_settings(
        {
            "uri": "neo4j+s://graph.example.com",
            "username": "neo4j",
            "password": "secret",
            "database": "neo4j",
        }
    )

    rows = Neo4jConnector._fetch_sync(
        settings,
        "MATCH (a:Airport) RETURN a.code AS name, count(*) AS legs ORDER BY legs DESC",
        {"country": "US"},
        2,
    )

    assert rows == [
        {"name": "JFK", "legs": 12},
        {"name": "LAX", "legs": 9},
    ]
    assert fake_driver.session_obj.calls == [
        (
            "MATCH (a:Airport) RETURN a.code AS name, count(*) AS legs ORDER BY legs DESC",
            {"country": "US"},
        )
    ]
    Neo4jConnector._clear_driver_cache()
    assert fake_driver.closed is True
