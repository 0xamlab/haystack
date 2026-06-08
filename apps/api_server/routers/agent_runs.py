from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.schemas.agent_runs import (
    AgentRunCheckpointsResponse,
    AgentRunCheckpointListResponse,
    AgentRunCreateRequest,
    AgentRunEventsResponse,
    AgentRunForkRequest,
    AgentRunListResponse,
    AgentRunMissionEventListResponse,
    AgentRunMissionEventsResponse,
    AgentRunReplayRequest,
    AgentRunReplayResponse,
    AgentRunResource,
    AgentRunTelemetryResponse,
    AgentRunTelemetryListResponse,
)
from apps.api_server.services.agent_run_service import (
    AgentRunServiceError,
    approve_agent_run,
    cancel_agent_run,
    create_agent_run,
    fork_agent_run,
    get_agent_run,
    get_agent_run_events,
    get_agent_run_checkpoints,
    get_agent_run_mission_events,
    get_agent_run_telemetry,
    list_agent_runs,
    query_agent_run_checkpoints,
    query_agent_run_mission_events,
    query_agent_run_telemetry,
    replay_agent_run,
    resume_agent_run,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.audit_service import get_client_ip, write_audit_event
from apps.api_server.services.quota_service import check_quota_redis, check_rate_limit

router = APIRouter(tags=["Agent Runtime"])


def _sse_data(payload: object) -> str:
    if payload == "[DONE]":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}\n\n"


async def _agent_run_events_stream(
    *,
    run_id: str,
    auth: AuthContext,
    limit: int,
    request: Request,
) -> AsyncIterator[str]:
    yielded_event_ids: set[str] = set()
    while True:
        events = get_agent_run_events(run_id=run_id, auth=auth, limit=limit)
        for event in events:
            if event.event_id in yielded_event_ids:
                continue
            yielded_event_ids.add(event.event_id)
            yield _sse_data(
                {
                    "type": "agent.run.event",
                    "run_id": run_id,
                    "event": event.model_dump(mode="json"),
                }
            )

        run = get_agent_run(run_id=run_id, auth=auth)
        if run.status in {"completed", "cancelled"}:
            yield _sse_data(
                {
                    "type": "agent.run.completed",
                    "run_id": run_id,
                    "status": run.status,
                    "total_events": len(events),
                }
            )
            yield _sse_data("[DONE]")
            return

        if await request.is_disconnected():
            return
        await asyncio.sleep(0.2)


async def _quota_check(
    *,
    auth: AuthContext,
    redis_client: Any,
    request_state: Any | None = None,
) -> None:
    await check_rate_limit(
        auth["org_id"],
        auth["plan"],
        redis_client,
        request_state=request_state,
    )
    await check_quota_redis(auth["org_id"], auth["plan"], redis_client)


def _agent_run_http_exception(exc: AgentRunServiceError) -> HTTPException:
    if exc.code in {"agent_run_not_found", "agent_run_checkpoint_not_found"}:
        status_code = 404
    elif exc.code == "agent_run_invalid_state":
        status_code = 409
    elif exc.code == "agent_run_replay_mismatch":
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            }
        },
    )


def _agent_run_metadata(run: AgentRunResource) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "selected_tool": run.selected_tool,
        "request_hash": run.request_hash,
        "decision_hash": run.decision_hash,
        "policy_snapshot_id": run.policy_snapshot_id,
        "schema_snapshot_id": run.schema_snapshot_id,
        "manifest_version": run.manifest_version,
        "latest_checkpoint_id": run.latest_checkpoint_id,
        "checkpoint_count": run.checkpoint_count,
        "artifact_refs": run.artifact_refs,
        "replayable": run.replayable,
        "source_run_id": run.source_run_id,
        "source_checkpoint_id": run.source_checkpoint_id,
    }


def _agent_run_replay_metadata(response: AgentRunReplayResponse) -> dict[str, Any]:
    return {
        "run_id": response.run_id,
        "checkpoint_id": response.checkpoint_id,
        "replay_status": response.replay_status,
        "compared_event_count": response.compared_event_count,
        "checkpoint_count": response.checkpoint_count,
        "request_hash": response.request_hash,
        "decision_hash": response.decision_hash,
        "content_hash": response.content_hash,
        "policy_snapshot_id": response.policy_snapshot_id,
        "schema_snapshot_id": response.schema_snapshot_id,
        "manifest_version": response.manifest_version,
        "failure_code": response.failure_code,
    }


