"""Tests for test_connector_preview_api: run_distributed.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-4/tests/test_connector_preview_api.py during modularization.
"""
from __future__ import annotations

from tests._test_connector_preview_api_helpers import *  # noqa: F401,F403


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


