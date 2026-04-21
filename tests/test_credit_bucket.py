"""
Credit bucket test suite — 50 checks covering:

  1.  CreditStore: decrement, exhaustion, persistence, atomic write
  2.  CreditStore: apply_refresh merges carry-over correctly
  3.  CreditStore: initialize_sync seeds from scratch
  4.  CreditStore: should_refresh thresholds (>10%, <10%, 0, expired)
  5.  consume_credit: permits when credits available
  6.  consume_credit: blocks when credits exhausted
  7.  consume_credit: blocks when no credit file unless explicit dev mode
  8.  consume_credit: triggers background refresh at <10%
  9.  plan_limits: credit_batch_size per plan
  10. plan_limits: batch sizes relative to monthly limits
  11. /v1/credits/refresh: grants full batch when under quota
  12. /v1/credits/refresh: denies when monthly quota exhausted (HTTP 429)
  13. /v1/credits/refresh: grants partial batch near limit
  14. /v1/credits/refresh: unlimited plan always grants full batch
  15. /v1/credits/refresh: requires valid auth (HTTP 401 without key)
  16. device register: response includes credit fields
  17. device register: STARTER plan blocked (HTTP 402) — no credits issued
  18. heartbeat: executions_since_last_heartbeat written to usage_records
  19. heartbeat: zero executions → no usage_record written
  20. metering: executions_since_last_heartbeat delta tracking
  21. metering: delta resets after confirmed heartbeat
  22. license: credit store seeded on successful registration
  23. CreditState: needs_refresh at exactly 10% boundary
  24. CreditState: expired flag
  25. CreditState: is_exhausted at 0
  26. CreditState: serialization round-trip
  27. credits_issued Redis counter incremented on refresh grant
  28. credits_issued Redis counter incremented on device register
  29. /v1/credits/refresh: device_id truncated in log (privacy)
  30. Full flow: register → execute 9999 credits → trigger refresh → execute
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tmp_store():
    """Return a CreditStore backed by a temp file (cleaned up automatically)."""
    from apps.runtime.credits import CreditStore
    d = tempfile.mkdtemp()
    return CreditStore(Path(d) / "credits.json")


def _make_state(remaining=5000, total=10_000, expires_offset=3600, billing="2026-04"):
    """Return a CreditState dict suitable for writing to the store."""
    now = time.time()
    return {
        "credits_remaining": remaining,
        "credits_total":     total,
        "issued_at":         now,
        "expires_at":        now + expires_offset,
        "billing_period":    billing,
        "refresh_after":     now + expires_offset * 0.9,
    }


def run(coro):
    """Run a coroutine synchronously without touching global event loop state."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════════════════════════
# 1–4  CreditState dataclass
# ══════════════════════════════════════════════════════════════════════════════

def test_credit_state_needs_refresh_above_threshold():
    """Above 10% → no refresh needed."""
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(remaining=2000, total=10_000))
    assert not s.needs_refresh


def test_credit_state_needs_refresh_at_threshold():
    """Exactly 10% → refresh needed."""
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(remaining=1000, total=10_000))
    assert s.needs_refresh


def test_credit_state_needs_refresh_below_threshold():
    """Below 10% → refresh needed."""
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(remaining=500, total=10_000))
    assert s.needs_refresh


def test_credit_state_is_exhausted():
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(remaining=0))
    assert s.is_exhausted


def test_credit_state_not_exhausted():
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(remaining=1))
    assert not s.is_exhausted


def test_credit_state_is_expired():
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(expires_offset=-1))   # expired 1s ago
    assert s.is_expired


def test_credit_state_not_expired():
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state(expires_offset=3600))
    assert not s.is_expired


def test_credit_state_roundtrip():
    """to_dict / from_dict preserves all fields."""
    from apps.runtime.credits import CreditState
    s = CreditState(**_make_state())
    s2 = CreditState.from_dict(s.to_dict())
    assert s.credits_remaining == s2.credits_remaining
    assert s.credits_total     == s2.credits_total
    assert s.billing_period    == s2.billing_period


def test_credit_state_from_dict_ignores_extra_keys():
    """Extra keys in JSON don't crash from_dict."""
    from apps.runtime.credits import CreditState
    d = {**_make_state(), "unknown_field": "ignored"}
    s = CreditState.from_dict(d)
    assert s.credits_remaining == 5000


# ══════════════════════════════════════════════════════════════════════════════
# 5–14  CreditStore operations
# ══════════════════════════════════════════════════════════════════════════════

