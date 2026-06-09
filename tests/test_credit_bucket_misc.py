"""Tests for test_credit_bucket: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_store_initialize_sync_creates_file():
    store = _tmp_store()
    store.initialize_sync(credits_granted=5000, billing_period="2026-04")
    assert store._path.exists()
    state = run(store.get_state())
    assert state.credits_remaining == 5000
    assert state.credits_total == 5000


def test_store_apply_refresh_adds_carry():
    """Remaining credits carry over on refresh."""
    store = _tmp_store()
    store.initialize_sync(credits_granted=100, billing_period="2026-04")
    # Drain to 30
    from apps.runtime.credits import CreditState

    store._write(CreditState(**_make_state(remaining=30, total=100)))
    run(
        store.apply_refresh(
            credits_granted=10_000,
            expires_at=time.time() + 3600,
            billing_period="2026-04",
        )
    )
    state = run(store.get_state())
    assert state.credits_remaining == 10_030  # 30 carry + 10k granted
    assert state.credits_total == 10_000


def test_store_atomic_write_no_partial_read():
    """Write via tmp + rename — file never in partial state."""
    store = _tmp_store()
    store.initialize_sync(credits_granted=1000, billing_period="2026-04")
    # Simulate concurrent decrement — second read should be consistent
    state1 = run(store.get_state())
    run(store.decrement())
    state2 = run(store.get_state())
    assert state2.credits_remaining == state1.credits_remaining - 1


def test_background_refresh_offline_failure_is_nonfatal(monkeypatch):
    """Network failure during refresh must not raise or corrupt local credits."""
    import urllib.error

    import apps.runtime.credits as cmod

    monkeypatch.setenv("DE_API_KEY", "de_live_offline")
    monkeypatch.setenv("ALGENTA_CONTROL_PLANE_URL", "https://offline.invalid")

    store = _tmp_store()
    store.initialize_sync(credits_granted=5, billing_period="2026-04")
    old_store = cmod._store
    cmod._store = store
    try:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            run(cmod._background_refresh())

        state = run(store.get_state())
        assert state is not None
        assert state.credits_remaining == 5
        assert cmod._store._refreshing is False
    finally:
        cmod._store = old_store
        monkeypatch.delenv("DE_API_KEY", raising=False)
        monkeypatch.delenv("ALGENTA_CONTROL_PLANE_URL", raising=False)


def test_executor_blocks_when_no_credits():
    """Executor returns error dict when credits exhausted."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    from apps.runtime.executor import Executor

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=0)))
    old_store = cmod._store
    cmod._store = store
    try:
        ex = Executor()
        result = run(ex.execute_module("monte_carlo", "run", {}))
        assert result["success"] is False
        assert "quota_exhausted" in result["error"]
        assert result["engine_used"] == "blocked"
    finally:
        cmod._store = old_store


def test_executor_decrements_on_success():
    """A successful execution decrements the credit counter."""
    import apps.runtime.credits as cmod
    from apps.runtime.executor import Executor

    store = _tmp_store()
    store.initialize_sync(100, "2026-04")
    old_store = cmod._store
    cmod._store = store
    try:
        ex = Executor()
        # Mock _mojo_available so it uses python fallback
        with patch.object(ex, "_mojo_available", return_value=False):
            with patch(
                "apps.runtime.executor._python_fallback", return_value={"result": {"value": 42}}
            ):
                run(ex.execute_module("monte_carlo", "run", {}))
        state = run(store.get_state())
        assert state.credits_remaining == 99
    finally:
        cmod._store = old_store


