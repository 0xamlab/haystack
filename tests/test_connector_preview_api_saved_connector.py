"""Tests for test_connector_preview_api: saved_connector.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-4/tests/test_connector_preview_api.py during modularization.
"""
from __future__ import annotations

from tests._test_connector_preview_api_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_saved_connector_test_route_coalesces_concurrent_identical_requests(
    app,
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    fake_db = _FakeDbSession()
    connector = SimpleNamespace(
        id="conn_123",
        org_id="org_a",
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
        org_id="org_a",
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
        org_id="org_a",
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
        org_id="org_a",
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
        org_id="org_a",
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
        org_id="org_a",
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