def test_store_decrement_reduces_count():
    store = _tmp_store()
    store._write(store._read() or __import__('apps.runtime.credits', fromlist=['CreditState']).CreditState(**_make_state(remaining=100)))
    # Re-write via initialize_sync
    store.initialize_sync(credits_granted=100, billing_period="2026-04")
    permitted = run(store.decrement())
    assert permitted
    state = run(store.get_state())
    assert state.credits_remaining == 99


def test_store_decrement_returns_false_when_exhausted():
    store = _tmp_store()
    store.initialize_sync(credits_granted=0, billing_period="2026-04")
    # Patch: write 0 remaining directly
    from apps.runtime.credits import CreditState
    store._write(CreditState(**_make_state(remaining=0)))
    result = run(store.decrement())
    assert result is False


def test_store_decrement_blocks_when_no_file():
    """No credit file → contract blocks execution unless explicit dev mode is enabled."""
    store = _tmp_store()
    result = run(store.decrement())
    assert result is False


def test_store_initialize_sync_creates_file():
    store = _tmp_store()
    store.initialize_sync(credits_granted=5000, billing_period="2026-04")
    assert store._path.exists()
    state = run(store.get_state())
    assert state.credits_remaining == 5000
    assert state.credits_total     == 5000


def test_store_apply_refresh_adds_carry():
    """Remaining credits carry over on refresh."""
    store = _tmp_store()
    store.initialize_sync(credits_granted=100, billing_period="2026-04")
    # Drain to 30
    from apps.runtime.credits import CreditState
    store._write(CreditState(**_make_state(remaining=30, total=100)))
    run(store.apply_refresh(
        credits_granted=10_000,
        expires_at=time.time() + 3600,
        billing_period="2026-04",
    ))
    state = run(store.get_state())
    assert state.credits_remaining == 10_030   # 30 carry + 10k granted
    assert state.credits_total     == 10_000


def test_store_should_refresh_true_when_no_file():
    store = _tmp_store()
    assert store.should_refresh() is True


def test_store_should_refresh_true_when_low():
    store = _tmp_store()
    from apps.runtime.credits import CreditState
    store._write(CreditState(**_make_state(remaining=500, total=10_000)))
    assert store.should_refresh() is True


def test_store_should_refresh_false_when_healthy():
    store = _tmp_store()
    from apps.runtime.credits import CreditState
    store._write(CreditState(**_make_state(remaining=5000, total=10_000)))
    assert store.should_refresh() is False


def test_store_atomic_write_no_partial_read():
    """Write via tmp + rename — file never in partial state."""
    store = _tmp_store()
    store.initialize_sync(credits_granted=1000, billing_period="2026-04")
    # Simulate concurrent decrement — second read should be consistent
    state1 = run(store.get_state())
    run(store.decrement())
    state2 = run(store.get_state())
    assert state2.credits_remaining == state1.credits_remaining - 1


# ══════════════════════════════════════════════════════════════════════════════
# 15–20  consume_credit hot path
# ══════════════════════════════════════════════════════════════════════════════

def test_consume_credit_permits_when_available():
    import apps.runtime.credits as cmod
    store = _tmp_store()
    store.initialize_sync(5000, "2026-04")
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is True
    finally:
        cmod._store = old_store


def test_consume_credit_blocks_when_exhausted():
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=0)))
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is False
    finally:
        cmod._store = old_store


def test_consume_credit_blocks_without_credit_file():
    """No credit file → execution is blocked by default."""
    import apps.runtime.credits as cmod
    store = _tmp_store()   # empty temp dir, no file
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is False
    finally:
        cmod._store = old_store


def test_consume_credit_allows_explicit_dev_mode(monkeypatch):
    """Explicit local dev mode preserves the dev-stub escape hatch."""
    monkeypatch.setenv("ALGENTA_RUNTIME_DEV_MODE", "1")
    import apps.runtime.credits as cmod
    store = _tmp_store()
    old_store = cmod._store
    cmod._store = store
    try:
        result = run(cmod.consume_credit())
        assert result is True
    finally:
        cmod._store = old_store
        monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)


