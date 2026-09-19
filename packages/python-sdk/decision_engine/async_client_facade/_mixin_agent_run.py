# SPDX-License-Identifier: Apache-2.0

"""_AsyncAgentRunMixin for the AsyncDecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/async_client_facade.py during modularization.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_agent_runs import (
        AgentRunCheckpointListResponseResult,
        AgentRunCheckpointsResult,
        AgentRunEventsResult,
        AgentRunListResult,
        AgentRunMissionEventListResponseResult,
        AgentRunMissionEventsResult,
        AgentRunReplayResult,
        AgentRunResult,
        AgentRunStreamEventResult,
        AgentRunTelemetryListResult,
        AgentRunTelemetryResult,
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



class _AsyncAgentRunMixin:
    async def create_agent_run(
        self,
        *,
        task: str,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        max_steps: int = 10,
        output_format: str = "text",
        approval_mode: str = "auto",
        start_paused: bool = False,
    ) -> AgentRunResult:
        return await _agent_run_surface_module().create_agent_run(
            self,
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    async def get_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().get_agent_run(self, run_id)

    async def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> AgentRunListResult:
        return await _agent_run_surface_module().list_agent_runs(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    async def get_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunEventsResult:
        return await _agent_run_surface_module().get_agent_run_events(self, run_id, limit=limit)

    def stream_agent_run_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AsyncIterator[AgentRunStreamEventResult]:
        return _agent_run_surface_module().stream_agent_run_events(self, run_id, limit=limit)

    async def resume_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().resume_agent_run(self, run_id)

    async def cancel_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().cancel_agent_run(self, run_id)

    async def approve_agent_run(self, run_id: str) -> AgentRunResult:
        return await _agent_run_surface_module().approve_agent_run(self, run_id)

    async def list_agent_run_checkpoints(self, run_id: str) -> AgentRunCheckpointsResult:
        return await _agent_run_surface_module().list_agent_run_checkpoints(self, run_id)

    async def query_agent_run_checkpoints(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AgentRunCheckpointListResponseResult:
        return await _agent_run_surface_module().query_agent_run_checkpoints(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )

    async def list_agent_run_mission_events(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunMissionEventsResult:
        return await _agent_run_surface_module().list_agent_run_mission_events(
            self,
            run_id,
            limit=limit,
        )

    async def query_agent_run_mission_events(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        event_type: str | None = None,
    ) -> AgentRunMissionEventListResponseResult:
        return await _agent_run_surface_module().query_agent_run_mission_events(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        )

    async def list_agent_run_telemetry(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> AgentRunTelemetryResult:
        return await _agent_run_surface_module().list_agent_run_telemetry(
            self,
            run_id,
            limit=limit,
        )

    async def query_agent_run_telemetry(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
        run_id: str | None = None,
        telemetry_kind: str | None = None,
        module_name: str | None = None,
    ) -> AgentRunTelemetryListResult:
        return await _agent_run_surface_module().query_agent_run_telemetry(
            self,
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        )

    async def replay_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunReplayResult:
        return await _agent_run_surface_module().replay_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

    async def fork_agent_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str | None = None,
    ) -> AgentRunResult:
        return await _agent_run_surface_module().fork_agent_run(
            self,
            run_id,
            checkpoint_id=checkpoint_id,
        )

