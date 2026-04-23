"""High-level Connections/Datasets API — /v1/data/*."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.pagination import paginate_sequence
from apps.api_server.routers.query import _CACHE_LOCK, _PLANNER_CACHE, _SOURCE_CACHE
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_connection_service import (
    connect_data,
    refresh_dataset,
)
from apps.api_server.services.data_visibility import (
    dataset_manageable,
    filter_visible_datasets,
    get_visible_dataset_entry,
)

router = APIRouter(tags=["Data"])


class ConnectDataRequest(BaseModel):
    connection_type: str | None = Field(
        default=None,
        description="database | api | object_storage | file_upload",
    )
    dataset_name: str = Field(..., description="Public dataset name.")
    provider: str | None = Field(
        default=None,
        description="Specific provider such as postgres, snowflake, s3, rest.",
    )
    connector: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Canonical connector envelope with type/location/auth/options. "
            "Preferred for cross-SDK and MCP compatibility."
        ),
    )
    connection_id: str | None = Field(
        default=None,
        description="Reuse an existing saved connection.",
    )
    connection_name: str | None = Field(
        default=None,
        description="Optional saved connection label.",
    )
    connection_config: dict[str, Any] | None = Field(
        default=None,
        description="Connector credentials/config.",
    )
    selection: dict[str, Any] | None = Field(default=None, description="Chosen table/query/path.")
    description: str | None = Field(default=None)
    visibility: str | None = Field(default=None, description="private | shared")
    records: list[dict[str, Any]] | None = None
    csv: str | None = None
    json_str: str | None = None
    url: str | None = None
    excel_b64: str | None = None
    parquet_b64: str | None = None


def _dataset_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": entry.get("id"),
        "source_id": entry.get("id"),
        "dataset_name": entry.get("dataset_name") or entry.get("name") or entry.get("id"),
        "source_name": entry.get("name"),
        "description": entry.get("description"),
        "connection_id": entry.get("connector_id"),
        "connection_type": entry.get("connection_type"),
        "provider": entry.get("provider"),
        "visibility": entry.get("visibility", "private"),
        "owner_user_id": entry.get("owner_user_id"),
        "owner_key_id": entry.get("owner_key_id"),
        "refreshable": bool(entry.get("refreshable")),
        "row_count": entry.get("row_count", 0),
        "columns": entry.get("columns", 0),
        "roles_summary": entry.get("roles_summary", {}),
        "registered_at": entry.get("registered_at"),
        "selection": entry.get("selection"),
    }


@router.post("/v1/data/connect", summary="Connect data, pick a dataset, and make it queryable.")
async def connect_dataset(
    payload: ConnectDataRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, Any]:
    return await connect_data(db=db, auth=auth, payload=payload.model_dump(exclude_none=True))


@router.get("/v1/data", summary="List visible datasets for the caller.")
async def list_data(
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    datasets = [
        _dataset_summary(entry)
        for entry in filter_visible_datasets(sreg.list_sources(org_id), auth)
    ]
    paged = paginate_sequence(datasets, page=page, limit=limit)
    return {
        "datasets": paged.items,
        "count": len(paged.items),
        "total": paged.total,
        "page": paged.page,
        "limit": paged.limit,
        "pages": paged.pages,
    }


@router.get("/v1/data/{dataset_id}", summary="Get one dataset plus its schema.")
async def get_data(
    dataset_id: str,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    entry = get_visible_dataset_entry(org_id, dataset_id, auth)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"Dataset '{dataset_id}' not found.",
                }
            },
        )
    schema = sreg.get_source_meta(org_id, dataset_id)
    return {"dataset": _dataset_summary(entry), "schema": schema}


@router.post("/v1/data/{dataset_id}/refresh", summary="Refresh a dataset from its saved origin.")
async def refresh_data(
    dataset_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, Any]:
    return await refresh_dataset(db=db, auth=auth, dataset_id=dataset_id)


@router.delete("/v1/data/{dataset_id}", summary="Disconnect data by deleting the dataset.")
async def disconnect_data(
    dataset_id: str,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, Any]:
    from apps.api_server.services.data_connection_service import (
        get_visible_connector,
    )
    from apps.api_server.services.data_visibility import connector_manageable

    org_id = str(auth["org_id"])
    entry = get_visible_dataset_entry(org_id, dataset_id, auth)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"Dataset '{dataset_id}' not found.",
                }
            },
        )
    if not dataset_manageable(entry, auth):
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                "You do not have permission to disconnect this dataset.",
            ),
        )

    connector_id = entry.get("connector_id")
    deleted = sreg.delete_source(org_id, dataset_id)
    async with _CACHE_LOCK:
        _SOURCE_CACHE.pop(dataset_id, None)
        _PLANNER_CACHE.clear()
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"Dataset '{dataset_id}' not found.",
                }
            },
        )

    connector_deleted = False
    if connector_id:
        remaining = [
            item
            for item in sreg.list_sources(org_id)
            if item.get("connector_id") == connector_id and item.get("id") != dataset_id
        ]
        if not remaining:
            try:
                connector = await get_visible_connector(db, uuid.UUID(str(connector_id)), auth)
            except Exception:
                connector = None
            if connector is not None and connector_manageable(connector, auth):
                await db.delete(connector)
                await db.commit()
                connector_deleted = True

    return {"dataset_id": dataset_id, "status": "deleted", "connection_deleted": connector_deleted}
