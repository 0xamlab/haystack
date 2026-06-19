"""Meta routes — health check, version, and machine-readable contracts."""

from datetime import UTC, datetime
from typing import Annotated, Any, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from apps.api_server.config import SettingsProxy
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.middleware.rbac import require_role
from apps.api_server.services.platform_contract_surface import build_platform_contract_surface
from apps.api_server.services.public_url_policy import request_origin_base_url
from apps.api_server.services.privacy_service import (
    get_egress_policy_payload,
    get_privacy_report,
    list_egress_events,
)
from apps.privacy_policy import (
    DeploymentMode,
    EgressClass,
    EgressDecisionValue,
    MeteringMode,
    TelemetryMode,
)
from apps.platform_contract import (
    PlatformContractManifestError,
    PlatformContractResponse,
    load_platform_contract_manifest_model,
    validate_platform_contract_payload,
)
from apps.runtime_manifest import (
    RuntimeAdminBenchmarksResponse,
    RuntimeAdminModulesResponse,
    RuntimeManifestBuildError,
    RuntimeManifestResponse,
    RuntimeReleaseValidationResponse,
    get_runtime_admin_benchmarks,
    get_runtime_admin_modules,
    get_runtime_manifest,
    get_runtime_release_validation,
    validate_runtime_admin_benchmarks_payload,
    validate_runtime_admin_modules_payload,
    validate_runtime_manifest_payload,
    validate_runtime_release_validation_payload,
)

router = APIRouter(tags=["System"])
settings = SettingsProxy()

ENGINE_VERSION = "0.1.0"
API_VERSION = "1.0.0"


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class VersionResponse(BaseModel):
    api_version: str
    engine_version: str
    environment: str


class AdminPrivacyRegistryResponse(BaseModel):
    algenta_owned_hosts: list[str]
    algenta_owned_suffixes: list[str]
    vendor_telemetry_hosts: list[str]
    private_host_suffixes: list[str]


class AdminEgressPolicyResponse(BaseModel):
    deployment_mode: DeploymentMode
    disable_cloud: bool
    disable_telemetry: bool
    telemetry_mode: TelemetryMode
    metering_mode: MeteringMode
    require_local_license: bool
    control_plane_url: str
    allow_outbound_network: bool
    egress_allowlist: list[str]
    algenta_owned_hosts: list[str]
    algenta_owned_suffixes: list[str]
    vendor_telemetry_hosts: list[str]
    private_host_suffixes: list[str]
    privacy_registry: AdminPrivacyRegistryResponse
    algenta_cloud_enabled: bool
    vendor_telemetry_enabled: bool
    customer_connector_egress_enabled: bool
    undeclared_public_egress_allowed: bool
    mandatory_heartbeat_enabled: bool
    metering_flush_enabled: bool
    algenta_owned_host_patterns: list[str]
    vpc_mode_note: str


class AdminEgressLogEntry(BaseModel):
    surface: str
    egress_class: EgressClass
    destination_host_hash: str
    destination_host_redacted: str
    decision: EgressDecisionValue
    reason: str
    timestamp: datetime
    deployment_mode: DeploymentMode
    service_name: str
    request_id: str | None = None


class AdminEgressLogResponse(BaseModel):
    entries: list[AdminEgressLogEntry]
    total: int
    page: int
    limit: int
    pages: int


class AdminPrivacyReportResponse(BaseModel):
    deployment_mode: DeploymentMode
    algenta_cloud_enabled: bool
    vendor_telemetry_enabled: bool
    customer_connector_egress_enabled: bool
    undeclared_public_egress_allowed: bool
    local_license_required: bool
    local_license_active: bool
    mandatory_heartbeat_enabled: bool
    metering_flush_enabled: bool
    telemetry_mode: TelemetryMode
    metering_mode: MeteringMode
    algenta_owned_egress_count_24h: int
    blocked_egress_attempt_count_24h: int
    last_outbound_request_at: datetime | None = None
    last_algenta_owned_egress_at: datetime | None = None


RuntimeRouteResponseT = TypeVar("RuntimeRouteResponseT", bound=BaseModel)


def _runtime_payload_http_exception(exc: RuntimeManifestBuildError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "error": {
                "code": exc.code,
                "message": str(exc),
                "details": exc.details,
            }
        },
    )


