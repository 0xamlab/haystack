"""Tests for test_connector_preview_api: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-4/tests/test_connector_preview_api.py during modularization.
"""
from __future__ import annotations

from tests._test_connector_preview_api_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_get_connector_route_returns_visible_connector(
    monkeypatch: pytest.MonkeyPatch,
    connector_preview_client,
) -> None:
    async def _fake_get_visible_connector(_db, _connector_id, _auth):
        return SimpleNamespace(
            id="conn_123",
            org_id="org_a",
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


