from __future__ import annotations

import sys
import types

# Stub the optional `redis` client so test collection works in CI where
# the package isn't installed. RedisConnector imports redis lazily inside
# _connect_sync; this stub is harmless when the real package is present.
sys.modules.setdefault("redis", types.ModuleType("redis"))

import pytest  # noqa: E402

from apps.api_server.connectors.redis_connector import RedisConnector  # noqa: E402


def test_connection_url_builds_from_host_fields() -> None:
    connection_url = RedisConnector._connection_url(
        {
            "host": "redis.example.com",
            "port": 15638,
            "database": 2,
            "user": "default",
            "password": "secret",
        }
    )

    assert connection_url == "redis://default:secret@redis.example.com:15638/2"


def test_parse_connection_url_supports_rediss_defaults() -> None:
    parsed = RedisConnector._parse_connection_url("rediss://default:secret@redis.example.com/1")

    assert parsed == {
        "scheme": "rediss",
        "host": "redis.example.com",
        "port": 6380,
        "user": "default",
        "password": "secret",
        "database": 1,
    }


@pytest.mark.anyio
async def test_fetch_data_requires_explicit_keys() -> None:
    connector = RedisConnector({"url": "redis://default:secret@redis.example.com:15638/0"})

    with pytest.raises(ValueError, match="requires a non-empty 'keys' list"):
        await connector.fetch_data()


@pytest.mark.anyio
async def test_fetch_data_materializes_supported_value_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakePipeline:
        def __init__(self, client: _FakeRedisClient) -> None:  # type: ignore[name-defined]
            self._client = client
            self._operations: list[tuple[str, str]] = []

        def get(self, key: str) -> None:
            self._operations.append(("get", key))

        def type(self, key: str) -> None:
            self._operations.append(("type", key))

        def ttl(self, key: str) -> None:
            self._operations.append(("ttl", key))

        def execute(self, raise_on_error: bool = True) -> list[object]:
            responses: list[object] = []
            for op, key in self._operations:
                if op == "get":
                    try:
                        responses.append(self._client.get(key))
                    except Exception as exc:
                        if raise_on_error:
                            raise
                        responses.append(exc)
                elif op == "type":
                    responses.append(self._client.type(key))
                elif op == "ttl":
                    responses.append(self._client.ttl(key))
                else:  # pragma: no cover - defensive
                    raise AssertionError(f"Unexpected pipeline op: {op}")
            return responses

    class _FakeRedisClient:
        def __init__(self) -> None:
            self.closed = False
            self.type_calls: list[str] = []

        def close(self) -> None:
            self.closed = True

        def type(self, key: str) -> str:
            self.type_calls.append(key)
            return {
                "greeting": "string",
                "profile": "hash",
                "events": "list",
            }[key]

        def ttl(self, key: str) -> int:
            return {"greeting": 30, "profile": -1, "events": 120}[key]

        def get(self, key: str) -> str:
            if key != "greeting":
                raise TypeError("WRONGTYPE")
            return '{"message":"hello"}'

        def hgetall(self, key: str) -> dict[str, str]:
            assert key == "profile"
            return {"user_id": "42", "status": "active"}

        def llen(self, key: str) -> int:
            assert key == "events"
            return 3

        def lrange(self, key: str, _start: int, _end: int) -> list[str]:
            assert key == "events"
            return ["created", "processed"]

        def pipeline(self, transaction: bool = False) -> _FakePipeline:
            assert transaction is False
            return _FakePipeline(self)

    fake_client = _FakeRedisClient()
    RedisConnector._clear_client_cache()
    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(lambda _connection_url: fake_client),
    )

    connector = RedisConnector(
        {
            "url": "redis://default:secret@redis.example.com:15638/0",
            "keys": ["greeting", "profile", "events"],
            "value_max_items": 2,
        }
    )

    rows = await connector.fetch_data()

    assert rows == [
        {
            "key": "greeting",
            "value_type": "string",
            "ttl_seconds": 30,
            "exists": True,
            "item_count": 1,
            "truncated": False,
            "value_text": None,
            "value_json": '{"message":"hello"}',
        },
        {
            "key": "profile",
            "value_type": "hash",
            "ttl_seconds": -1,
            "exists": True,
            "item_count": 2,
            "truncated": False,
            "value_text": None,
            "value_json": '{"status":"active","user_id":"42"}',
        },
        {
            "key": "events",
            "value_type": "list",
            "ttl_seconds": 120,
            "exists": True,
            "item_count": 3,
            "truncated": True,
            "value_text": None,
            "value_json": '["created","processed"]',
        },
    ]
    assert fake_client.type_calls == ["profile", "events"]
    assert fake_client.closed is False
    RedisConnector._clear_client_cache()
    assert fake_client.closed is True