@router.post(
    "/v1/agent/runs",
    response_model=AgentRunResource,
    summary="Create a persisted agent run",
    description=(
        "Creates a deterministic persisted agent run. The run can complete immediately, "
        "pause before execution, or wait for approval before executing its selected tool."
    ),
)
async def create_run(
    payload: AgentRunCreateRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[Any, Depends(get_redis)],
    db: Any = Depends(get_db),
) -> AgentRunResource:
    await _quota_check(
        auth=auth,
        redis_client=redis_client,
        request_state=request.state,
    )
    try:
        run = await create_agent_run(payload, auth=auth, request_state=request.state)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.create",
        resource_type="agent_run",
        resource_id=run.run_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_metadata(run),
    )
    await db.commit()
    return run


@router.get(
    "/v1/agent/runs",
    response_model=AgentRunListResponse,
    summary="List persisted agent runs",
)
async def list_runs(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
) -> AgentRunListResponse:
    normalized_status: str | None = None
    if status is not None:
        normalized_status = status.strip()
        valid_statuses = {"running", "paused", "requires_approval", "completed", "cancelled"}
        if normalized_status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_agent_run_status",
                        "message": "status must be one of: cancelled, completed, paused, requires_approval, running.",
                        "details": {"status": normalized_status},
                    }
                },
            )
    return list_agent_runs(
        auth=auth,
        page=page,
        limit=limit,
        status=normalized_status,  # type: ignore[arg-type]
        request_hash=request_hash.strip() if isinstance(request_hash, str) and request_hash.strip() else None,
        policy_snapshot_id=(
            policy_snapshot_id.strip()
            if isinstance(policy_snapshot_id, str) and policy_snapshot_id.strip()
            else None
        ),
        schema_snapshot_id=(
            schema_snapshot_id.strip()
            if isinstance(schema_snapshot_id, str) and schema_snapshot_id.strip()
            else None
        ),
    )


@router.get(
    "/v1/agent/runs/checkpoints",
    response_model=AgentRunCheckpointListResponse,
    summary="Query persisted agent run checkpoints across runs",
)
async def query_runs_checkpoints(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    checkpoint_id: str | None = Query(default=None),
) -> AgentRunCheckpointListResponse:
    normalized_status: str | None = None
    if status is not None:
        normalized_status = status.strip()
        valid_statuses = {"running", "paused", "requires_approval", "completed", "cancelled"}
        if normalized_status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_agent_run_status",
                        "message": "status must be one of: cancelled, completed, paused, requires_approval, running.",
                        "details": {"status": normalized_status},
                    }
                },
            )
    return query_agent_run_checkpoints(
        auth=auth,
        page=page,
        limit=limit,
        status=normalized_status,  # type: ignore[arg-type]
        request_hash=request_hash.strip() if isinstance(request_hash, str) and request_hash.strip() else None,
        policy_snapshot_id=(
            policy_snapshot_id.strip()
            if isinstance(policy_snapshot_id, str) and policy_snapshot_id.strip()
            else None
        ),
        schema_snapshot_id=(
            schema_snapshot_id.strip()
            if isinstance(schema_snapshot_id, str) and schema_snapshot_id.strip()
            else None
        ),
        run_id=run_id.strip() if isinstance(run_id, str) and run_id.strip() else None,
        checkpoint_id=(
            checkpoint_id.strip()
            if isinstance(checkpoint_id, str) and checkpoint_id.strip()
            else None
        ),
    )


