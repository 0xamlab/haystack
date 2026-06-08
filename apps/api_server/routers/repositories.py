from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.schemas.repositories import (
    RepositoryApplyRequest,
    RepositoryApplyResponse,
    RepositoryDecisionPlanCreateRequest,
    RepositoryDecisionPlanResponse,
    RepositoryGraphQueryRequest,
    RepositoryGraphQueryResponse,
    RepositoryIntelligenceCapabilitiesResponse,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositorySnapshotResponse,
    RepositoryTriageRequest,
    RepositoryTriageResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_visibility import get_visible_connector
from apps.api_server.services.repository_intelligence import (
    RepositoryIntelligenceError,
    apply_repository_decision,
    create_repository_decision_plan,
    get_repository_intelligence_capabilities,
    create_repository_snapshot,
    get_repository_snapshot,
    query_repository_graph,
    simulate_repository_decision,
    triage_repository,
)

router = APIRouter(tags=["Repository Intelligence"])


def _repository_http_exception(exc: RepositoryIntelligenceError, request: Request) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@router.get(
    "/v1/repositories/capabilities",
    response_model=RepositoryIntelligenceCapabilitiesResponse,
    summary="List repository intelligence language support and progress",
)
async def get_capabilities(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryIntelligenceCapabilitiesResponse:
    del request, auth
    return get_repository_intelligence_capabilities()


@router.post(
    "/v1/repositories/{repository_id}/snapshots",
    response_model=RepositorySnapshotResponse,
    summary="Create or reuse an immutable repository snapshot",
)
async def create_snapshot(
    repository_id: UUID,
    payload: RepositorySnapshotCreateRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositorySnapshotResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return create_repository_snapshot(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.get(
    "/v1/repositories/{repository_id}/snapshots/{snapshot_id}",
    response_model=RepositorySnapshotResponse,
    summary="Get one immutable repository snapshot",
)
async def get_snapshot(
    repository_id: UUID,
    snapshot_id: str,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositorySnapshotResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return get_repository_snapshot(connector=connector, snapshot_id=snapshot_id)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/triage",
    response_model=RepositoryTriageResponse,
    summary="Triage a repository snapshot into a bounded workspace evidence bundle",
)
async def triage_repository_snapshot(
    repository_id: UUID,
    payload: RepositoryTriageRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryTriageResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return triage_repository(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/graph-query",
    response_model=RepositoryGraphQueryResponse,
    summary="Query repository dependency and blast-radius graph from one persisted snapshot",
)
async def query_repository_snapshot_graph(
    repository_id: UUID,
    payload: RepositoryGraphQueryRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryGraphQueryResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return query_repository_graph(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/decision-plans",
    response_model=RepositoryDecisionPlanResponse,
    summary="Create one stored immutable repository decision plan revision",
)
async def create_decision_plan(
    repository_id: UUID,
    payload: RepositoryDecisionPlanCreateRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryDecisionPlanResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await create_repository_decision_plan(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/simulate",
    response_model=DecisionEnvelope,
    summary="Simulate repository patch risk and populate the decision envelope gate",
)
async def simulate_repository_patch(
    repository_id: UUID,
    payload: RepositorySimulationRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> DecisionEnvelope:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await simulate_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc


@router.post(
    "/v1/repositories/{repository_id}/apply",
    response_model=RepositoryApplyResponse,
    summary="Apply a simulated repository decision through patch, local branch, or remote PR",
)
async def apply_repository_patch(
    repository_id: UUID,
    payload: RepositoryApplyRequest,
    request: Request,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RepositoryApplyResponse:
    connector = await get_visible_connector(db, repository_id, auth)
    try:
        return await apply_repository_decision(connector=connector, request=payload)
    except RepositoryIntelligenceError as exc:
        raise _repository_http_exception(exc, request) from exc
