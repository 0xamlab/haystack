# SPDX-License-Identifier: Apache-2.0

"""_TriggerSourceMixin for the DecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_query import SourceRegistrationResult
    from decision_engine.models_triggers import (
        TriggerDeleteResult,
        TriggerFireResult,
        TriggerListResult,
        TriggerPauseResult,
        TriggerSummaryResult,
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



class _TriggerSourceMixin:
    def register_trigger(
        self,
        *,
        name: str,
        condition: dict[str, Any],
        simulation_template: dict[str, Any],
        webhook_url: str | None = None,
        execution_webhook_url: str | None = None,
        auto_execute: bool = False,
        description: str | None = None,
    ) -> TriggerSummaryResult:
        return _trigger_surface_module().register_trigger(
            self,
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        )

    def list_triggers(
        self,
        *,
        status: str = "all",
        page: int | None = None,
        limit: int | None = None,
    ) -> TriggerListResult:
        return _trigger_surface_module().list_triggers(
            self,
            status=status,
            page=page,
            limit=limit,
        )

    def fire_trigger(
        self,
        trigger_id: str,
        *,
        force: bool = False,
    ) -> TriggerFireResult:
        return _trigger_surface_module().fire_trigger(self, trigger_id, force=force)

    def pause_trigger(
        self,
        trigger_id: str,
        *,
        paused: bool = True,
    ) -> TriggerPauseResult:
        return _trigger_surface_module().pause_trigger(self, trigger_id, paused=paused)

    def delete_trigger(self, trigger_id: str) -> TriggerDeleteResult:
        return _trigger_surface_module().delete_trigger(self, trigger_id)

    def register_source(
        self,
        source: dict[str, Any] | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> SourceRegistrationResult:
        return _source_surface_module().register_source(
            self,
            source,
            description=description,
            **kwargs,
        )

    def refresh_source(self, dataset_id: str) -> SourceRegistrationResult:
        return _source_surface_module().refresh_source(self, dataset_id)

