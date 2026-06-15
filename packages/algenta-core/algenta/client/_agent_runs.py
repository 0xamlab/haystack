"""_AgentRunsMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _AgentRunsMixin:
    def create_agent_run(
        self,
        *,
        task: str,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        max_steps: int = 10,
        output_format: str = "text",
        approval_mode: str = "auto",
        start_paused: bool = False,
    ) -> Any:
        return self._sdk_client().create_agent_run(
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        )

    def get_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().get_agent_run(run_id)

    def list_agent_runs(
        self,
        *,
        page: int = 1,
        limit: int = 25,
        status: str | None = None,
        request_hash: str | None = None,
        policy_snapshot_id: str | None = None,
        schema_snapshot_id: str | None = None,
    ) -> Any:
        return self._sdk_client().list_agent_runs(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        )

    def get_agent_run_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().get_agent_run_events(run_id, limit=limit)

    def stream_agent_run_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().stream_agent_run_events(run_id, limit=limit)

    def list_agent_run_checkpoints(self, run_id: str) -> Any:
        return self._sdk_client().list_agent_run_checkpoints(run_id)

    def query_agent_run_checkpoints(
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
    ) -> Any:
        return self._sdk_client().query_agent_run_checkpoints(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )

    def list_agent_run_mission_events(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().list_agent_run_mission_events(run_id, limit=limit)

    def query_agent_run_mission_events(
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
    ) -> Any:
        return self._sdk_client().query_agent_run_mission_events(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        )

    def list_agent_run_telemetry(self, run_id: str, *, limit: int = 1000) -> Any:
        return self._sdk_client().list_agent_run_telemetry(run_id, limit=limit)

    def query_agent_run_telemetry(
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
    ) -> Any:
        return self._sdk_client().query_agent_run_telemetry(
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

    def replay_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> Any:
        return self._sdk_client().replay_agent_run(run_id, checkpoint_id=checkpoint_id)

    def fork_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> Any:
        return self._sdk_client().fork_agent_run(run_id, checkpoint_id=checkpoint_id)

    def resume_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().resume_agent_run(run_id)

    def cancel_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().cancel_agent_run(run_id)

    def approve_agent_run(self, run_id: str) -> Any:
        return self._sdk_client().approve_agent_run(run_id)

