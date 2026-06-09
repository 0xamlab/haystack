"""Tests for test_connector_preview_api: inline_connector.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-4/tests/test_connector_preview_api.py during modularization.
"""
from __future__ import annotations

from tests._test_connector_preview_api_helpers import *  # noqa: F401,F403


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