@router.get(
    "/v1/agent/runs/mission-events",
    response_model=AgentRunMissionEventListResponse,
    summary="Query mission-event records across agent runs",
)
async def query_runs_mission_events(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
) -> AgentRunMissionEventListResponse:
    normalized_status: str | None = None
    if status is not None:
        normalized_status = status.strip()
        valid_statuses = {"running", "paused", "requires_approval", "completed", "cancelled"}
        if normalized_status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_agent_run_status",
                        "message": "status must be one of: cancelled, completed, paused, requires_approval, running.",
                        "details": {"status": normalized_status},
                    }
                },
            )
    return query_agent_run_mission_events(
        auth=auth,
        page=page,
        limit=limit,
        status=normalized_status,  # type: ignore[arg-type]
        request_hash=request_hash.strip() if isinstance(request_hash, str) and request_hash.strip() else None,
        policy_snapshot_id=(
            policy_snapshot_id.strip()
            if isinstance(policy_snapshot_id, str) and policy_snapshot_id.strip()
            else None
        ),
        schema_snapshot_id=(
            schema_snapshot_id.strip()
            if isinstance(schema_snapshot_id, str) and schema_snapshot_id.strip()
            else None
        ),
        run_id=run_id.strip() if isinstance(run_id, str) and run_id.strip() else None,
        event_type=event_type.strip() if isinstance(event_type, str) and event_type.strip() else None,
    )


@router.get(
    "/v1/agent/runs/telemetry",
    response_model=AgentRunTelemetryListResponse,
    summary="Query telemetry batches across agent runs",
)
async def query_runs_telemetry(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    status: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    telemetry_kind: str | None = Query(default=None),
    module_name: str | None = Query(default=None),
) -> AgentRunTelemetryListResponse:
    normalized_status: str | None = None
    if status is not None:
        normalized_status = status.strip()
        valid_statuses = {"running", "paused", "requires_approval", "completed", "cancelled"}
        if normalized_status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_agent_run_status",
                        "message": "status must be one of: cancelled, completed, paused, requires_approval, running.",
                        "details": {"status": normalized_status},
                    }
                },
            )
    return query_agent_run_telemetry(
        auth=auth,
        page=page,
        limit=limit,
        status=normalized_status,  # type: ignore[arg-type]
        request_hash=request_hash.strip() if isinstance(request_hash, str) and request_hash.strip() else None,
        policy_snapshot_id=(
            policy_snapshot_id.strip()
            if isinstance(policy_snapshot_id, str) and policy_snapshot_id.strip()
            else None
        ),
        schema_snapshot_id=(
            schema_snapshot_id.strip()
            if isinstance(schema_snapshot_id, str) and schema_snapshot_id.strip()
            else None
        ),
        run_id=run_id.strip() if isinstance(run_id, str) and run_id.strip() else None,
        telemetry_kind=(
            telemetry_kind.strip()
            if isinstance(telemetry_kind, str) and telemetry_kind.strip()
            else None
        ),
        module_name=module_name.strip() if isinstance(module_name, str) and module_name.strip() else None,
    )


@router.get(
    "/v1/agent/runs/{run_id}",
    response_model=AgentRunResource,
    summary="Get a persisted agent run",
)
async def get_run(
    run_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> AgentRunResource:
    try:
        return get_agent_run(run_id=str(run_id), auth=auth)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc


@router.get(
    "/v1/agent/runs/{run_id}/events",
    response_model=AgentRunEventsResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "JSON event list by default, or Server-Sent Events stream when stream=true."
            ),
        }
    },
    summary="List persisted agent run events",
)
async def get_run_events(
    run_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    limit: int = Query(default=1000, ge=1, le=1000),
    stream: bool = Query(default=False),
) -> AgentRunEventsResponse | StreamingResponse:
    try:
        run_id_text = str(run_id)
        events = get_agent_run_events(run_id=run_id_text, auth=auth, limit=limit)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    if stream:
        return StreamingResponse(
            _agent_run_events_stream(
                run_id=run_id_text,
                auth=auth,
                limit=limit,
                request=request,
            ),
            media_type="text/event-stream",
        )
    return AgentRunEventsResponse(run_id=run_id_text, data=events, total_events=len(events))


@router.get(
    "/v1/agent/runs/{run_id}/mission-events",
    response_model=AgentRunMissionEventsResponse,
    summary="List canonical agent run mission events",
)
async def list_run_mission_events(
    run_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    limit: int = Query(default=1000, ge=1, le=1000),
) -> AgentRunMissionEventsResponse:
    try:
        return get_agent_run_mission_events(run_id=str(run_id), auth=auth, limit=limit)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc


