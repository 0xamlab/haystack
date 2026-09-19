# SPDX-License-Identifier: Apache-2.0

"""_SimulationQueryMixin for the DecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_decision_envelope import DecisionEnvelope
    from decision_engine.models_decision_plan import DecisionPlanResult
    from decision_engine.models_query import (
        ExplainResult,
        QueryBatchResult,
        QueryResult,
        QuerySqlReportResult,
        QueryWithMetadataResult,
        ResolveResult,
        VerifyResult,
    )

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._capability_plane_surface_module()



class _SimulationQueryMixin:
    def simulate(self, **kwargs: Any) -> DecisionEnvelope:
        return _simulation_surface_module().simulate(self, **kwargs)

    def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ResolveResult:
        return _query_surface_module().resolve(self, request, **kwargs)

    def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> QueryResult:
        return _query_surface_module().query(self, request, **kwargs)

    def query_with_metadata(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> QueryWithMetadataResult:
        return _query_surface_module().query_with_metadata(self, request, **kwargs)

    def query_batch(self, request: dict[str, Any]) -> QueryBatchResult:
        return _query_surface_module().query_batch(self, request)

    def query_sql_report(self, request: dict[str, Any]) -> QuerySqlReportResult:
        return _query_surface_module().query_sql_report(self, request)

    def plan_decision(self, request: dict[str, Any]) -> DecisionPlanResult:
        return _decision_plan_surface_module().plan_decision(self, request)

    def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> VerifyResult:
        return _query_surface_module().verify(self, request, **kwargs)

    def explain(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ExplainResult:
        return _query_surface_module().explain(self, request, **kwargs)

    def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        return _simulation_surface_module().recommend(self, actions, **kwargs)

    def score(
        self, request: dict[str, Any], scoring_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:
        return _simulation_surface_module().score(self, request, scoring_weights)

    def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _simulation_surface_module().batch(self, items)

    def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        return _simulation_surface_module().compare(self, scenarios, **kwargs)

