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
from apps.api_server.services.data_discovery import (
    discovery_dataset_id,
    discovery_dataset_name,
    discovery_dataset_status,
    discovery_source_names,
    filter_discovery_entries,
)
from apps.api_server.services.data_visibility import (
    dataset_manageable,
    filter_visible_datasets,
    get_visible_dataset_entry,
)

router = APIRouter(tags=["Data"])


def _coerce_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _coerce_page(value: Any) -> int:
    return value if isinstance(value, int) and value >= 1 else 1


def _coerce_limit(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 1 else None


def _coerce_compact(value: Any) -> bool:
    return value if isinstance(value, bool) else False


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


def _dataset_summary(
    entry: dict[str, Any],
    *,
    compact: bool = False,
) -> dict[str, Any]:
    dataset_id = discovery_dataset_id(entry)
    dataset_name = discovery_dataset_name(entry)
    summary = {
        "dataset_id": dataset_id,
        "source_id": dataset_id,
        "dataset_name": dataset_name,
        "name": dataset_name,
        "status": discovery_dataset_status(entry),
        "source_names": discovery_source_names(entry),
        "column_count": int(entry.get("column_count") or entry.get("columns") or 0),
        "registered_at": entry.get("registered_at"),
    }
    if compact:
        return summary
    return {
        **summary,
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
        "discovery_labels": entry.get("discovery_labels"),
        "discovery_metadata": entry.get("discovery_metadata"),
        "selection": entry.get("selection"),
    }


def _dataset_selection_summary(
    entry: dict[str, Any],
    *,
    schema_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    query_hints = schema_meta.get("query_hints") if isinstance(schema_meta, dict) else None
    row_count = (
        schema_meta.get("row_count")
        if isinstance(schema_meta, dict) and schema_meta.get("row_count") is not None
        else entry.get("row_count", 0)
    )
    column_count = (
        len(schema_meta.get("columns", []))
        if isinstance(schema_meta, dict) and isinstance(schema_meta.get("columns"), list)
        else int(entry.get("column_count") or entry.get("columns") or 0)
    )
    return {
        "dataset_id": discovery_dataset_id(entry),
        "name": discovery_dataset_name(entry),
        "status": discovery_dataset_status(entry),
        "source_names": discovery_source_names(entry),
        "row_count": row_count,
        "column_count": column_count,
        "registered_at": entry.get("registered_at"),
        "query_hints": list(query_hints[:10]) if isinstance(query_hints, list) else [],
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
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    compact: bool = Query(default=False),
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    visible_entries = filter_visible_datasets(sreg.list_sources(org_id), auth)
    resolved_page = _coerce_page(page)
    resolved_limit = _coerce_limit(limit)
    resolved_search = _coerce_optional_text(search)
    resolved_status = _coerce_optional_text(status)
    resolved_source_name = _coerce_optional_text(source_name)
    resolved_compact = _coerce_compact(compact)
    total = len(visible_entries)
    filtered_entries = filter_discovery_entries(
        visible_entries,
        search=resolved_search,
        status=resolved_status,
        source_name=resolved_source_name,
    )
    datasets = [_dataset_summary(entry, compact=resolved_compact) for entry in filtered_entries]
    paged = paginate_sequence(datasets, page=resolved_page, limit=resolved_limit)
    return {
        "datasets": paged.items,
        "count": len(paged.items),
        "total": total,
        "matched_total": len(filtered_entries),
        "page": paged.page,
        "limit": paged.limit,
        "pages": paged.pages,
    }


@router.get(
    "/v1/data/{dataset_id}/summary",
    summary="Get low-token discovery summary for one dataset.",
)
async def get_data_summary(
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
    schema_meta = sreg.get_source_meta(org_id, dataset_id)
    return _dataset_selection_summary(entry, schema_meta=schema_meta)


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
    from apps.api_server.services.data_visibility import (
        connector_manageable,
        invalidate_visible_connector_cache,
    )

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
        # Count remaining datasets for this connector WITHIN the caller's workspace only —
        # an org-wide raw list_sources would let a sibling workspace's datasets keep (or a
        # cross-workspace dataset GC) the connector, mismatching the workspace-scoped
        # get_visible_connector fetch below.
        remaining = [
            item
            for item in filter_visible_datasets(sreg.list_sources(org_id), auth)
            if item.get("connector_id") == connector_id and item.get("id") != dataset_id
        ]
        if not remaining:
            try:
                connector = await get_visible_connector(
                    db,
                    uuid.UUID(str(connector_id)),
                    auth,
                    for_update=True,
                )
            except Exception:
                connector = None
            if connector is not None and connector_manageable(connector, auth):
                await db.delete(connector)
                await db.commit()
                invalidate_visible_connector_cache(connector_id, auth)
                connector_deleted = True

    return {"dataset_id": dataset_id, "status": "deleted", "connection_deleted": connector_deleted}