def _validated_runtime_route_response(
    payload: Any,
    *,
    validator: Callable[[Any], RuntimeRouteResponseT],
) -> RuntimeRouteResponseT:
    try:
        return validator(payload)
    except RuntimeManifestBuildError as exc:
        raise _runtime_payload_http_exception(exc) from exc


def _platform_contract_http_exception(exc: PlatformContractManifestError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "error": {
                "code": exc.code,
                "message": str(exc),
                "details": exc.details,
            }
        },
    )


def _validated_platform_contract_response(payload: Any) -> PlatformContractResponse:
    try:
        return validate_platform_contract_payload(payload)
    except PlatformContractManifestError as exc:
        raise _platform_contract_http_exception(exc) from exc


@router.get("/v1/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(UTC))


@router.get("/v1/version", response_model=VersionResponse, summary="API and engine version")
async def version() -> VersionResponse:
    return VersionResponse(
        api_version=API_VERSION,
        engine_version=ENGINE_VERSION,
        environment=settings.api_env,
    )


@router.get(
    "/v1/meta/contract",
    response_model=PlatformContractResponse,
    summary="Machine-readable Algenta contract",
)
async def contract(request: Request) -> PlatformContractResponse:
    manifest = load_platform_contract_manifest_model()
    try:
        payload = build_platform_contract_surface(
            manifest=manifest,
            request_origin=request_origin_base_url(request),
        )
    except PlatformContractManifestError as exc:
        raise _platform_contract_http_exception(exc) from exc
    return _validated_platform_contract_response(payload)


@router.get(
    "/v1/runtime/manifest",
    response_model=RuntimeManifestResponse,
    summary="Signed runtime manifest",
)
async def runtime_manifest() -> RuntimeManifestResponse:
    return _validated_runtime_route_response(
        get_runtime_manifest(),
        validator=validate_runtime_manifest_payload,
    )


@router.get(
    "/v1/admin/runtime/modules",
    response_model=RuntimeAdminModulesResponse,
    summary="Admin runtime module catalog",
)
async def runtime_admin_modules(
    _auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> RuntimeAdminModulesResponse:
    del _auth
    return _validated_runtime_route_response(
        get_runtime_admin_modules(),
        validator=validate_runtime_admin_modules_payload,
    )


@router.get(
    "/v1/admin/runtime/benchmarks",
    response_model=RuntimeAdminBenchmarksResponse,
    summary="Admin runtime benchmark catalog",
)
async def runtime_admin_benchmarks(
    _auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> RuntimeAdminBenchmarksResponse:
    del _auth
    return _validated_runtime_route_response(
        get_runtime_admin_benchmarks(),
        validator=validate_runtime_admin_benchmarks_payload,
    )


@router.get(
    "/v1/admin/runtime/validation",
    response_model=RuntimeReleaseValidationResponse,
    summary="Admin runtime release validation",
)
async def runtime_admin_validation(
    _auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> RuntimeReleaseValidationResponse:
    del _auth
    return _validated_runtime_route_response(
        get_runtime_release_validation(),
        validator=validate_runtime_release_validation_payload,
    )


@router.get(
    "/v1/admin/egress-policy",
    response_model=AdminEgressPolicyResponse,
    summary="Admin privacy egress policy",
)
async def admin_egress_policy(
    _auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> AdminEgressPolicyResponse:
    del _auth
    return AdminEgressPolicyResponse.model_validate(await get_egress_policy_payload())


@router.get(
    "/v1/admin/egress-log",
    response_model=AdminEgressLogResponse,
    summary="Admin privacy egress log",
)
async def admin_egress_log(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> AdminEgressLogResponse:
    payload = await list_egress_events(
        org_id=auth["org_id"],
        page=page,
        limit=limit,
    )
    return AdminEgressLogResponse.model_validate(payload)


@router.get(
    "/v1/admin/privacy-report",
    response_model=AdminPrivacyReportResponse,
    summary="Admin privacy report",
)
async def admin_privacy_report(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> AdminPrivacyReportResponse:
    return AdminPrivacyReportResponse.model_validate(
        await get_privacy_report(org_id=auth["org_id"])
    )
