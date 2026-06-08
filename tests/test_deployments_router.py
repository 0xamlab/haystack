from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from apps.api_server.routers import deployments


@pytest.mark.anyio
async def test_list_regions_falls_back_to_static_algenta_managed_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_regions() -> dict[str, list[dict[str, str]]]:
        return {
            "aws": [{"id": "us-east-1", "label": "US East (N. Virginia)", "flag": "🇺🇸"}],
            "azure": [{"id": "eastus", "label": "East US", "flag": "🇺🇸"}],
            "gcp": [{"id": "us-central1", "label": "Iowa", "flag": "🇺🇸"}],
        }

    monkeypatch.setattr(deployments, "get_available_regions", _fake_regions)

    result = await deployments.list_regions(auth={"org_id": "org-123"})  # type: ignore[arg-type]

    providers = {provider["id"]: provider for provider in result["providers"]}
    assert providers["algenta_shared"]["regions"] == deployments.REGIONS["algenta_shared"]
    assert providers["aws"]["regions"] == [
        {"id": "us-east-1", "label": "US East (N. Virginia)", "flag": "🇺🇸"}
    ]


@pytest.mark.anyio
async def test_create_deployment_uses_actor_user_id_not_api_key_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExecuteResult:
        @staticmethod
        def scalar_one_or_none() -> None:
            return None

    captured: dict[str, object] = {}

    class _FakeDB:
        async def execute(self, *_args, **_kwargs) -> _ExecuteResult:
            return _ExecuteResult()

        def add(self, deployment: deployments.Deployment) -> None:
            captured["deployment"] = deployment

        async def commit(self) -> None:
            return None

        async def refresh(self, deployment: deployments.Deployment) -> None:
            if deployment.id is None:
                deployment.id = uuid.uuid4()
            if deployment.created_at is None:
                deployment.created_at = datetime.now(UTC)
            if deployment.billing_markup_pct is None:
                deployment.billing_markup_pct = Decimal("20.0")
            if deployment.cost_usd_month_cents is None:
                deployment.cost_usd_month_cents = 0

    monkeypatch.setattr(
        asyncio,
        "create_task",
        lambda coro: (coro.close(), None)[1],
    )
    monkeypatch.setattr(deployments, "_provision_async", AsyncMock())

    auth = {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "role": "owner",
    }
    payload = deployments.DeploymentCreate(provider="aws", region="us-east-1")

    response = await deployments.create_deployment(payload, _FakeDB(), auth=auth)  # type: ignore[arg-type]

    deployment = captured["deployment"]
    assert isinstance(deployment, deployments.Deployment)
    assert deployment.requested_by_user_id == auth["user_id"]
    assert deployment.requested_by_user_id != auth["key_id"]
    assert response.deployment_id == str(deployment.id)