def test_executor_credit_error_has_zero_latency():
    """Blocked executions report 0ms latency (didn't reach engine)."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    from apps.runtime.executor import Executor

    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=0)))
    old_store = cmod._store
    cmod._store = store
    try:
        ex = Executor()
        result = run(ex.execute_module("recommender", "cosine_sim_users", []))
        assert result["latency_ms"] == 0.0
    finally:
        cmod._store = old_store


@pytest.mark.anyio
async def test_get_issued_falls_back_to_db_sum_when_redis_is_unavailable(monkeypatch):
    import redis.asyncio as aioredis

    from apps.api_server.routers import credits

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    mock_db.execute.return_value = mock_result

    def _broken_from_url(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(aioredis, "from_url", _broken_from_url)

    issued = await credits._get_issued(
        "credits_issued:test-org:2026-04",
        uuid.uuid4(),
        "2026-04",
        mock_db,
    )

    assert issued == 42
    mock_db.execute.assert_awaited_once()


def test_register_response_model_has_credit_fields():
    """RegisterResponse schema includes credit fields."""

    from apps.api_server.routers.devices import RegisterResponse

    fields = RegisterResponse.model_fields
    assert "credits_granted" in fields
    assert "credits_expires_at" in fields
    assert "credits_billing_period" in fields
    assert "server_time" in fields


def test_register_response_credit_defaults_zero():
    """Credit fields default to 0 so old clients don't break."""
    from apps.api_server.routers.devices import RegisterResponse

    r = RegisterResponse(
        license_token="tok",
        device_id="dev",
        plan="pro",
        device_limit=5,
        device_count=1,
        api_key_prefix="de_live_",
        message="ok",
    )
    assert r.credits_granted == 0
    assert r.credits_expires_at == 0.0
    assert r.credits_billing_period == ""
    assert r.server_time == 0.0


def test_credit_refresh_response_model_has_server_time():
    from apps.api_server.routers.credits import CreditRefreshResponse

    assert "server_time" in CreditRefreshResponse.model_fields


def test_heartbeat_request_usage_dict_default():
    from apps.api_server.routers.devices import HeartbeatRequest

    req = HeartbeatRequest(device_id="a" * 20)
    assert isinstance(req.usage, dict)
    assert len(req.usage) == 0


def test_heartbeat_usage_executions_key():
    """Usage dict can carry executions_since_last_heartbeat."""
    from apps.api_server.routers.devices import HeartbeatRequest

    req = HeartbeatRequest(
        device_id="a" * 20,
        usage={"executions_since_last_heartbeat": 1234, "modules_used": ["monte_carlo"]},
    )
    assert req.usage.get("executions_since_last_heartbeat") == 1234


def test_metering_executions_since_last_heartbeat():
    """Delta counter starts at 0 and increments with enqueued events."""
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    assert q.executions_since_last_heartbeat() == 0
    q.record(UsageEvent(event_type="execute_module", module="monte_carlo"))
    q.record(UsageEvent(event_type="execute_module", module="recommender"))
    assert q.executions_since_last_heartbeat() == 2


def test_metering_delta_advances_baseline():
    """After marking the baseline, delta resets."""
    from apps.runtime.metering import MeteringQueue, UsageEvent

    q = MeteringQueue()
    q.record(UsageEvent(event_type="execute_module"))
    q.record(UsageEvent(event_type="execute_module"))
    q._executions_at_last_heartbeat = q._total_enqueued  # simulate confirmed heartbeat
    assert q.executions_since_last_heartbeat() == 0
    q.record(UsageEvent(event_type="execute_module"))
    assert q.executions_since_last_heartbeat() == 1


def test_end_to_end_drain_then_block(monkeypatch: pytest.MonkeyPatch):
    """
    Full local flow: seed 3 credits → execute 3 times → 4th call blocked.
    """
    import apps.runtime.credits as cmod

    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    store = _tmp_store()
    store.initialize_sync(credits_granted=3, billing_period="2026-04")
    old_store = cmod._store
    cmod._store = store

    async def _noop_refresh() -> None:
        return None

    try:
        with patch.object(cmod, "_background_refresh", _noop_refresh):
            assert run(cmod.consume_credit()) is True  # 2 remaining
            assert run(cmod.consume_credit()) is True  # 1 remaining
            assert run(cmod.consume_credit()) is True  # 0 remaining
            assert run(cmod.consume_credit()) is False  # blocked
    finally:
        cmod._store = old_store


def test_end_to_end_refresh_restores_execution(monkeypatch: pytest.MonkeyPatch):
    """
    After exhaustion, applying a refresh batch re-enables execution.
    """
    import apps.runtime.credits as cmod

    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)

    store = _tmp_store()
    store.initialize_sync(credits_granted=1, billing_period="2026-04")
    old_store = cmod._store
    cmod._store = store

    async def _noop_refresh() -> None:
        return None

    try:
        with patch.object(cmod, "_background_refresh", _noop_refresh):
            run(cmod.consume_credit())  # drain to 0
            assert run(cmod.consume_credit()) is False  # blocked

        # Simulate a successful refresh
        run(
            store.apply_refresh(
                credits_granted=10_000,
                expires_at=time.time() + 3600,
                billing_period="2026-04",
            )
        )

        assert run(cmod.consume_credit()) is True  # unblocked
    finally:
        cmod._store = old_store


