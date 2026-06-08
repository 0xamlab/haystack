"""agent_run lifecycle/events/checkpoints/telemetry runtime requests.

Extracted from packages/algenta-core/algenta/runtime_execution_surface.py during modularization.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")


from algenta.runtime_execution_surface._api_client_local import *  # noqa: F401, F403
from algenta.runtime_execution_surface._api_client_local import (
    _run_sync,
)
from algenta.runtime_execution_surface._validation import *  # noqa: F401, F403
from algenta.runtime_execution_surface._validation import (
    _validate_contract_payload,
    _build_runtime_validation_error_details,
    _validate_runtime_proof_payload,
    _validate_runtime_api_payload,
    _validate_runtime_api_mapping_payload,
    _validate_runtime_api_structured_mapping_payload,
    _validate_runtime_api_mapping_list_payload,
    _validate_runtime_api_stream,
    _validate_runtime_api_payload_list,
    _request_runtime_contract_payload,
)
from algenta.runtime_execution_surface._query_jobs_triggers import *  # noqa: F401, F403
from algenta.runtime_execution_surface._decision_repo_product_deploy import *  # noqa: F401, F403
from algenta.runtime_execution_surface._account_team_billing import *  # noqa: F401, F403
from algenta.runtime_execution_surface._llm_runtime import *  # noqa: F401, F403


def create_agent_run_runtime_request(
    runtime: Any,
    *,
    task: str,
    context: dict[str, Any] | None,
    tools: list[str] | None,
    max_steps: int,
    output_format: str,
    approval_mode: str,
    start_paused: bool,
) -> Any:
    runtime._require_api_transport("create_agent_run")
    return _validate_runtime_api_payload(
        "create_agent_run",
        runtime._client().create_agent_run(
            task=task,
            context=context,
            tools=tools,
            max_steps=max_steps,
            output_format=output_format,
            approval_mode=approval_mode,
            start_paused=start_paused,
        ),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def get_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("get_agent_run")
    return _validate_runtime_api_payload(
        "get_agent_run",
        runtime._client().get_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def list_agent_runs_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
) -> Any:
    runtime._require_api_transport("list_agent_runs")
    return _validate_runtime_api_payload(
        "list_agent_runs",
        runtime._client().list_agent_runs(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
        ),
        _runtime_model_agent_runs_module().AgentRunListOutput,
    )


def get_agent_run_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("get_agent_run_events")
    return _validate_runtime_api_payload(
        "get_agent_run_events",
        runtime._client().get_agent_run_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunEventsOutput,
    )


def list_agent_run_mission_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("list_agent_run_mission_events")
    return _validate_runtime_api_payload(
        "list_agent_run_mission_events",
        runtime._client().list_agent_run_mission_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunMissionEventsOutput,
    )


def query_agent_run_mission_events_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    event_type: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_mission_events")
    return _validate_runtime_api_payload(
        "query_agent_run_mission_events",
        runtime._client().query_agent_run_mission_events(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            event_type=event_type,
        ),
        _runtime_model_agent_runs_module().AgentRunMissionEventListResponseOutput,
    )


def stream_agent_run_events_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("stream_agent_run_events")
    return _validate_runtime_api_stream(
        "stream_agent_run_events",
        runtime._client().stream_agent_run_events(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunStreamEventOutput,
    )


def list_agent_run_checkpoints_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("list_agent_run_checkpoints")
    return _validate_runtime_api_payload(
        "list_agent_run_checkpoints",
        runtime._client().list_agent_run_checkpoints(run_id),
        _runtime_model_agent_runs_module().AgentRunCheckpointsOutput,
    )


def query_agent_run_checkpoints_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_checkpoints")
    return _validate_runtime_api_payload(
        "query_agent_run_checkpoints",
        runtime._client().query_agent_run_checkpoints(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        ),
        _runtime_model_agent_runs_module().AgentRunCheckpointListResponseOutput,
    )


def list_agent_run_telemetry_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    limit: int,
) -> Any:
    runtime._require_api_transport("list_agent_run_telemetry")
    return _validate_runtime_api_payload(
        "list_agent_run_telemetry",
        runtime._client().list_agent_run_telemetry(run_id, limit=limit),
        _runtime_model_agent_runs_module().AgentRunTelemetryOutput,
    )


def query_agent_run_telemetry_runtime_request(
    runtime: Any,
    *,
    page: int,
    limit: int,
    status: str | None,
    request_hash: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    run_id: str | None,
    telemetry_kind: str | None,
    module_name: str | None,
) -> Any:
    runtime._require_api_transport("query_agent_run_telemetry")
    return _validate_runtime_api_payload(
        "query_agent_run_telemetry",
        runtime._client().query_agent_run_telemetry(
            page=page,
            limit=limit,
            status=status,
            request_hash=request_hash,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            run_id=run_id,
            telemetry_kind=telemetry_kind,
            module_name=module_name,
        ),
        _runtime_model_agent_runs_module().AgentRunTelemetryListOutput,
    )


def replay_agent_run_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("replay_agent_run")
    return _validate_runtime_api_payload(
        "replay_agent_run",
        runtime._client().replay_agent_run(run_id, checkpoint_id=checkpoint_id),
        _runtime_model_agent_runs_module().AgentRunReplayOutput,
    )


def fork_agent_run_runtime_request(
    runtime: Any,
    run_id: str,
    *,
    checkpoint_id: str | None,
) -> Any:
    runtime._require_api_transport("fork_agent_run")
    return _validate_runtime_api_payload(
        "fork_agent_run",
        runtime._client().fork_agent_run(run_id, checkpoint_id=checkpoint_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def resume_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("resume_agent_run")
    return _validate_runtime_api_payload(
        "resume_agent_run",
        runtime._client().resume_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def cancel_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("cancel_agent_run")
    return _validate_runtime_api_payload(
        "cancel_agent_run",
        runtime._client().cancel_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )


def approve_agent_run_runtime_request(runtime: Any, run_id: str) -> Any:
    runtime._require_api_transport("approve_agent_run")
    return _validate_runtime_api_payload(
        "approve_agent_run",
        runtime._client().approve_agent_run(run_id),
        _runtime_model_agent_runs_module().AgentRunOutput,
    )

