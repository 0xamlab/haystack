"""Tests for test_credit_bucket: credits_refresh.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
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

    with (
        patch("apps.api_server.routers.credits._get_issued", return_value=0),
        patch("apps.api_server.routers.credits._increment_issued", AsyncMock()),
    ):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 10_000
    assert response.monthly_limit == 500_000
    assert response.monthly_remaining == 490_000
    assert response.expires_at > time.time()


@pytest.mark.anyio
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


@pytest.mark.anyio
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
    with (
        patch("apps.api_server.routers.credits._get_issued", return_value=497_000),
        patch("apps.api_server.routers.credits._increment_issued", AsyncMock()),
    ):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 3_000  # min(10k batch, 3k remaining)
    assert response.monthly_remaining == 0


@pytest.mark.anyio
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
    assert response.monthly_limit == 0  # 0 = unlimited
    assert response.monthly_remaining == 0  # meaningless for unlimited


@pytest.mark.anyio
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

    with (
        patch("apps.api_server.routers.credits._get_issued", return_value=0),
        patch("apps.api_server.routers.credits._increment_issued", AsyncMock()),
    ):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.credits_granted == 25_000
    assert response.monthly_limit == 1_000_000
    assert response.monthly_remaining == 975_000


@pytest.mark.anyio
async def test_credits_refresh_increments_counter():
    """_increment_issued is called with the correct amount."""
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(
        device_id="abc123def456789", billing_period="2026-04", credits_used=0
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    increment_calls = []

    async def _capture_increment(redis_key, amount, org_id, billing_period, db):
        increment_calls.append(amount)

    with (
        patch("apps.api_server.routers.credits._get_issued", return_value=0),
        patch("apps.api_server.routers.credits._increment_issued", _capture_increment),
    ):
        await refresh_credits(request, ctx, mock_db)

    assert increment_calls == [10_000]


@pytest.mark.anyio
async def test_credits_refresh_response_expiry_in_future():
    from apps.api_server.routers.credits import CreditRefreshRequest, refresh_credits

    ctx = _make_mock_ctx("pro")
    request = CreditRefreshRequest(
        device_id="abc123def456789", billing_period="2026-04", credits_used=0
    )
    mock_db = _mock_db_with_row(_mock_api_key_row("pro"))

    with (
        patch("apps.api_server.routers.credits._get_issued", return_value=0),
        patch("apps.api_server.routers.credits._increment_issued", AsyncMock()),
    ):
        response = await refresh_credits(request, ctx, mock_db)

    assert response.expires_at > time.time()
    assert response.refresh_after > time.time()
    assert response.refresh_after < response.expires_at


