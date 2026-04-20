"""Unit tests for Phase 5A quota enforcement and usage recording."""
import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import apps.api_server.services.quota_service as quota_service
from apps.api_server.models.usage_record import UsageEndpoint
from apps.api_server.services.quota_service import (
    PLAN_QUOTAS,
    _current_billing_period,
    check_monthly_quota,
    check_rate_limit,
    get_monthly_usage_count,
    record_usage,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mock_db(count: int = 0) -> AsyncMock:
    """Return a mock AsyncSession that returns `count` for SELECT COUNT queries."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = count
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _mock_redis(current_count: int = 1) -> AsyncMock:
    """Return a mock Redis client for rate limit tests."""
    r = AsyncMock()
    r.incr = AsyncMock(return_value=current_count)
    r.expire = AsyncMock(return_value=True)
    return r


# ─── PLAN_QUOTAS ──────────────────────────────────────────────────────────────

class TestPlanQuotas:
    def test_free_plan_exists(self):
        assert "free" in PLAN_QUOTAS

    def test_developer_plan_exists(self):
        assert "developer" in PLAN_QUOTAS

    def test_pro_plan_exists(self):
        assert "pro" in PLAN_QUOTAS

    def test_enterprise_plan_exists(self):
        assert "enterprise" in PLAN_QUOTAS

    def test_free_quota_500(self):
        assert PLAN_QUOTAS["free"]["simulations_month"] == 500

    def test_developer_quota_10000(self):
        assert PLAN_QUOTAS["developer"]["simulations_month"] == 10_000

    def test_pro_quota_100000(self):
        assert PLAN_QUOTAS["pro"]["simulations_month"] == 100_000

    def test_enterprise_quota_unlimited(self):
        # 0 = unlimited
        assert PLAN_QUOTAS["enterprise"]["simulations_month"] == 0

    def test_free_rate_limit_60(self):
        assert PLAN_QUOTAS["free"]["rate_per_minute"] == 60

    def test_developer_rate_limit_300(self):
        assert PLAN_QUOTAS["developer"]["rate_per_minute"] == 300

    def test_free_no_async_jobs(self):
        assert PLAN_QUOTAS["free"]["async_jobs"] is False

    def test_developer_has_async_jobs(self):
        assert PLAN_QUOTAS["developer"]["async_jobs"] is True

    def test_free_no_webhooks(self):
        assert PLAN_QUOTAS["free"]["webhooks"] is False

    def test_enterprise_has_webhooks(self):
        assert PLAN_QUOTAS["enterprise"]["webhooks"] is True


# ─── _current_billing_period ──────────────────────────────────────────────────

class TestCurrentBillingPeriod:
    def test_returns_yyyy_mm_format(self):
        period = _current_billing_period()
        assert len(period) == 7
        assert period[4] == "-"
        year, month = period.split("-")
        assert year.isdigit() and len(year) == 4
        assert month.isdigit() and 1 <= int(month) <= 12


# ─── check_monthly_quota ──────────────────────────────────────────────────────

class TestCheckMonthlyQuota:
    @pytest.mark.asyncio
    async def test_under_limit_does_not_raise(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=100)  # 100 used out of 500 free limit
        await check_monthly_quota(org_id, "free", db)  # Should not raise

    @pytest.mark.asyncio
    async def test_at_limit_raises_429(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=500)  # exactly at free limit
        with pytest.raises(HTTPException) as exc_info:
            await check_monthly_quota(org_id, "free", db)
        assert exc_info.value.status_code == 429
        detail: dict[str, Any] = cast(dict, exc_info.value.detail)
        assert detail["error"]["code"] == "quota_exceeded"

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=600)  # over free limit
        with pytest.raises(HTTPException) as exc_info:
            await check_monthly_quota(org_id, "free", db)
        assert exc_info.value.status_code == 429  # detail access not needed here

    @pytest.mark.asyncio
    async def test_enterprise_never_raises(self):
        """Enterprise plan is unlimited — should never raise regardless of count."""
        org_id = uuid.uuid4()
        db = _mock_db(count=999_999)
        await check_monthly_quota(org_id, "enterprise", db)  # No raise

    @pytest.mark.asyncio
    async def test_developer_under_limit_ok(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=5_000)
        await check_monthly_quota(org_id, "developer", db)  # 5k < 10k limit

    @pytest.mark.asyncio
    async def test_developer_at_limit_raises(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=10_000)
        with pytest.raises(HTTPException) as exc_info:
            await check_monthly_quota(org_id, "developer", db)
        assert exc_info.value.status_code == 429
        assert "10000" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_unknown_plan_uses_free_limits(self):
        """Unknown plan should fall back to free tier limits."""
        org_id = uuid.uuid4()
        db = _mock_db(count=500)
        with pytest.raises(HTTPException):
            await check_monthly_quota(org_id, "unknown_plan", db)

    @pytest.mark.asyncio
    async def test_quota_error_includes_upgrade_url(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=500)
        with pytest.raises(HTTPException) as exc_info:
            await check_monthly_quota(org_id, "free", db)
        detail: dict[str, Any] = cast(dict, exc_info.value.detail)
        error: dict[str, Any] = detail["error"]
        assert "upgrade_url" in error

    @pytest.mark.asyncio
    async def test_quota_error_includes_used_and_limit(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=500)
        with pytest.raises(HTTPException) as exc_info:
            await check_monthly_quota(org_id, "free", db)
        detail: dict[str, Any] = cast(dict, exc_info.value.detail)
        error: dict[str, Any] = detail["error"]
        assert error["used"] == 500
        assert error["limit"] == 500


# ─── check_rate_limit ─────────────────────────────────────────────────────────

class TestCheckRateLimit:
    @pytest.mark.asyncio
    async def test_under_rate_limit_does_not_raise(self):
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=30)  # 30/60 per minute
        await check_rate_limit(org_id, "free", redis)  # Should not raise

    @pytest.mark.asyncio
    async def test_over_rate_limit_raises_429(self):
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=61)  # 61 > 60 limit for free
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(org_id, "free", redis)
        assert exc_info.value.status_code == 429
        detail: dict[str, Any] = cast(dict, exc_info.value.detail)
        assert detail["error"]["code"] == "rate_limit_exceeded"

    @pytest.mark.asyncio
    async def test_retry_after_header_included(self):
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=61)
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(org_id, "free", redis)
        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["X-RateLimit-Limit"] == "60"
        assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_pro_plan_higher_limit(self):
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=999)  # 999 < 1000 pro limit
        await check_rate_limit(org_id, "pro", redis)  # Should not raise

    @pytest.mark.asyncio
    async def test_successful_check_sets_rate_limit_state(self):
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=12)
        state = SimpleNamespace()
        await check_rate_limit(org_id, "free", redis, request_state=state)
        assert state.rate_limit_limit == 60
        assert state.rate_limit_remaining == 48

    @pytest.mark.asyncio
    async def test_redis_error_fails_open(self):
        """Redis unavailable should NOT block requests — fail open."""
        org_id = uuid.uuid4()
        redis = AsyncMock()
        redis.incr = AsyncMock(side_effect=Exception("Redis connection failed"))
        # Should NOT raise — rate limit fails open
        await check_rate_limit(org_id, "free", redis)

    @pytest.mark.asyncio
    async def test_redis_error_fails_closed_when_runtime_fallbacks_denied(self, monkeypatch):
        org_id = uuid.uuid4()
        redis = AsyncMock()
        redis.incr = AsyncMock(side_effect=Exception("Redis connection failed"))
        monkeypatch.setattr(quota_service.settings, "runtime_fallback_mode", "deny")

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(org_id, "free", redis)

        assert exc_info.value.status_code == 503
        detail: dict[str, Any] = cast(dict, exc_info.value.detail)
        assert detail["error"]["code"] == "rate_limit_backend_unavailable"
        assert exc_info.value.headers is not None
        assert exc_info.value.headers["Retry-After"] == "30"

    @pytest.mark.asyncio
    async def test_first_request_sets_ttl(self):
        """First request in a minute should set TTL on the key."""
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=1)  # First request
        await check_rate_limit(org_id, "free", redis)
        redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_request_no_ttl_reset(self):
        """Non-first requests should NOT reset TTL."""
        org_id = uuid.uuid4()
        redis = _mock_redis(current_count=5)  # Not first request
        await check_rate_limit(org_id, "free", redis)
        redis.expire.assert_not_called()


# ─── record_usage ─────────────────────────────────────────────────────────────

class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_creates_usage_record(self):
        org_id = uuid.uuid4()
        db = _mock_db()
        await record_usage(
            org_id=org_id,
            plan="free",
            endpoint=UsageEndpoint.SIMULATE,
            db=db,
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_usage_record_has_correct_billing_period(self):
        org_id = uuid.uuid4()
        db = _mock_db()
        expected_period = _current_billing_period()
        await record_usage(
            org_id=org_id,
            plan="free",
            endpoint=UsageEndpoint.SIMULATE,
            db=db,
        )
        # The record added to db should have the correct period
        added_record = db.add.call_args[0][0]
        assert added_record.billing_period == expected_period

    @pytest.mark.asyncio
    async def test_usage_record_endpoint_set(self):
        org_id = uuid.uuid4()
        db = _mock_db()
        await record_usage(
            org_id=org_id,
            plan="free",
            endpoint=UsageEndpoint.SIMULATE,
            db=db,
        )
        added = db.add.call_args[0][0]
        assert added.endpoint == UsageEndpoint.SIMULATE

    @pytest.mark.asyncio
    async def test_usage_record_scenarios_run(self):
        org_id = uuid.uuid4()
        db = _mock_db()
        await record_usage(
            org_id=org_id,
            plan="free",
            endpoint=UsageEndpoint.SIMULATE,
            db=db,
            scenarios_run=10000,
        )
        added = db.add.call_args[0][0]
        assert added.scenarios_run == 10000

    @pytest.mark.asyncio
    async def test_usage_record_billing_units(self):
        org_id = uuid.uuid4()
        db = _mock_db()
        await record_usage(
            org_id=org_id,
            plan="pro",
            endpoint=UsageEndpoint.BATCH,
            db=db,
            billing_units=5,
        )
        added = db.add.call_args[0][0]
        assert added.billing_units == 5


# ─── get_monthly_usage_count ──────────────────────────────────────────────────

class TestGetMonthlyUsageCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=42)
        count = await get_monthly_usage_count(org_id, db)
        assert count == 42

    @pytest.mark.asyncio
    async def test_zero_when_no_records(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=0)
        count = await get_monthly_usage_count(org_id, db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_custom_billing_period(self):
        org_id = uuid.uuid4()
        db = _mock_db(count=100)
        count = await get_monthly_usage_count(org_id, db, billing_period="2025-01")
        assert count == 100


# ─── UsageEndpoint enum ────────────────────────────────────────────────────────

class TestUsageEndpointEnum:
    def test_simulate_value(self):
        assert UsageEndpoint.SIMULATE.value == "simulate"

    def test_recommend_value(self):
        assert UsageEndpoint.RECOMMEND.value == "recommend"

    def test_score_value(self):
        assert UsageEndpoint.SCORE.value == "score"

    def test_batch_value(self):
        assert UsageEndpoint.BATCH.value == "batch"

    def test_compare_value(self):
        assert UsageEndpoint.COMPARE.value == "compare"

    def test_job_value(self):
        assert UsageEndpoint.JOB.value == "job"