def test_browse_sync_returns_key_metadata_in_sorted_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakePipeline:
        def __init__(self, client: _FakeRedisClient) -> None:  # type: ignore[name-defined]
            self._client = client
            self._keys: list[str] = []

        def type(self, key: str) -> None:
            self._keys.append(key)

        def ttl(self, key: str) -> None:
            self._keys.append(key)

        def execute(self) -> list[object]:
            responses: list[object] = []
            for index, key in enumerate(self._keys):
                if index % 2 == 0:
                    responses.append(self._client.types[key])
                else:
                    responses.append(self._client.ttls[key])
            return responses

    class _FakeRedisClient:
        def __init__(self) -> None:
            self.closed = False
            self.types = {"alpha": "string", "beta": "hash"}
            self.ttls = {"alpha": 10, "beta": 20}

        def close(self) -> None:
            self.closed = True

        def scan(self, *, cursor: int, match: str, count: int) -> tuple[int, list[str]]:
            assert cursor == 0
            assert match == "a*"
            assert count >= 10
            return 0, ["beta", "alpha"]

        def pipeline(self, transaction: bool = False) -> _FakePipeline:
            assert transaction is False
            return _FakePipeline(self)

    fake_client = _FakeRedisClient()
    RedisConnector._clear_client_cache()
    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(lambda _connection_url: fake_client),
    )

    items = RedisConnector._browse_sync(
        "redis://default:secret@redis.example.com:15638/0",
        pattern="a*",
        limit=2,
    )

    assert items == [
        {
            "id": "alpha",
            "label": "alpha",
            "kind": "key",
            "selection": {"keys": ["alpha"]},
            "value_type": "string",
            "ttl_seconds": 10,
        },
        {
            "id": "beta",
            "label": "beta",
            "kind": "key",
            "selection": {"keys": ["beta"]},
            "value_type": "hash",
            "ttl_seconds": 20,
        },
    ]
    assert fake_client.closed is False
    RedisConnector._clear_client_cache()
    assert fake_client.closed is True


def test_browse_summary_sync_allows_clients_without_dbsize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakePipeline:
        def __init__(self, client: _FakeRedisClient) -> None:  # type: ignore[name-defined]
            self._client = client
            self._keys: list[str] = []

        def type(self, key: str) -> None:
            self._keys.append(key)

        def ttl(self, key: str) -> None:
            self._keys.append(key)

        def execute(self) -> list[object]:
            responses: list[object] = []
            for index, key in enumerate(self._keys):
                if index % 2 == 0:
                    responses.append(self._client.types[key])
                else:
                    responses.append(self._client.ttls[key])
            return responses

    class _FakeRedisClient:
        def __init__(self) -> None:
            self.types = {"alpha": "string"}
            self.ttls = {"alpha": 10}

        def close(self) -> None:
            return

        def scan(self, *, cursor: int, match: str, count: int) -> tuple[int, list[str]]:
            assert cursor == 0
            assert match == "a*"
            assert count >= 10
            return 0, ["alpha"]

        def pipeline(self, transaction: bool = False) -> _FakePipeline:
            assert transaction is False
            return _FakePipeline(self)

    fake_client = _FakeRedisClient()
    RedisConnector._clear_client_cache()
    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(lambda _connection_url: fake_client),
    )

    items, metadata = RedisConnector._browse_summary_sync(
        "redis://default:secret@redis.example.com:15638/0",
        pattern="a*",
        limit=1,
    )

    assert items == [
        {
            "id": "alpha",
            "label": "alpha",
            "kind": "key",
            "selection": {"keys": ["alpha"]},
            "value_type": "string",
            "ttl_seconds": 10,
        }
    ]
    assert metadata == {
        "keyspace_total_count": None,
        "scan_exhausted": True,
        "scan_cap": 50,
        "pattern": "a*",
        "returned_count": 1,
    }


def test_scan_keys_stops_after_bounded_headroom() -> None:
    class _FakeRedisClient:
        def __init__(self) -> None:
            self.scan_calls = 0

        def scan(self, *, cursor: int, match: str, count: int) -> tuple[int, list[str]]:
            self.scan_calls += 1
            assert match == "orders:*"
            assert count >= 10
            if self.scan_calls == 1:
                return 1, [f"orders:{idx:02d}" for idx in range(30)]
            if self.scan_calls == 2:
                return 2, [f"orders:{idx:02d}" for idx in range(30, 60)]
            return 0, [f"orders:{idx:02d}" for idx in range(60, 90)]

    client = _FakeRedisClient()

    keys = RedisConnector._scan_keys(client, pattern="orders:*", limit=5)

    assert client.scan_calls == 2
    assert keys == [f"orders:{idx:02d}" for idx in range(5)]


def test_validate_sync_reuses_cached_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRedisClient:
        def __init__(self) -> None:
            self.closed = False
            self.ping_calls = 0

        def ping(self) -> bool:
            self.ping_calls += 1
            return True

        def close(self) -> None:
            self.closed = True

    connect_calls: list[str] = []
    fake_client = _FakeRedisClient()
    RedisConnector._clear_client_cache()
    monkeypatch.setattr(
        RedisConnector,
        "_connect_sync",
        staticmethod(
            lambda connection_url: (
                connect_calls.append(connection_url),
                fake_client,
            )[1]
        ),
    )

    RedisConnector._validate_sync("redis://default:secret@redis.example.com:15638/0")
    RedisConnector._validate_sync("redis://default:secret@redis.example.com:15638/0")

    assert connect_calls == ["redis://default:secret@redis.example.com:15638/0"]
    assert fake_client.ping_calls == 2
    assert fake_client.closed is False
    RedisConnector._clear_client_cache()
    assert fake_client.closed is True
