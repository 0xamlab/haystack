from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from apps.api_server.middleware.auth import get_current_org, get_redis, require_verified_email
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.quota_service import check_rate_limit
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime.mojo_library_runner import MojoLibraryError

router = APIRouter(tags=["Runtime Libraries"], dependencies=[Depends(require_verified_email)])


class RuntimeLibraryModuleResponse(BaseModel):
    name: str
    engine: str
    functions: list[str]


class RuntimeLibraryListResponse(BaseModel):
    modules: list[RuntimeLibraryModuleResponse]
    count: int
    total: int
    page: int
    limit: int
    pages: int


class RuntimeLibraryHealthResponse(BaseModel):
    status: str
    engine: str
    module_count: int
    runtime_available: bool


class RuntimeLibraryExecuteRequest(BaseModel):
    module: str = Field(..., description="Runtime library module name, for example `ab_testing`.")
    function: str = Field(..., description="Exported runtime library function name.")
    args: Any | None = Field(
        default=None,
        description="JSON-serializable positional args array, single value, or kwargs object.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional caller-supplied idempotency or tracing identifier.",
    )


class RuntimeLibraryExecuteResponse(BaseModel):
    module: str
    function: str
    result: Any | None
    latency_ms: float
    engine_used: str
    request_id: str | None


async def _enforce_runtime_library_rate_limit(
    *,
    request: Request,
    auth: AuthContext,
    redis_client: object,
) -> None:
    await check_rate_limit(
        auth["org_id"],
        auth["plan"],
        redis_client,
        request_state=request.state,
    )


def _mojo_library_http_exception(exc: MojoLibraryError, request: Request) -> HTTPException:
    if exc.code in {"module_not_registered", "function_not_registered"}:
        status_code = 404
    elif exc.code == "invalid_arguments":
        status_code = 422
    elif exc.code == "compute_runtime_unavailable":
        status_code = 503
    elif exc.code == "mojo_library_timeout":
        status_code = 504
    else:
        status_code = 502
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@router.get(
    "/v1/libraries",
    response_model=RuntimeLibraryListResponse,
    summary="List executable runtime libraries",
)
async def list_runtime_libraries(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(
        default=None,
        description="Optional substring match against module names and exported functions.",
    ),
) -> RuntimeLibraryListResponse:
    await _enforce_runtime_library_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    descriptors = [
        RuntimeLibraryModuleResponse(
            name=descriptor.name,
            engine=descriptor.engine,
            functions=list(descriptor.functions),
        )
        for descriptor in list_public_runtime_library_descriptors(query=q)
    ]
    paged = paginate_sequence(descriptors, page=page, limit=limit)
    return RuntimeLibraryListResponse(
        modules=paged.items,
        count=len(paged.items),
        total=paged.total,
        page=paged.page,
        limit=paged.limit,
        pages=paged.pages,
    )


@router.get(
    "/v1/libraries/health",
    response_model=RuntimeLibraryHealthResponse,
    summary="Check runtime library availability",
)
async def runtime_libraries_health(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> RuntimeLibraryHealthResponse:
    await _enforce_runtime_library_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    health = get_public_runtime_library_health()
    return RuntimeLibraryHealthResponse(
        status=health.status,
        engine=health.engine,
        module_count=health.module_count,
        runtime_available=health.runtime_available,
    )


@router.post(
    "/v1/libraries/execute",
    response_model=RuntimeLibraryExecuteResponse,
    summary="Execute one runtime library function",
)
async def execute_runtime_library(
    payload: RuntimeLibraryExecuteRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> RuntimeLibraryExecuteResponse:
    await _enforce_runtime_library_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    effective_request_id = payload.request_id or getattr(request.state, "request_id", None)
    try:
        execution = await execute_public_runtime_library(
            module=payload.module,
            function=payload.function,
            args=payload.args,
            request_id=effective_request_id,
        )
    except MojoLibraryError as exc:
        raise _mojo_library_http_exception(exc, request) from exc
    return RuntimeLibraryExecuteResponse(
        module=execution.module,
        function=execution.function,
        result=execution.result,
        latency_ms=execution.latency_ms,
        engine_used=execution.engine_used,
        request_id=execution.request_id,
    )
