from __future__ import annotations

import pytest

from apps.api_server.services.cost_tracker_service import estimate_monthly_cost


@pytest.mark.anyio
async def test_estimate_monthly_cost_uses_markup_and_provider_defaults() -> None:
    result = await estimate_monthly_cost(
        provider="aws",
        region="us-east-1",
        config={"instance_size": "medium", "billing_markup_pct": 25.0},
    )

    assert result["estimated_base_cost_usd_month"] == 350.0
    assert result["markup_pct"] == 25.0
    assert result["estimated_billable_usd_month"] == 437.5


@pytest.mark.anyio
async def test_estimate_monthly_cost_defaults_unknown_provider_to_aws_small() -> None:
    result = await estimate_monthly_cost(
        provider="unknown-provider",
        region="test-region",
        config={},
    )

    assert result["estimated_base_cost_usd_month"] == 150.0
    assert result["estimated_billable_usd_month"] == 180.0