@router.get(
    "/v1/agent/runs/{run_id}/checkpoints",
    response_model=AgentRunCheckpointsResponse,
    summary="List persisted agent run checkpoints",
)
async def list_run_checkpoints(
    run_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> AgentRunCheckpointsResponse:
    try:
        return get_agent_run_checkpoints(run_id=str(run_id), auth=auth)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc


@router.get(
    "/v1/agent/runs/{run_id}/telemetry",
    response_model=AgentRunTelemetryResponse,
    summary="List agent run telemetry batches",
)
async def list_run_telemetry(
    run_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    limit: int = Query(default=1000, ge=1, le=1000),
) -> AgentRunTelemetryResponse:
    try:
        return get_agent_run_telemetry(run_id=str(run_id), auth=auth, limit=limit)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc


@router.post(
    "/v1/agent/runs/{run_id}/replay",
    response_model=AgentRunReplayResponse,
    summary="Replay a persisted agent run checkpoint deterministically",
)
async def replay_run(
    run_id: UUID,
    payload: AgentRunReplayRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: Any = Depends(get_db),
) -> AgentRunReplayResponse:
    try:
        response = replay_agent_run(run_id=str(run_id), auth=auth, payload=payload)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.replay",
        resource_type="agent_run_checkpoint",
        resource_id=response.checkpoint_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_replay_metadata(response),
    )
    await db.commit()
    return response


@router.post(
    "/v1/agent/runs/{run_id}/fork",
    response_model=AgentRunResource,
    summary="Fork a persisted agent run from a checkpoint",
)
async def fork_run(
    run_id: UUID,
    payload: AgentRunForkRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: Any = Depends(get_db),
) -> AgentRunResource:
    try:
        run = fork_agent_run(run_id=str(run_id), auth=auth, payload=payload)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.fork",
        resource_type="agent_run",
        resource_id=run.run_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_metadata(run),
    )
    await db.commit()
    return run


@router.post(
    "/v1/agent/runs/{run_id}/resume",
    response_model=AgentRunResource,
    summary="Resume a paused agent run",
)
async def resume_run(
    run_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[Any, Depends(get_redis)],
    db: Any = Depends(get_db),
) -> AgentRunResource:
    await _quota_check(
        auth=auth,
        redis_client=redis_client,
        request_state=request.state,
    )
    try:
        run = await resume_agent_run(run_id=str(run_id), auth=auth, request_state=request.state)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.resume",
        resource_type="agent_run",
        resource_id=run.run_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_metadata(run),
    )
    await db.commit()
    return run


@router.post(
    "/v1/agent/runs/{run_id}/cancel",
    response_model=AgentRunResource,
    summary="Cancel a pending agent run",
)
async def cancel_run(
    run_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    db: Any = Depends(get_db),
) -> AgentRunResource:
    try:
        run = cancel_agent_run(run_id=str(run_id), auth=auth)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.cancel",
        resource_type="agent_run",
        resource_id=run.run_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_metadata(run),
    )
    await db.commit()
    return run


@router.post(
    "/v1/agent/runs/{run_id}/approve",
    response_model=AgentRunResource,
    summary="Approve a waiting agent run",
)
async def approve_run(
    run_id: UUID,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[Any, Depends(get_redis)],
    db: Any = Depends(get_db),
) -> AgentRunResource:
    await _quota_check(
        auth=auth,
        redis_client=redis_client,
        request_state=request.state,
    )
    try:
        run = await approve_agent_run(run_id=str(run_id), auth=auth, request_state=request.state)
    except AgentRunServiceError as exc:
        raise _agent_run_http_exception(exc) from exc
    await write_audit_event(
        db,
        org_id=auth["org_id"],
        actor_email=auth.get("email", "system"),
        actor_user_id=auth.get("user_id"),
        action="agent_run.approve",
        resource_type="agent_run",
        resource_id=run.run_id,
        ip_address=get_client_ip(request),
        metadata=_agent_run_metadata(run),
    )
    await db.commit()
    return run
