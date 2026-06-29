"""Data connector CRUD + connection testing — /v1/connectors.

Schemas and tester logic have been extracted to:
  apps/api_server/services/connectors/schemas.py  — Pydantic models + type constants
  apps/api_server/services/connectors/tester.py   — Real connection testers
"""

import json
from datetime import UTC, datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.models.data_connector import ConnectorStatus, DataConnector
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.config_crypto import (
    config_fingerprint,
    decrypt_config_json,
    encrypt_config_json,
)
from apps.api_server.services.connectors import (
    VALID_TYPES,
    ConnectorCreate,
    ConnectorPreviewRequest,
    ConnectorResponse,
    ConnectorTestResult,
    ConnectorUpdate,
    classify_connector_failure,
    normalize_type,
    test_connector_real_detailed,
)
from apps.api_server.services.connectors.preview_cache_distributed_runner import (
    run_distributed_inline_preview_browse_once,
    run_distributed_inline_preview_test_once,
    run_distributed_saved_connector_browse_once,
    run_distributed_saved_connector_test_once,
)
from apps.api_server.services.connectors.preview_cache_distributed_state import (
    DistributedPreviewRedisClient,
)
from apps.api_server.services.connectors.preview_cache_local import (
    get_cached_inline_preview_browse_outcome,
    get_cached_inline_preview_test_outcome,
    put_cached_inline_preview_browse_outcome,
    put_cached_inline_preview_test_outcome,
    run_inline_preview_once,
)
from apps.api_server.services.connectors.preview_outcomes import (
    ConnectorBrowsePreviewOutcome,
)
from apps.api_server.services.connectors.tester import ConnectorTestOutcome
from apps.api_server.services.data_connection_browse import browse_connector_real_detailed
from apps.api_server.services.data_connection_discovery import (
    build_discovery_labels,
    build_discovery_metadata,
)
from apps.api_server.services.data_visibility import (
    connector_manageable,
    get_visible_connector,
    list_visible_connectors,
    normalize_visibility,
)
from apps.api_server.services.quota_service import check_named_rate_limit

router = APIRouter(tags=["Data Connectors"])
_INLINE_PREVIEW_LIMIT_PER_MINUTE = 20


class ConnectorListResponse(BaseModel):
    connectors: list[ConnectorResponse]
    total: int
    page: int
    limit: int
    pages: int


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _to_response(c: DataConnector) -> ConnectorResponse:
    return ConnectorResponse(
        id=str(c.id),
        name=c.name,
        description=c.description,
        connector_type=c.connector_type.value,
        status=c.status.value,
        visibility=str(c.visibility),
        last_tested_at=c.last_tested_at,
        error_message=c.error_message,
        created_at=c.created_at,
    )


def _parse_connector_config(
    config_json: str | None, org_id: UUID | str
) -> dict[str, Any]:
    config_json = decrypt_config_json(config_json, org_id=org_id)
    if not config_json:
        return {}
    try:
        parsed = json.loads(config_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_connector_type_or_422(raw_connector_type: str) -> str:
    raw = raw_connector_type.lower().replace("-", "_")
    if raw not in {t.replace("-", "_") for t in VALID_TYPES}:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_type",
                    "message": f"connector_type must be one of: {sorted(VALID_TYPES)}",
                }
            },
        )
    return normalize_type(raw)


async def _check_inline_preview_rate_limit(
    *,
    request: Request,
    auth: AuthContext,
    redis_client: object,
) -> None:
    await check_named_rate_limit(
        auth["org_id"],
        redis_client,
        key_prefix="inline-preview",
        limit_per_minute=_INLINE_PREVIEW_LIMIT_PER_MINUTE,
        request_state=request.state,
        error_code="inline_preview_rate_limited",
        error_message=(
            "Inline connector previews are rate limited. Create and reuse a saved "
            "connector for production workflows."
        ),
    )


def _preview_browse_failure_http_exception(exc: Exception) -> HTTPException:
    failure_type, recoverable = classify_connector_failure(message=str(exc), exception=exc)
    if failure_type != "unknown":
        return HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "connector_test_failed",
                    "message": str(exc),
                    "details": {
                        "status": "error",
                        "error_type": failure_type,
                        "recoverable": recoverable,
                    },
                }
            },
        )
    return HTTPException(
        status_code=502,
        detail={"error": {"code": "browse_failed", "message": str(exc)}},
    )


