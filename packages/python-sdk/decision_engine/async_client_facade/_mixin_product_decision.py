# SPDX-License-Identifier: Apache-2.0

"""_AsyncProductDecisionMixin for the AsyncDecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/async_client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_decision_memory import (
        DecisionListResult,
        DecisionLogResult,
        ExecutionReceiptResult,
    )
    from decision_engine.models_products import (
        ProductAgentRunResult,
        ProductDecisionResult,
        ProductForecastResult,
        ProductOptimizeResult,
        ProductRetrieveResult,
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



class _AsyncProductDecisionMixin:
    async def product_decision(self, request: dict[str, Any]) -> ProductDecisionResult:
        return await _product_surface_module().product_decision(self, request)

    async def product_agent_run(self, request: dict[str, Any]) -> ProductAgentRunResult:
        return await _product_surface_module().product_agent_run(self, request)

    async def product_optimize(self, request: dict[str, Any]) -> ProductOptimizeResult:
        return await _product_surface_module().product_optimize(self, request)

    async def product_retrieve(self, request: dict[str, Any]) -> ProductRetrieveResult:
        return await _product_surface_module().product_retrieve(self, request)

    async def product_forecast(self, request: dict[str, Any]) -> ProductForecastResult:
        return await _product_surface_module().product_forecast(self, request)

    async def log_decision(self, request: dict[str, Any]) -> DecisionLogResult:
        return await _decision_memory_surface_module().log_decision(self, request)

    async def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> DecisionListResult:
        return await _decision_memory_surface_module().list_decisions(
            self,
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    async def get_decision(self, decision_id: str) -> DecisionLogResult:
        return await _decision_memory_surface_module().get_decision(self, decision_id)

    async def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> DecisionLogResult:
        return await _decision_memory_surface_module().record_outcome(
            self,
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        )

    async def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionReceiptResult:
        return await _decision_memory_surface_module().execute_decision(
            self,
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    async def delete_decision(self, decision_id: str) -> dict[str, Any]:
        return await _decision_memory_surface_module().delete_decision(self, decision_id)

