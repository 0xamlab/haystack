"""Data connector CRUD + connection testing — /v1/connectors.

Schemas and tester logic have been extracted to:
  apps/api_server/services/connectors/schemas.py  — Pydantic models + type constants
  apps/api_server/services/connectors/tester.py   — Real connection testers
"""

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.models.data_connector import ConnectorStatus, DataConnector
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.connectors import (
    VALID_TYPES,
    ConnectorCreate,
    ConnectorResponse,
    ConnectorTestResult,
    ConnectorUpdate,
    normalize_type,
    test_connector_real,
)
from apps.api_server.services.data_connection_specs import browse_connector_real
from apps.api_server.services.data_visibility import (
    connector_manageable,
    get_visible_connector,
    list_visible_connectors,
    normalize_visibility,
)

router = APIRouter(tags=["Data Connectors"])


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
    raw = payload.connector_type.lower().replace("-", "_")
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
    ct = normalize_type(raw)
    config_json = json.dumps(payload.config) if payload.config else None
    visibility = normalize_visibility(payload.visibility, auth)

    connector = DataConnector(
        org_id=auth["org_id"],
        name=payload.name,
        description=payload.description,
        connector_type=ct,  # type: ignore[arg-type]
        config_json=config_json,
        status=ConnectorStatus.UNTESTED,
        visibility=visibility,
        owner_user_id=auth.get("user_id"),
        owner_key_id=auth.get("key_id"),
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return _to_response(connector)


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
        connector.name = payload.name  # type: ignore[assignment]
    if payload.description is not None:
        connector.description = payload.description  # type: ignore[assignment]
    if payload.visibility is not None:
        connector.visibility = normalize_visibility(payload.visibility, auth)  # type: ignore[assignment]
    if payload.config is not None:
        connector.config_json = json.dumps(payload.config)  # type: ignore[assignment]
        connector.status = ConnectorStatus.UNTESTED  # type: ignore[assignment]
        connector.error_message = None  # type: ignore[assignment]

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
) -> ConnectorTestResult:
    connector = await get_visible_connector(db, connector_id, auth)

    config: dict[str, Any] = {}
    if connector.config_json:
        try:
            config = json.loads(connector.config_json)
        except json.JSONDecodeError:
            config = {}

    success, message, latency_ms = await test_connector_real(connector.connector_type.value, config)

    connector.status = ConnectorStatus.LIVE if success else ConnectorStatus.ERROR  # type: ignore[assignment]
    connector.last_tested_at = datetime.now(tz=UTC)  # type: ignore[assignment]
    connector.error_message = None if success else message  # type: ignore[assignment]
    await db.commit()

    return ConnectorTestResult(
        success=success, message=message, latency_ms=latency_ms if latency_ms else None
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


@router.get(
    "/v1/connectors/{connector_id}/browse",
    response_model=BrowseResult,
    summary="Browse connector schema — list tables, files, or datasets",
)
async def browse_connector(
    connector_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> BrowseResult:
    connector = await get_visible_connector(db, connector_id, auth)

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

    config: dict[str, Any] = {}
    if connector.config_json:
        try:
            config = json.loads(connector.config_json)
        except json.JSONDecodeError:
            config = {}

    ct = connector.connector_type.value
    try:
        items, message = await browse_connector_real(ct, config)
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

    return BrowseResult(connector_type=ct, items=items, total=len(items), message=message)