def _org_scope_id(auth: AuthContext) -> str:
    return str(auth["org_id"])


def _distributed_preview_redis(
    redis_client: object,
) -> DistributedPreviewRedisClient | None:
    if redis_client is None:
        return None
    return cast(DistributedPreviewRedisClient, redis_client)


# ─── Routes ──────────────────────────────────────────────────────────────────


@router.get(
    "/v1/connectors",
    response_model=list[ConnectorResponse] | ConnectorListResponse,
    summary="List data connectors",
)
async def list_connectors(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[ConnectorResponse] | ConnectorListResponse:
    connectors = [_to_response(c) for c in await list_visible_connectors(db, auth)]
    if page is None and limit is None:
        return connectors
    envelope = paginate_sequence(connectors, page=page or 1, limit=limit or 25)
    return ConnectorListResponse(
        connectors=envelope.items,
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
    )


@router.post(
    "/v1/connectors",
    response_model=ConnectorResponse,
    status_code=201,
    summary="Create a data connector with credentials",
)
async def create_connector(
    payload: ConnectorCreate,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> ConnectorResponse:
    ct = _normalize_connector_type_or_422(payload.connector_type)
    config_json = json.dumps(payload.config) if payload.config else None
    visibility = normalize_visibility(payload.visibility, auth)

    if auth.get("email") == "offline_license":
        # Offline (device-token): persist the connector to the LOCAL registry, not Postgres, so the
        # whole repo flow (register + every fix) is DB-free on the device hot path. config_json is
        # encrypted exactly like the DB row, so parse_connector_config decrypts it unchanged.
        import uuid as _uuid

        from apps.api_server.services import local_connector_store as _lcs

        record = {
            "id": str(_uuid.uuid4()),
            "org_id": str(auth["org_id"]),
            "workspace_id": str(auth["workspace_id"]) if auth.get("workspace_id") else None,
            "name": payload.name,
            "description": payload.description,
            "connector_type": ct,
            "config_json": encrypt_config_json(config_json, org_id=auth["org_id"]),
            "config_fingerprint": config_fingerprint(payload.config),
            "status": ConnectorStatus.UNTESTED.value,
            "visibility": visibility,
            "owner_user_id": str(auth["user_id"]) if auth.get("user_id") else None,
            "owner_key_id": str(auth["key_id"]) if auth.get("key_id") else None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        _lcs.save_connector(record)
        return _to_response(_lcs.synthesize_connector(record))

    connector = DataConnector(
        org_id=auth["org_id"],
        name=payload.name,
        description=payload.description,
        connector_type=ct,
        config_json=encrypt_config_json(config_json, org_id=auth["org_id"]),
        config_fingerprint=config_fingerprint(payload.config),
        status=ConnectorStatus.UNTESTED,
        visibility=visibility,
        owner_user_id=auth.get("user_id"),
        owner_key_id=auth.get("key_id"),
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return _to_response(connector)


@router.get(
    "/v1/connectors/{connector_id}",
    response_model=ConnectorResponse,
    summary="Get one data connector",
)
async def get_connector(
    connector_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> ConnectorResponse:
    connector = await get_visible_connector(db, connector_id, auth)
    return _to_response(connector)


@router.get(
    "/v1/connectors/types",
    summary="List supported connector types",
)
async def list_connector_types(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, list[str]]:
    del auth
    from apps.api_server.connectors import ConnectorRegistry

    return {"types": sorted(set(ConnectorRegistry.available_types()) | VALID_TYPES)}


@router.patch(
    "/v1/connectors/{connector_id}",
    response_model=ConnectorResponse,
    summary="Update connector name or config",
)
async def update_connector(
    connector_id: UUID,
    payload: ConnectorUpdate,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> ConnectorResponse:
    connector = await get_visible_connector(db, connector_id, auth)
    if not connector_manageable(connector, auth):
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                "You do not have permission to update this connection.",
            ),
        )

    if payload.name is not None:
        connector.name = payload.name
    if payload.description is not None:
        connector.description = payload.description
    if payload.visibility is not None:
        connector.visibility = normalize_visibility(payload.visibility, auth)
    if payload.config is not None:
        connector.config_json = encrypt_config_json(
            json.dumps(payload.config), org_id=connector.org_id
        )
        connector.config_fingerprint = config_fingerprint(payload.config)
        connector.status = ConnectorStatus.UNTESTED
        connector.error_message = None

    await db.commit()
    await db.refresh(connector)
    return _to_response(connector)


@router.post(
    "/v1/connectors/{connector_id}/test",
    response_model=ConnectorTestResult,
    summary="Test connector — real connection attempt",
)
async def test_connector(
    connector_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> ConnectorTestResult:
    connector = await get_visible_connector(db, connector_id, auth)
    config = _parse_connector_config(connector.config_json, connector.org_id)
    org_id = _org_scope_id(auth)
    distributed_redis = _distributed_preview_redis(redis_client)

    async def _load_saved_test() -> ConnectorTestOutcome:
        outcome = await test_connector_real_detailed(
            connector.connector_type.value,
            config,
        )
        connector.status = ConnectorStatus.LIVE if outcome.success else ConnectorStatus.ERROR
        connector.last_tested_at = datetime.now(tz=UTC)
        connector.error_message = None if outcome.success else outcome.message
        await db.commit()
        return outcome

    outcome = await run_inline_preview_once(
        operation="saved_test",
        org_id=org_id,
        connector_type=connector.connector_type.value,
        config={
            "connector_id": str(connector.id),
            "config": config,
        },
        load=lambda: run_distributed_saved_connector_test_once(
            redis_client=distributed_redis,
            org_id=org_id,
            connector_id=str(connector.id),
            connector_type=connector.connector_type.value,
            config=config,
            load=_load_saved_test,
        ),
    )

    return ConnectorTestResult(
        success=outcome.success,
        message=outcome.message,
        latency_ms=outcome.latency_ms,
        status=outcome.status,
        error_type=outcome.error_type,
        recoverable=outcome.recoverable,
    )


@router.post(
    "/v1/connectors/test",
    response_model=ConnectorTestResult,
    summary="Test an inline connector preview without saving it",
)
async def test_connector_preview(
    payload: ConnectorPreviewRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> ConnectorTestResult:
    connector_type = _normalize_connector_type_or_422(payload.connector_type)
    config = dict(payload.config or {})
    org_id = _org_scope_id(auth)
    distributed_redis = _distributed_preview_redis(redis_client)
    await _check_inline_preview_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    cached_outcome = get_cached_inline_preview_test_outcome(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    if cached_outcome is not None:
        outcome = cached_outcome
    else:

        async def _load_preview_test() -> ConnectorTestOutcome:
            outcome = await test_connector_real_detailed(connector_type, config)
            if outcome.success:
                return put_cached_inline_preview_test_outcome(
                    org_id=org_id,
                    connector_type=connector_type,
                    config=config,
                    outcome=outcome,
                )
            return outcome

        outcome = await run_inline_preview_once(
            operation="test",
            org_id=org_id,
            connector_type=connector_type,
            config=config,
            load=lambda: run_distributed_inline_preview_test_once(
                redis_client=distributed_redis,
                org_id=org_id,
                connector_type=connector_type,
                config=config,
                load=_load_preview_test,
            ),
        )
    return ConnectorTestResult(
        success=outcome.success,
        message=outcome.message,
        latency_ms=outcome.latency_ms,
        status=outcome.status,
        error_type=outcome.error_type,
        recoverable=outcome.recoverable,
    )


@router.delete("/v1/connectors/{connector_id}", status_code=204, summary="Delete a data connector")
async def delete_connector(
    connector_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> None:
    connector = await get_visible_connector(db, connector_id, auth)
    if not connector_manageable(connector, auth):
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                "You do not have permission to delete this connection.",
            ),
        )
    await db.delete(connector)
    await db.commit()


# ─── Browse ───────────────────────────────────────────────────────────────────


class BrowseResult(BaseModel):
    connector_type: str
    items: list[dict[str, Any]]
    total: int
    message: str
    labels: dict[str, Any]
    discovery: dict[str, Any]


@router.get(
    "/v1/connectors/{connector_id}/browse",
    response_model=BrowseResult,
    summary="Browse connector schema — list tables, files, or datasets",
)
async def browse_connector(
    connector_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> BrowseResult:
    connector = await get_visible_connector(db, connector_id, auth)
    org_id = _org_scope_id(auth)
    distributed_redis = _distributed_preview_redis(redis_client)

    if connector.status.value != "live":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "not_connected",
                    "message": (
                        "Connector must be tested and live before browsing. Run /test first."
                    ),
                }
            },
        )

    config = _parse_connector_config(connector.config_json, connector.org_id)

    ct = connector.connector_type.value

    async def _load_saved_browse() -> ConnectorBrowsePreviewOutcome:
        try:
            items, message, discovery = await browse_connector_real_detailed(ct, config)
        except ImportError as exc:
            raise HTTPException(
                status_code=501,
                detail={"error": {"code": "not_implemented", "message": str(exc)}},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": {"code": "browse_failed", "message": str(exc)}},
            ) from exc
        return ConnectorBrowsePreviewOutcome(
            items=items,
            message=message,
            discovery=discovery or build_discovery_metadata(ct, config=config, items=items),
            labels=build_discovery_labels(
                ct,
                config=config,
                items=items,
                provider_metadata=discovery,
            ),
        )

    outcome = await run_inline_preview_once(
        operation="saved_browse",
        org_id=org_id,
        connector_type=ct,
        config={
            "connector_id": str(connector.id),
            "config": config,
        },
        load=lambda: run_distributed_saved_connector_browse_once(
            redis_client=distributed_redis,
            org_id=org_id,
            connector_id=str(connector.id),
            connector_type=ct,
            config=config,
            load=_load_saved_browse,
        ),
    )

    return BrowseResult(
        connector_type=ct,
        items=outcome.items,
        total=len(outcome.items),
        message=outcome.message,
        labels=outcome.labels,
        discovery=outcome.discovery,
    )


@router.post(
    "/v1/connectors/browse",
    response_model=BrowseResult,
    summary="Browse an inline connector preview without saving it",
)
async def browse_connector_preview(
    payload: ConnectorPreviewRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> BrowseResult:
    connector_type = _normalize_connector_type_or_422(payload.connector_type)
    config = dict(payload.config or {})
    org_id = _org_scope_id(auth)
    distributed_redis = _distributed_preview_redis(redis_client)
    await _check_inline_preview_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    cached_outcome = get_cached_inline_preview_browse_outcome(
        org_id=org_id,
        connector_type=connector_type,
        config=config,
    )
    if cached_outcome is None:

        async def _load_preview_browse() -> ConnectorBrowsePreviewOutcome:
            try:
                items, message, discovery = await browse_connector_real_detailed(
                    connector_type,
                    config,
                )
            except ImportError as exc:
                raise HTTPException(
                    status_code=501,
                    detail={"error": {"code": "not_implemented", "message": str(exc)}},
                ) from exc
            except Exception as exc:
                raise _preview_browse_failure_http_exception(exc) from exc
            labels = build_discovery_labels(
                connector_type,
                config=config,
                items=items,
                provider_metadata=discovery,
            )
            return put_cached_inline_preview_browse_outcome(
                org_id=org_id,
                connector_type=connector_type,
                config=config,
                outcome=ConnectorBrowsePreviewOutcome(
                    items=items,
                    message=message,
                    discovery=discovery
                    or build_discovery_metadata(
                        connector_type,
                        config=config,
                        items=items,
                    ),
                    labels=labels,
                ),
            )

        cached_outcome = await run_inline_preview_once(
            operation="browse",
            org_id=org_id,
            connector_type=connector_type,
            config=config,
            load=lambda: run_distributed_inline_preview_browse_once(
                redis_client=distributed_redis,
                org_id=org_id,
                connector_type=connector_type,
                config=config,
                load=_load_preview_browse,
            ),
        )

    return BrowseResult(
        connector_type=connector_type,
        items=cached_outcome.items,
        total=len(cached_outcome.items),
        message=cached_outcome.message,
        labels=cached_outcome.labels,
        discovery=cached_outcome.discovery,
    )
