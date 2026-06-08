"""
tests/test_metering_flush.py — POST /v1/metering + MeteringQueue flush tests.

Coverage:
  Server (POST /v1/metering):
    1.  valid batch        → 200, accepted == len(events)
    2.  empty events       → 400 empty_events
    3.  no auth            → 401/403
    4.  billing period from event timestamp
    5.  Redis failure      → still 200 (analytics failure is non-fatal)

  Client (MeteringQueue):
    6.  empty queue        → no HTTP attempt
    7.  flush clears queue
    8.  flush captures correct batch payload
    9.  HTTP error drops events (no re-queue)
    10. total_flushed incremented

  Integration (_send_metering_batch_sync):
    11. payload structure: device_id + events list
    12. handles load_license failure gracefully
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException

from tests._asgi_client import SyncASGIClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fake_ctx():
    return {"org_id": uuid.uuid4(), "key_id": uuid.uuid4(), "plan": "pro"}


def _event(module: str = "scheduling_algo", success: bool = True, ts: float | None = None) -> dict:
    return {
        "event_type": "execute_module",
        "module": module,
        "function": "fcfs",
        "engine_used": "local",
        "latency_ms": 12.5,
        "success": success,
        "timestamp": ts or time.time(),
        "request_id": "",
    }


def _build_app(ctx: dict | None = None):
    """Build a test FastAPI app with the metering router and auth overridden."""
    from apps.api_server.middleware.auth import get_current_org
    from apps.api_server.routers import metering as _mr

    fake_ctx = ctx or _fake_ctx()
    app = FastAPI()
    app.include_router(_mr.router)
    app.dependency_overrides[get_current_org] = lambda: fake_ctx
    return app


# ── Server tests ──────────────────────────────────────────────────────────────


# 1. Valid batch
def test_metering_ingest_valid_batch():
    from apps.api_server.routers import metering as _mr

    with patch.object(_mr, "_increment_metering_counter", new=AsyncMock()):
        app = _build_app()
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/v1/metering",
                json={
                    "device_id": "dev-test-0001",
                    "events": [_event() for _ in range(5)],
                },
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 5
    assert len(data["billing_period"]) == 7  # "YYYY-MM"


# 2. Empty events list → 400
def test_metering_ingest_empty_events():
    from apps.api_server.routers import metering as _mr

    with patch.object(_mr, "_increment_metering_counter", new=AsyncMock()):
        app = _build_app()
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/v1/metering",
                json={
                    "device_id": "dev-001",
                    "events": [],
                },
            )
    assert resp.status_code == 400
    # Standalone test app has no custom exception handler — FastAPI wraps
    # HTTPException detail as {"detail": {...}}.
    body = resp.json()
    detail = body.get("detail") or body
    if isinstance(detail, dict):
        error = detail.get("error", detail)
    else:
        error = {}
    assert error.get("code") == "empty_events"


# 3. Auth dependency raises 401 → endpoint returns 401
def test_metering_ingest_no_auth():
    from apps.api_server.middleware.auth import get_current_org
    from apps.api_server.routers import metering as _mr

    def _deny():
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "No API key provided"}},
        )

    app = FastAPI()
    app.include_router(_mr.router)
    app.dependency_overrides[get_current_org] = _deny

    with SyncASGIClient(app, raise_app_exceptions=False) as client:
        resp = client.post(
            "/v1/metering",
            json={
                "device_id": "dev-001",
                "events": [_event()],
            },
        )
    assert resp.status_code == 401


# 4. Billing period derived from event timestamps
def test_metering_ingest_billing_period_from_timestamps():
    from datetime import datetime

    from apps.api_server.routers import metering as _mr

    with patch.object(_mr, "_increment_metering_counter", new=AsyncMock()):
        app = _build_app()
        now = time.time()
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/v1/metering",
                json={
                    "device_id": "dev-001",
                    "events": [_event(ts=now), _event(ts=now - 3600)],
                },
            )
    assert resp.status_code == 200
    expected = datetime.now(UTC).strftime("%Y-%m")
    assert resp.json()["billing_period"] == expected


# 5. Redis failure in _increment_metering_counter is non-fatal
def test_metering_ingest_redis_failure_still_200():
    """Verify the endpoint succeeds even when Redis is unavailable."""
    # _increment_metering_counter already suppresses all exceptions internally.
    # Simulate a Redis connection error by patching redis.asyncio.from_url.
    import redis.asyncio as aioredis

    app = _build_app()
    with patch.object(aioredis, "from_url", side_effect=ConnectionError("Redis down")):
        with SyncASGIClient(app) as client:
            resp = client.post(
                "/v1/metering",
                json={
                    "device_id": "dev-001",
                    "events": [_event()],
                },
            )
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1


# ── Client tests (MeteringQueue) ──────────────────────────────────────────────


# 6. Empty queue → _send_metering_batch_sync never called
def test_flush_empty_queue_no_http():
    from apps.runtime.metering import MeteringQueue

    q = MeteringQueue()
    assert len(q._queue) == 0

    async def _test():
        with patch.object(q, "_send_metering_batch_sync") as mock:
            await q._flush()
            mock.assert_not_called()

    _run(_test())


# 7. Queue cleared after flush
def test_flush_clears_queue():
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    q.record(UsageEvent(event_type="execute_module", module="m1"))
    q.record(UsageEvent(event_type="execute_module", module="m2"))
    assert len(q._queue) == 2

    async def _test():
        with patch.object(q, "_send_metering_batch_sync", return_value=None):
            await q._flush()

    _run(_test())
    assert len(q._queue) == 0


# 8. Flush passes correct batch to send helper
def test_flush_passes_batch_to_send():
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    q.record(UsageEvent(event_type="execute_module", module="scheduling_algo", function="fcfs"))
    q.record(UsageEvent(event_type="execute_module", module="recommender", function="cosine"))

    captured: list = []

    async def _test():
        with patch.object(q, "_send_metering_batch_sync", side_effect=lambda b: captured.extend(b)):
            await q._flush()

    _run(_test())
    assert len(captured) == 2
    assert captured[0].module == "scheduling_algo"
    assert captured[1].module == "recommender"


# 9. Send failure still clears queue (no re-queue)
def test_flush_send_failure_drops_events():
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    q.record(UsageEvent(event_type="execute_module"))

    async def _test():
        # Raise from the thread — _flush wraps asyncio.to_thread in try/except
        with patch.object(
            q, "_send_metering_batch_sync", side_effect=RuntimeError("network error")
        ):
            await q._flush()

    _run(_test())
    # Queue was already swapped out before the send attempt — never re-queued
    assert len(q._queue) == 0


# 10. total_flushed incremented by flush
def test_flush_increments_total_flushed():
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    q.record(UsageEvent(event_type="execute_module"))
    q.record(UsageEvent(event_type="execute_module"))
    q.record(UsageEvent(event_type="execute_module"))
    assert q._total_flushed == 0

    async def _test():
        with patch.object(q, "_send_metering_batch_sync", return_value=None):
            await q._flush()

    _run(_test())
    assert q._total_flushed == 3


@pytest.mark.parametrize("deployment_mode", ["self_hosted", "air_gapped"])
def test_start_background_flush_noops_for_private_profiles(
    monkeypatch: pytest.MonkeyPatch,
    deployment_mode: str,
) -> None:
    from apps.runtime.metering import MeteringQueue

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", deployment_mode)
    monkeypatch.delenv("ALGENTA_METERING_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", raising=False)

    created: list[object] = []

    class _FakeLoop:
        def create_task(self, coro):  # noqa: ANN001
            created.append(coro)
            return object()

    queue = MeteringQueue()
    queue.start_background_flush(_FakeLoop())

    assert created == []
    assert queue._flush_task is None
    assert queue._heartbeat_task is None


# ── Integration: _send_metering_batch_sync payload ────────────────────────────


# 11. Correct payload structure
def test_send_batch_sync_payload_structure():
    import urllib.request as _urllib_req

    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    batch = [
        UsageEvent(
            event_type="execute_module",
            module="scheduling_algo",
            function="fcfs",
            engine_used="local",
            latency_ms=10.0,
            success=True,
            timestamp=1700000000.0,
        )
    ]

    captured_bodies: list[dict] = []

    class _FakeResp:
        def read(self):
            return json.dumps({"accepted": 1}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    def _fake_urlopen(req, timeout=None):
        captured_bodies.append(json.loads(req.data.decode()))
        return _FakeResp()

    fake_lic = MagicMock()
    fake_lic.device_id = "device-abc-123"

    with patch.object(_urllib_req, "urlopen", _fake_urlopen):
        with patch("apps.runtime.license.load_license", return_value=fake_lic):
            q._send_metering_batch_sync(batch)

    assert len(captured_bodies) == 1
    body = captured_bodies[0]
    assert body["device_id"] == "device-abc-123"
    assert len(body["events"]) == 1
    ev = body["events"][0]
    assert ev["module"] == "scheduling_algo"
    assert ev["function"] == "fcfs"
    assert ev["latency_ms"] == 10.0
    assert ev["success"] is True
    assert ev["timestamp"] == 1700000000.0


# 12. load_license failure is swallowed — never raises
def test_send_batch_sync_license_failure_is_silent():
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    batch = [UsageEvent(event_type="execute_module", module="m1")]

    with patch("apps.runtime.license.load_license", side_effect=FileNotFoundError("no license")):
        # Must not raise
        q._send_metering_batch_sync(batch)
