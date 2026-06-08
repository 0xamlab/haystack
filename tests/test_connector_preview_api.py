from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.services.connectors.preview_cache import (
    ConnectorBrowsePreviewOutcome,
    clear_inline_preview_browse_cache,
    clear_inline_preview_inflight,
    clear_inline_preview_test_cache,
    run_distributed_inline_preview_browse_once,
    run_distributed_inline_preview_test_once,
    run_inline_preview_once,
)
from apps.api_server.services.connectors.tester import ConnectorTestOutcome


class _FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[object, float | None]] = {}
        self._lock = threading.Lock()

    def _get_live_entry(self, key: str) -> tuple[object, float | None] | None:
        entry = self._values.get(key)
        if entry is None:
            return None
        _, expires_at = entry
        if expires_at is not None and expires_at <= time.time():
            self._values.pop(key, None)
            return None
        return entry

    async def incr(self, _key: str) -> int:
        with self._lock:
            entry = self._get_live_entry(_key)
            current = 0 if entry is None else int(entry[0])
            next_value = current + 1
            expires_at = None if entry is None else entry[1]
            self._values[_key] = (next_value, expires_at)
            return next_value

    async def expire(self, _key: str, _ttl: int) -> bool:
        with self._lock:
            entry = self._get_live_entry(_key)
            if entry is None:
                return False
            value, _ = entry
            self._values[_key] = (value, time.time() + _ttl)
            return True

    async def get(self, key: str) -> object | None:
        with self._lock:
            entry = self._get_live_entry(key)
            return None if entry is None else entry[0]

    async def set(
        self,
        key: str,
        value: object,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        with self._lock:
            entry = self._get_live_entry(key)
            if nx and entry is not None:
                return False
            expires_at = time.time() + ex if ex is not None else None
            self._values[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> int:
        with self._lock:
            existed = self._get_live_entry(key) is not None
            self._values.pop(key, None)
            return 1 if existed else 0

    async def eval(self, _script: str, _numkeys: int, key: str, token: str, ttl: int) -> int:
        with self._lock:
            entry = self._get_live_entry(key)
            if entry is None:
                return 0
            value, _ = entry
            if str(value) != token:
                return 0
            self._values[key] = (value, time.time() + ttl)
            return 1


class _FakeDbSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


@pytest.fixture
async def connector_preview_client(app, client):
    clear_inline_preview_test_cache()
    clear_inline_preview_browse_cache()
    clear_inline_preview_inflight()
    fake_redis = _FakeRedis()
    fake_auth: dict[str, Any] = {
        "org_id": "org_a",
        "role": "member",
        "user_id": "u1",
        "key_id": "k1",
    }
    app.dependency_overrides[get_current_org] = lambda: fake_auth
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        yield client
    finally:
        clear_inline_preview_test_cache()
        clear_inline_preview_browse_cache()
        clear_inline_preview_inflight()
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_inline_connector_test_route_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    response = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "ok",
        "latency_ms": 12,
        "status": "live",
        "error_type": None,
        "recoverable": None,
    }


@pytest.mark.anyio
async def test_get_connector_route_returns_visible_connector(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return SimpleNamespace(
            id="conn_123",
            name="Warehouse Postgres",
            description="analytics warehouse",
            connector_type=SimpleNamespace(value="postgres"),
            status=SimpleNamespace(value="live"),
            visibility="private",
            last_tested_at=None,
            error_message=None,
            created_at=datetime(2026, 5, 18, 16, 0, tzinfo=UTC),
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector",
        _fake_get_visible_connector,
    )

    response = await connector_preview_client.get(
        "/v1/connectors/00000000-0000-0000-0000-000000000123",
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "conn_123",
        "name": "Warehouse Postgres",
        "description": "analytics warehouse",
        "connector_type": "postgres",
        "status": "live",
        "visibility": "private",
        "last_tested_at": None,
        "error_message": None,
        "created_at": "2026-05-18T16:00:00Z",
    }


@pytest.mark.anyio
async def test_inline_connector_test_route_reuses_success_cache(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    second = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_inline_connector_test_route_does_not_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return ConnectorTestOutcome(
            success=False,
            message="Connection refused",
            latency_ms=12,
            status="error",
            error_type="timeout",
            recoverable=True,
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    second = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["success"] is False
    assert second.json()["success"] is False
    assert calls == 2


@pytest.mark.anyio
async def test_inline_connector_test_route_coalesces_concurrent_identical_requests(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        started.set()
        await release.wait()
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first_task = asyncio.create_task(
        connector_preview_client.post(
            "/v1/connectors/test",
            json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
        )
    )
    await started.wait()
    second_task = asyncio.create_task(
        connector_preview_client.post(
            "/v1/connectors/test",
            json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
        )
    )
    await asyncio.sleep(0.01)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_inline_connector_browse_route_returns_labels_and_discovery(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _unexpected_test(
        _connector_type: str, _config: dict[str, object]
    ) -> ConnectorTestOutcome:
        raise AssertionError("inline preview browse must not call test_connector_real_detailed")

    async def _fake_browse(
        connector_type: str,
        config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str, dict[str, object]]:
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return (
            [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "1 key available.",
            {
                "scope_noun": "keyspace",
                "returned_count": 1,
                "count_kind": "sample",
                "matching_total_count": 1,
                "scope_total_count": 25,
                "more_available": True,
                "sampling_reason": "keyspace_scan_limit",
            },
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _unexpected_test
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    response = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connector_type"] == "redis"
    assert body["total"] == 1
    assert body["labels"]["entity_noun"] == "key"
    assert body["discovery"]["scope_noun"] == "keyspace"
    assert body["discovery"]["sampling_reason"] == "keyspace_scan_limit"


@pytest.mark.anyio
async def test_inline_connector_browse_route_reuses_success_cache(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_browse(
        connector_type: str,
        config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str, dict[str, object]]:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return (
            [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "1 key available.",
            {
                "scope_noun": "keyspace",
                "returned_count": 1,
                "count_kind": "sample",
                "matching_total_count": 1,
                "scope_total_count": 25,
                "more_available": True,
            },
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    second = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_inline_connector_browse_route_does_not_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_browse(_connector_type: str, _config: dict[str, object]):
        nonlocal calls
        calls += 1
        raise TimeoutError("Connection refused")

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    second = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 409
    assert second.status_code == 409
    assert calls == 2


@pytest.mark.anyio
async def test_inline_connector_browse_route_surfaces_connector_test_failures(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _unexpected_test(
        _connector_type: str, _config: dict[str, object]
    ) -> ConnectorTestOutcome:
        raise AssertionError("inline preview browse must not call test_connector_real_detailed")

    async def _fake_browse(_connector_type: str, _config: dict[str, object]):
        raise TimeoutError("Connection refused")

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _unexpected_test
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    response = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "connector_test_failed"
    assert response.json()["error"]["details"] == {
        "status": "error",
        "error_type": "timeout",
        "recoverable": True,
    }


@pytest.mark.anyio
async def test_run_inline_preview_once_coalesces_concurrent_browse_loads() -> None:
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _load():
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {
            "items": [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "message": "1 key available.",
        }

    first_task = asyncio.create_task(
        run_inline_preview_once(
            operation="browse",
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await started.wait()
    second_task = asyncio.create_task(
        run_inline_preview_once(
            operation="browse",
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await asyncio.sleep(0.01)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert calls == 1
    assert (
        first
        == second
        == {
            "items": [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "message": "1 key available.",
        }
    )


@pytest.mark.anyio
async def test_run_inline_preview_once_shares_failures_and_clears_inflight() -> None:
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _fail():
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        raise TimeoutError("Connection refused")

    first_task = asyncio.create_task(
        run_inline_preview_once(
            operation="browse",
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_fail,
        )
    )
    await started.wait()
    second_task = asyncio.create_task(
        run_inline_preview_once(
            operation="browse",
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_fail,
        )
    )
    await asyncio.sleep(0.01)
    release.set()
    first_result, second_result = await asyncio.gather(
        first_task,
        second_task,
        return_exceptions=True,
    )

    assert calls == 1
    assert isinstance(first_result, TimeoutError)
    assert isinstance(second_result, TimeoutError)

    retry_calls = 0

    async def _success():
        nonlocal retry_calls
        retry_calls += 1
        return {"ok": True}

    recovered = await run_inline_preview_once(
        operation="browse",
        org_id="org_a",
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
        load=_success,
    )

    assert retry_calls == 1
    assert recovered == {"ok": True}


@pytest.mark.anyio
async def test_run_distributed_inline_preview_test_once_coalesces_shared_redis_requests() -> None:
    redis_client = _FakeRedis()
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _load() -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    first_task = asyncio.create_task(
        run_distributed_inline_preview_test_once(
            redis_client=redis_client,
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await started.wait()
    second_task = asyncio.create_task(
        run_distributed_inline_preview_test_once(
            redis_client=redis_client,
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await asyncio.sleep(0.01)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert calls == 1
    assert (
        first
        == second
        == ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )
    )


@pytest.mark.anyio
async def test_run_distributed_inline_preview_test_once_refreshes_lock_for_slow_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_client = _FakeRedis()
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    monkeypatch.setattr(
        "apps.api_server.services.connectors.preview_cache_distributed_state._DISTRIBUTED_INLINE_PREVIEW_LOCK_TTL_SECONDS",
        1,
    )

    async def _load() -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    first_task = asyncio.create_task(
        run_distributed_inline_preview_test_once(
            redis_client=redis_client,
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await started.wait()
    await asyncio.sleep(1.05)
    second_task = asyncio.create_task(
        run_distributed_inline_preview_test_once(
            redis_client=redis_client,
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_load,
        )
    )
    await asyncio.sleep(0.05)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert calls == 1
    assert (
        first
        == second
        == ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )
    )


@pytest.mark.anyio
async def test_run_distributed_inline_preview_browse_once_does_not_cache_failures() -> None:
    redis_client = _FakeRedis()
    calls = 0

    async def _fail() -> ConnectorBrowsePreviewOutcome:
        nonlocal calls
        calls += 1
        raise TimeoutError("Connection refused")

    with pytest.raises(TimeoutError):
        await run_distributed_inline_preview_browse_once(
            redis_client=redis_client,
            org_id="org_a",
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            load=_fail,
        )

    recovered = await run_distributed_inline_preview_browse_once(
        redis_client=redis_client,
        org_id="org_a",
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
        load=lambda: _successful_browse_outcome(),
    )

    assert calls == 1
    assert recovered == await _successful_browse_outcome()


async def _successful_browse_outcome() -> ConnectorBrowsePreviewOutcome:
    return ConnectorBrowsePreviewOutcome(
        items=[{"id": "cache:key", "label": "cache:key", "kind": "key"}],
        message="1 key available.",
        discovery={
            "scope_noun": "keyspace",
            "returned_count": 1,
            "count_kind": "sample",
        },
        labels={"entity_noun": "key", "row_noun": "value"},
    )


@pytest.mark.anyio
async def test_inline_connector_test_route_reuses_distributed_success_after_local_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    clear_inline_preview_test_cache()
    clear_inline_preview_inflight()
    second = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_inline_connector_browse_route_reuses_distributed_success_after_local_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    calls = 0

    async def _noop_rate_limit(**_kwargs):  # type: ignore[no-untyped-def]
        return None

    async def _fake_browse(
        connector_type: str,
        config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str, dict[str, object]]:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        return (
            [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "1 key available.",
            {
                "scope_noun": "keyspace",
                "returned_count": 1,
                "count_kind": "sample",
                "matching_total_count": 1,
                "scope_total_count": 25,
                "more_available": True,
            },
        )

    monkeypatch.setattr(
        "apps.api_server.routers.connectors._check_inline_preview_rate_limit", _noop_rate_limit
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )
    clear_inline_preview_browse_cache()
    clear_inline_preview_inflight()
    second = await connector_preview_client.post(
        "/v1/connectors/browse",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_inline_connector_preview_routes_surface_rate_limit_errors(
    app,
    connector_preview_client,
) -> None:
    class _RateLimitedRedis:
        async def incr(self, _key: str) -> int:
            return 21

        async def expire(self, _key: str, _ttl: int) -> bool:
            return True

    app.dependency_overrides[get_redis] = lambda: _RateLimitedRedis()

    response = await connector_preview_client.post(
        "/v1/connectors/test",
        json={"connector_type": "redis", "config": {"url": "redis://localhost:6379"}},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "inline_preview_rate_limited"
    assert response.headers["Retry-After"] == "60"
    assert response.headers["X-RateLimit-Limit"] == "20"
    assert response.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.anyio
async def test_saved_connector_test_route_coalesces_concurrent_identical_requests(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    fake_db = _FakeDbSession()
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="untested"),
        error_message=None,
        last_tested_at=None,
    )
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield fake_db

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_test(connector_type: str, config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        started.set()
        await release.wait()
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first_task = asyncio.create_task(
        connector_preview_client.post("/v1/connectors/00000000-0000-0000-0000-000000000123/test")
    )
    await started.wait()
    second_task = asyncio.create_task(
        connector_preview_client.post("/v1/connectors/00000000-0000-0000-0000-000000000123/test")
    )
    await asyncio.sleep(0.01)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1
    assert fake_db.commit_calls == 1


@pytest.mark.anyio
async def test_saved_connector_test_route_reuses_short_distributed_handoff(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    fake_db = _FakeDbSession()
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="untested"),
        error_message=None,
        last_tested_at=None,
    )
    calls = 0

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield fake_db

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_test(_connector_type: str, _config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        return ConnectorTestOutcome(
            success=True,
            message="ok",
            latency_ms=12,
            status="live",
            error_type=None,
            recoverable=None,
        )

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first = await connector_preview_client.post(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/test"
    )
    second = await connector_preview_client.post(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/test"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1
    assert fake_db.commit_calls == 1


@pytest.mark.anyio
async def test_saved_connector_test_route_does_not_cache_failures(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    fake_db = _FakeDbSession()
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="untested"),
        error_message=None,
        last_tested_at=None,
    )
    calls = 0

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield fake_db

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_test(_connector_type: str, _config: dict[str, object]) -> ConnectorTestOutcome:
        nonlocal calls
        calls += 1
        return ConnectorTestOutcome(
            success=False,
            message="Connection refused",
            latency_ms=12,
            status="error",
            error_type="timeout",
            recoverable=True,
        )

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.test_connector_real_detailed", _fake_test
    )

    first = await connector_preview_client.post(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/test"
    )
    second = await connector_preview_client.post(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/test"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 2
    assert fake_db.commit_calls == 2


@pytest.mark.anyio
async def test_saved_connector_browse_route_coalesces_concurrent_identical_requests(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="live"),
    )
    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield _FakeDbSession()

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_browse(
        connector_type: str,
        config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str, dict[str, object]]:
        nonlocal calls
        calls += 1
        assert connector_type == "redis"
        assert config == {"url": "redis://localhost:6379"}
        started.set()
        await release.wait()
        return (
            [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "1 key available.",
            {
                "scope_noun": "keyspace",
                "returned_count": 1,
                "count_kind": "sample",
            },
        )

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first_task = asyncio.create_task(
        connector_preview_client.get("/v1/connectors/00000000-0000-0000-0000-000000000123/browse")
    )
    await started.wait()
    second_task = asyncio.create_task(
        connector_preview_client.get("/v1/connectors/00000000-0000-0000-0000-000000000123/browse")
    )
    await asyncio.sleep(0.01)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_saved_connector_browse_route_reuses_short_distributed_handoff(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="live"),
    )
    calls = 0

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield _FakeDbSession()

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_browse(
        _connector_type: str,
        _config: dict[str, object],
    ) -> tuple[list[dict[str, object]], str, dict[str, object]]:
        nonlocal calls
        calls += 1
        return (
            [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "1 key available.",
            {
                "scope_noun": "keyspace",
                "returned_count": 1,
                "count_kind": "sample",
            },
        )

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first = await connector_preview_client.get(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/browse"
    )
    second = await connector_preview_client.get(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/browse"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == 1


@pytest.mark.anyio
async def test_saved_connector_browse_route_does_not_cache_failures(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    connector = SimpleNamespace(
        id="conn_123",
        connector_type=SimpleNamespace(value="redis"),
        config_json='{"url":"redis://localhost:6379"}',
        status=SimpleNamespace(value="live"),
    )
    calls = 0

    async def _fake_db_override():  # type: ignore[no-untyped-def]
        yield _FakeDbSession()

    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return connector

    async def _fake_browse(_connector_type: str, _config: dict[str, object]):
        nonlocal calls
        calls += 1
        raise TimeoutError("Connection refused")

    app.dependency_overrides[get_db] = _fake_db_override
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.get_visible_connector", _fake_get_visible_connector
    )
    monkeypatch.setattr(
        "apps.api_server.routers.connectors.browse_connector_real_detailed", _fake_browse
    )

    first = await connector_preview_client.get(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/browse"
    )
    second = await connector_preview_client.get(
        "/v1/connectors/00000000-0000-0000-0000-000000000123/browse"
    )

    assert first.status_code == 502
    assert second.status_code == 502
    assert calls == 2
