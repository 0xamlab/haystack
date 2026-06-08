from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.capability_plane import (
    CapabilityAuthorizationCompleteRequest,
    CapabilityAuthorizationCompleteResponse,
    CapabilityAuthorizationStartRequest,
    CapabilityAuthorizationStartResponse,
    CapabilityBindingCreateRequest,
    CapabilityBindingPreviewRequest,
    CapabilityBindingResponse,
    CapabilityBindingTestResult,
    CapabilityBindingUpdateRequest,
    CapabilityCatalogEntry,
    CapabilityDiscoverResponse,
    CapabilityExecutionRequest,
    CapabilityExecutionResponse,
    CapabilityKind,
    CapabilityOutcomeRecord,
    CapabilityOutcomeRecordRequest,
    CapabilityPlaneError,
    CapabilityProviderResponse,
    CapabilityRoutePlan,
    CapabilityRouteRequest,
    BindingScope,
    capability_plane_error_payload,
    complete_capability_authorization_service,
    create_capability_binding_service,
    delete_capability_binding_service,
    discover_capability_binding_preview_service,
    discover_capability_binding_service,
    execute_capability_service,
    get_capability_binding_service,
    get_capability_provider_service,
    get_capability_service,
    list_capabilities_service,
    list_capability_bindings_service,
    list_capability_providers_service,
    record_capability_outcome_service,
    route_capabilities_service,
    start_capability_authorization_service,
    test_capability_binding_preview_service,
    test_capability_binding_service,
    update_capability_binding_service,
)

router = APIRouter(tags=["Capability Plane"])


def _raise_http_exception(exc: CapabilityPlaneError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=capability_plane_error_payload(exc),
    ) from exc


@router.get(
    "/v1/capability-providers",
    response_model=list[CapabilityProviderResponse],
    summary="List unified capability providers",
)
async def list_capability_providers(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> list[CapabilityProviderResponse]:
    try:
        return await list_capability_providers_service(db, auth)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.get(
    "/v1/capability-providers/{provider_id}",
    response_model=CapabilityProviderResponse,
    summary="Get one unified capability provider",
)
async def get_capability_provider(
    provider_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityProviderResponse:
    try:
        return await get_capability_provider_service(db, auth, provider_id)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.get(
    "/v1/capability-bindings",
    response_model=list[CapabilityBindingResponse],
    summary="List capability bindings",
)
async def list_capability_bindings(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    provider_id: str | None = Query(default=None),
    scope: BindingScope | None = Query(default=None),
) -> list[CapabilityBindingResponse]:
    try:
        return await list_capability_bindings_service(
            db,
            auth,
            provider_id=provider_id,
            scope=scope,
        )
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings",
    response_model=CapabilityBindingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a capability binding",
)
async def create_capability_binding(
    payload: CapabilityBindingCreateRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityBindingResponse:
    try:
        return await create_capability_binding_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.get(
    "/v1/capability-bindings/{binding_id}",
    response_model=CapabilityBindingResponse,
    summary="Get one capability binding",
)
async def get_capability_binding(
    binding_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityBindingResponse:
    try:
        return await get_capability_binding_service(db, auth, binding_id)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.patch(
    "/v1/capability-bindings/{binding_id}",
    response_model=CapabilityBindingResponse,
    summary="Update one capability binding",
)
async def update_capability_binding(
    binding_id: str,
    payload: CapabilityBindingUpdateRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityBindingResponse:
    try:
        return await update_capability_binding_service(db, auth, binding_id, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.delete(
    "/v1/capability-bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one capability binding",
)
async def delete_capability_binding(
    binding_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> Response:
    try:
        await delete_capability_binding_service(db, auth, binding_id)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/v1/capability-bindings/test",
    response_model=CapabilityBindingTestResult,
    summary="Preview-test an unsaved capability binding",
)
async def preview_test_capability_binding(
    payload: CapabilityBindingPreviewRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityBindingTestResult:
    try:
        return await test_capability_binding_preview_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings/{binding_id}/test",
    response_model=CapabilityBindingTestResult,
    summary="Test a saved capability binding",
)
async def test_capability_binding(
    binding_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityBindingTestResult:
    try:
        return await test_capability_binding_service(db, auth, binding_id)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings/discover",
    response_model=CapabilityDiscoverResponse,
    summary="Preview-discover capabilities for an unsaved binding",
)
async def preview_discover_capability_binding(
    payload: CapabilityBindingPreviewRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityDiscoverResponse:
    try:
        return await discover_capability_binding_preview_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings/{binding_id}/discover",
    response_model=CapabilityDiscoverResponse,
    summary="Discover capabilities for a saved binding",
)
async def discover_capability_binding(
    binding_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityDiscoverResponse:
    try:
        return await discover_capability_binding_service(db, auth, binding_id)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings/{binding_id}/authorize/start",
    response_model=CapabilityAuthorizationStartResponse,
    summary="Start capability-binding authorization",
)
async def start_capability_authorization(
    binding_id: str,
    payload: CapabilityAuthorizationStartRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityAuthorizationStartResponse:
    try:
        return await start_capability_authorization_service(db, auth, binding_id, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capability-bindings/{binding_id}/authorize/complete",
    response_model=CapabilityAuthorizationCompleteResponse,
    summary="Complete capability-binding authorization",
)
async def complete_capability_authorization(
    binding_id: str,
    payload: CapabilityAuthorizationCompleteRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityAuthorizationCompleteResponse:
    del binding_id
    try:
        return await complete_capability_authorization_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.get(
    "/v1/capabilities",
    response_model=list[CapabilityCatalogEntry],
    summary="List unified capabilities",
)
async def list_capabilities(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    kinds: list[CapabilityKind] = Query(default_factory=list),
    provider_ids: list[str] = Query(default_factory=list),
    binding_ids: list[str] = Query(default_factory=list),
) -> list[CapabilityCatalogEntry]:
    try:
        return await list_capabilities_service(
            db,
            auth,
            kinds=kinds,
            provider_ids=provider_ids,
            binding_ids=binding_ids,
        )
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.get(
    "/v1/capabilities/{capability_id}",
    response_model=CapabilityCatalogEntry,
    summary="Get one unified capability",
)
async def get_capability(
    capability_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    include_instruction: bool = Query(default=False),
) -> CapabilityCatalogEntry:
    try:
        return await get_capability_service(
            db,
            auth,
            capability_id,
            include_instruction=include_instruction,
        )
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capabilities/route",
    response_model=CapabilityRoutePlan,
    summary="Route an objective to one unified capability",
)
async def route_capabilities(
    payload: CapabilityRouteRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityRoutePlan:
    try:
        return await route_capabilities_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capabilities/execute",
    response_model=CapabilityExecutionResponse,
    summary="Execute one unified capability",
)
async def execute_capability(
    payload: CapabilityExecutionRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityExecutionResponse:
    try:
        return await execute_capability_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)


@router.post(
    "/v1/capabilities/outcomes",
    response_model=CapabilityOutcomeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record one capability outcome",
)
async def record_capability_outcome(
    payload: CapabilityOutcomeRecordRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> CapabilityOutcomeRecord:
    try:
        return await record_capability_outcome_service(db, auth, payload)
    except CapabilityPlaneError as exc:
        _raise_http_exception(exc)