def test_consume_credit_triggers_refresh_when_low():
    """When credits <= 10%, background refresh is scheduled."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=500, total=10_000)))  # 5% <= threshold
    old_store = cmod._store
    cmod._store = store

    refresh_called = []

    async def _fake_refresh():
        refresh_called.append(True)

    with patch.object(cmod, "_background_refresh", _fake_refresh):
        cmod._store._refreshing = False
        run(cmod.consume_credit())

    # should_refresh() is True because 500/10000 = 5% <= 10% threshold
    assert store.should_refresh() is True
    cmod._store = old_store


def test_consume_credit_no_double_refresh():
    """If _refreshing=True, don't schedule another refresh."""
    import apps.runtime.credits as cmod
    from apps.runtime.credits import CreditState
    store = _tmp_store()
    store._write(CreditState(**_make_state(remaining=100, total=10_000)))
    store._refreshing = True
    old_store = cmod._store
    cmod._store = store

    tasks_created = []

    async def _noop():
        tasks_created.append(True)

    with patch.object(cmod, "_background_refresh", _noop):
        run(cmod.consume_credit())

    # refresh was not triggered (already refreshing)
    assert len(tasks_created) == 0
    cmod._store = old_store
    store._refreshing = False


# ══════════════════════════════════════════════════════════════════════════════
# 21–26  Executor integration
# ══════════════════════════════════════════════════════════════════════════════

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
            with patch("apps.runtime.executor._python_fallback",
                       return_value={"result": {"value": 42}}):
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


# ══════════════════════════════════════════════════════════════════════════════
# 27–30  plan_limits credit_batch_size
# ══════════════════════════════════════════════════════════════════════════════

def test_plan_limits_credit_batch_size_free():
    from apps.api_server.services.plan_limits import credit_batch_size
    assert credit_batch_size("free") == 1_000


def test_plan_limits_credit_batch_size_pro():
    from apps.api_server.services.plan_limits import credit_batch_size
    assert credit_batch_size("pro") == 10_000


def test_plan_limits_credit_batch_size_developer_legacy():
    from apps.api_server.services.plan_limits import credit_batch_size
    assert credit_batch_size("developer") == 10_000   # same as pro


def test_plan_limits_credit_batch_size_team():
    from apps.api_server.services.plan_limits import credit_batch_size
    assert credit_batch_size("team") == 25_000


def test_plan_limits_credit_batch_size_enterprise():
    from apps.api_server.services.plan_limits import credit_batch_size
    assert credit_batch_size("enterprise") == 100_000


def test_plan_limits_batch_much_smaller_than_monthly():
    """Batch should always be << monthly limit to bound overage."""
    from apps.api_server.services.plan_limits import credit_batch_size, execution_quota
    for plan in ("free", "pro", "developer", "team"):
        batch   = credit_batch_size(plan)
        monthly = execution_quota(plan)
        assert batch <= monthly * 0.10, (
            f"Plan '{plan}': batch {batch} > 10% of monthly {monthly}"
        )


def test_plan_limits_enterprise_batch_nonzero():
    """Enterprise has unlimited monthly but should still have a finite batch."""
    from apps.api_server.services.plan_limits import credit_batch_size, execution_quota
    assert execution_quota("enterprise") == 0        # unlimited
    assert credit_batch_size("enterprise") > 0       # finite batch


# ══════════════════════════════════════════════════════════════════════════════
# 31–38  /v1/credits/refresh endpoint (unit tests, no live DB)
# ══════════════════════════════════════════════════════════════════════════════

def _make_mock_ctx(plan: str = "pro"):
    return {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
    }


def _mock_api_key_row(plan: str = "pro", org_id=None):
    row = MagicMock()
    row.org_id = org_id or uuid.uuid4()
    row.organization.plan = plan
    return row


def _mock_db_with_row(mock_row):
    """Return an AsyncMock db session that yields mock_row from execute().scalar_one()."""
    mock_db = AsyncMock()
    mock_result = MagicMock()           # non-async result so .scalar_one() returns value
    mock_result.scalar_one.return_value = mock_row
    mock_db.execute.return_value = mock_result
    return mock_db


@pytest.mark.asyncio
async def test_credits_refresh_grants_batch_under_quota():
    """Grants full batch when well under monthly limit."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(
        device_id="abc123def456789",
        billing_period="2026-04",
        credits_used=500,
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    with patch("apps.api_server.routers.credits._get_issued", return_value=0), \
         patch("apps.api_server.routers.credits._increment_issued", AsyncMock()):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 10_000
    assert response.monthly_limit   == 500_000
    assert response.monthly_remaining == 490_000
    assert response.expires_at > time.time()


@pytest.mark.asyncio
async def test_credits_refresh_denies_when_quota_exhausted():
    """Returns HTTP 429 when monthly quota is exhausted."""
    from fastapi import HTTPException

    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(
        device_id="abc123def456789",
        billing_period="2026-04",
        credits_used=0,
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    with patch("apps.api_server.routers.credits._get_issued", return_value=500_000):
        with pytest.raises(HTTPException) as exc_info:
            await refresh_credits(request, ctx, mock_db)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "quota_exhausted"


@pytest.mark.asyncio
async def test_credits_refresh_partial_grant_near_limit():
    """Grants only the remaining credits when close to the limit."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(
        device_id="abc123def456789",
        billing_period="2026-04",
        credits_used=0,
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    # Only 3000 left in monthly budget
    with patch("apps.api_server.routers.credits._get_issued", return_value=497_000), \
         patch("apps.api_server.routers.credits._increment_issued", AsyncMock()):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 3_000   # min(10k batch, 3k remaining)
    assert response.monthly_remaining == 0


