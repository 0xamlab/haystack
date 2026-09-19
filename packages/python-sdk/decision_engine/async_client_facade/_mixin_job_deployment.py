# SPDX-License-Identifier: Apache-2.0

"""_AsyncJobDeploymentMixin for the AsyncDecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/async_client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_deployments import (
        DeploymentCostResult,
        DeploymentDeleteResult,
        DeploymentRegionsResult,
        DeploymentResult,
    )

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._capability_plane_surface_module()



class _AsyncJobDeploymentMixin:
    async def submit_job(
        self,
        request: dict[str, Any] | None = None,
        callback_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await _job_surface_module().submit_job(self, request, callback_url, **kwargs)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().get_job(self, job_id)

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().get_job_result(self, job_id)

    async def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
    ) -> dict[str, Any]:
        return await _job_surface_module().list_jobs(
            self,
            page=page,
            limit=limit,
            status=status,
        )

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await _job_surface_module().cancel_job(self, job_id)

    async def test_webhook_delivery(self, callback_url: str) -> dict[str, Any]:
        return await _job_surface_module().test_webhook_delivery(self, callback_url)

    async def poll_job(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        return await _job_surface_module().poll_job(self, job_id, timeout, poll_interval)

    async def list_deployment_regions(self) -> DeploymentRegionsResult:
        return await _deployment_surface_module().list_deployment_regions(self)

    async def get_deployment(self) -> DeploymentResult | None:
        return await _deployment_surface_module().get_deployment(self)

    async def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> DeploymentResult:
        return await _deployment_surface_module().create_deployment(
            self,
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    async def delete_deployment(self, deployment_id: str) -> DeploymentDeleteResult:
        return await _deployment_surface_module().delete_deployment(self, deployment_id)

    async def get_deployment_cost(self, deployment_id: str) -> DeploymentCostResult:
        return await _deployment_surface_module().get_deployment_cost(self, deployment_id)