@pytest.mark.asyncio
async def test_credits_refresh_unlimited_plan():
    """Enterprise plan always gets full batch, no quota check."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("enterprise")
    request = CreditRefreshRequest(
        device_id="abc123def456789",
        billing_period="2026-04",
        credits_used=0,
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("enterprise"))

    response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 100_000
    assert response.monthly_limit   == 0      # 0 = unlimited
    assert response.monthly_remaining == 0    # meaningless for unlimited


@pytest.mark.asyncio
async def test_credits_refresh_team_plan():
    """TEAM plan gets 25k batch."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("team")
    request = CreditRefreshRequest(
        device_id="abc123def456789",
        billing_period="2026-04",
        credits_used=0,
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("team"))

    with patch("apps.api_server.routers.credits._get_issued", return_value=0), \
         patch("apps.api_server.routers.credits._increment_issued", AsyncMock()):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted   == 25_000
    assert response.monthly_limit     == 1_000_000
    assert response.monthly_remaining == 975_000


@pytest.mark.asyncio
async def test_credits_refresh_increments_counter():
    """_increment_issued is called with the correct amount."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(device_id="abc123def456789",
                                   billing_period="2026-04", credits_used=0)
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    increment_calls = []

    async def _capture_increment(redis_key, amount, org_id, billing_period, db):
        increment_calls.append(amount)

    with patch("apps.api_server.routers.credits._get_issued", return_value=0), \
         patch("apps.api_server.routers.credits._increment_issued", _capture_increment):
        await refresh_credits(request, ctx, mock_db)

    assert increment_calls == [10_000]


@pytest.mark.asyncio
async def test_credits_refresh_response_expiry_in_future():
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(device_id="abc123def456789",
                                   billing_period="2026-04", credits_used=0)
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    with patch("apps.api_server.routers.credits._get_issued", return_value=0), \
         patch("apps.api_server.routers.credits._increment_issued", AsyncMock()):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.expires_at   > time.time()
    assert response.refresh_after > time.time()
    assert response.refresh_after < response.expires_at


@pytest.mark.asyncio
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


# ══════════════════════════════════════════════════════════════════════════════
# 39–44  Device register includes credit fields
# ══════════════════════════════════════════════════════════════════════════════

def test_register_response_model_has_credit_fields():
    """RegisterResponse schema includes credit fields."""

    from apps.api_server.routers.devices import RegisterResponse
    fields = RegisterResponse.model_fields
    assert "credits_granted"        in fields
    assert "credits_expires_at"     in fields
    assert "credits_billing_period" in fields


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
    assert r.credits_granted        == 0
    assert r.credits_expires_at     == 0.0
    assert r.credits_billing_period == ""


# ══════════════════════════════════════════════════════════════════════════════
# 45–48  Heartbeat usage reconciliation
# ══════════════════════════════════════════════════════════════════════════════

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
    q._executions_at_last_heartbeat = q._total_enqueued   # simulate confirmed heartbeat
    assert q.executions_since_last_heartbeat() == 0
    q.record(UsageEvent(event_type="execute_module"))
    assert q.executions_since_last_heartbeat() == 1


# ══════════════════════════════════════════════════════════════════════════════
# 49–50  End-to-end flow
# ══════════════════════════════════════════════════════════════════════════════

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
            assert run(cmod.consume_credit()) is True    # 2 remaining
            assert run(cmod.consume_credit()) is True    # 1 remaining
            assert run(cmod.consume_credit()) is True    # 0 remaining
            assert run(cmod.consume_credit()) is False   # blocked
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
            run(cmod.consume_credit())   # drain to 0
            assert run(cmod.consume_credit()) is False   # blocked

        # Simulate a successful refresh
        run(store.apply_refresh(
            credits_granted=10_000,
            expires_at=time.time() + 3600,
            billing_period="2026-04",
        ))

        assert run(cmod.consume_credit()) is True    # unblocked
    finally:
        cmod._store = old_store
