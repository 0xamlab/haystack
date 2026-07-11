"""High-level Connections/Datasets orchestration on top of connectors + source registry."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, update
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.data_connector import (
    ConnectorStatus,
    ConnectorType,
    ConnectorVisibility,
    DataConnector,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.config_crypto import (
    config_fingerprint,
    decrypt_config_json,
    encrypt_config_json,
)
from apps.api_server.services.connector_contract import normalize_connect_payload
from apps.api_server.services.connectors import test_connector_real
from apps.api_server.services.data_connection_browse import (
    browse_connector_real,
    browse_connector_real_detailed,
)
from apps.api_server.services.data_connection_discovery import (
    build_discovery_labels,
    build_discovery_metadata,
)
from apps.api_server.services.data_connection_specs import (
    _build_object_storage_connection,
    build_source_spec,
    normalize_connection_provider,
)
from apps.api_server.services.data_visibility import (
    auth_key_id as _auth_key_id,
)
from apps.api_server.services.data_visibility import (
    auth_user_id as _auth_user_id,
)
from apps.api_server.services.data_visibility import (
    connector_manageable,
    dataset_manageable,
    filter_visible_datasets,
    get_visible_connector,
    get_visible_dataset_entry,
    list_visible_connectors,
    normalize_visibility,
    visibility_hash,
)
from apps.api_server.services.workspace_scope import (
    workspace_id_for_write,
    workspace_scope_clauses,
)

__all__ = [
    "_build_object_storage_connection",
    "browse_connector_real",
    "build_source_spec",
    "connector_manageable",
    "connect_data",
    "create_or_reuse_connector",
    "dataset_manageable",
    "filter_visible_datasets",
    "get_visible_connector",
    "get_visible_dataset_entry",
    "list_visible_connectors",
    "normalize_connection_provider",
    "normalize_visibility",
    "refresh_dataset",
    "visibility_hash",
]


logger = structlog.get_logger(__name__)


def _json_config(config: dict[str, Any] | None) -> str:
    return json.dumps(config or {}, sort_keys=True, separators=(",", ":"))


def _should_return_full_database_choices(config: dict[str, Any]) -> bool:
    return bool(str(config.get("schema", "") or "").strip())


def _selection_is_complete(
    *,
    provider: str,
    broad_type: str,
    selection: dict[str, Any],
    connector_config: dict[str, Any],
) -> bool:
    if broad_type == "database":
        if provider == "elasticsearch":
            return bool(selection.get("index") or connector_config.get("index"))
        if provider == "neo4j":
            return bool(
                selection.get("label")
                or selection.get("relationship_type")
                or connector_config.get("label")
                or connector_config.get("relationship_type")
                or selection.get("query")
                or selection.get("cypher")
                or connector_config.get("query")
                or connector_config.get("cypher")
            )
        if provider == "redis":
            return bool(selection.get("keys") or connector_config.get("keys"))
        return bool(
            selection.get("table")
            or selection.get("sql_query")
            or connector_config.get("table")
            or connector_config.get("sql_query")
            or connector_config.get("query")
        )
    if broad_type == "object_storage":
        return bool(
            selection.get("object_path")
            or connector_config.get("object_path")
            or connector_config.get("key")
            or connector_config.get("blob")
            or connector_config.get("blob_url")
        )
    return True


def _connector_status(connector: DataConnector) -> ConnectorStatus:
    raw_status = getattr(connector, "status", ConnectorStatus.UNTESTED)
    status_value = getattr(raw_status, "value", raw_status)
    try:
        return ConnectorStatus(str(status_value))
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "invalid_connector_status",
                    "message": "Connection has an invalid persisted verification status.",
                    "details": {"connector_id": str(connector.id)},
                }
            },
        ) from exc


def _persisted_verification_outcome(
    connector: DataConnector,
) -> tuple[bool, str, int] | None:
    status = _connector_status(connector)
    if status == ConnectorStatus.LIVE:
        return True, "Connection credentials already verified at registration.", 0
    if status == ConnectorStatus.ERROR:
        message = (
            str(getattr(connector, "error_message", "") or "").strip()
            or "Connection credential verification failed at registration."
        )
        return False, message, 0
    return None


def _copy_verification_state(*, source: DataConnector, target: DataConnector) -> None:
    target.status = source.status
    target.last_tested_at = source.last_tested_at
    target.error_message = source.error_message


def _connector_is_transient(connector: DataConnector) -> bool:
    try:
        return bool(sa_inspect(connector).transient)
    except NoInspectionAvailable:
        return False


async def _test_and_persist_local_connector(
    connector: DataConnector,
) -> tuple[bool, str, int]:
    from apps.api_server.services import local_connector_store

    record = local_connector_store.get_connector(str(connector.id))
    if record is None or record.get("org_id") != str(connector.org_id):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Connection not found."}},
        )
    parsed_config = json.loads(
        decrypt_config_json(connector.config_json, org_id=connector.org_id) or "{}"
    )
    config = parsed_config if isinstance(parsed_config, dict) else {}
    success, message, latency_ms = await test_connector_real(
        connector.connector_type.value,
        config,
    )
    tested_at = datetime.now(tz=UTC)
    connector.status = ConnectorStatus.LIVE if success else ConnectorStatus.ERROR
    connector.last_tested_at = tested_at
    connector.error_message = None if success else message
    record.update(
        {
            "status": connector.status.value,
            "last_tested_at": tested_at.isoformat(),
            "error_message": connector.error_message,
        }
    )
    local_connector_store.save_connector(record)
    return success, message, latency_ms


async def _test_and_persist_connector(
    connector: DataConnector,
    db: AsyncSession,
) -> tuple[bool, str, int]:
    if _connector_is_transient(connector):
        return await _test_and_persist_local_connector(connector)

    locked_result = await db.execute(
        select(DataConnector)
        .where(
            DataConnector.id == connector.id,
            DataConnector.org_id == connector.org_id,
        )
        .with_for_update()
    )
    locked_connector = locked_result.scalar_one_or_none()
    if locked_connector is None:
        await db.rollback()
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "Connection was deleted before credential verification began.",
                }
            },
        )

    persisted_outcome = _persisted_verification_outcome(locked_connector)
    if persisted_outcome is not None:
        await db.commit()
        _copy_verification_state(source=locked_connector, target=connector)
        return persisted_outcome

    parsed_config = json.loads(
        decrypt_config_json(
            locked_connector.config_json,
            org_id=getattr(locked_connector, "org_id", ""),
        )
        or "{}"
    )
    config = parsed_config if isinstance(parsed_config, dict) else {}
    success, message, latency_ms = await test_connector_real(
        locked_connector.connector_type.value,
        config,
    )
    status = ConnectorStatus.LIVE if success else ConnectorStatus.ERROR
    tested_at = datetime.now(tz=UTC)
    error_message = None if success else message
    result = await db.execute(
        update(DataConnector)
        .where(
            DataConnector.id == locked_connector.id,
            DataConnector.org_id == locked_connector.org_id,
        )
        .values(
            status=status,
            last_tested_at=tested_at,
            error_message=error_message,
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "Connection was deleted before its test result could be saved.",
                }
            },
        )
    await db.commit()
    locked_connector.status = status
    locked_connector.last_tested_at = tested_at
    locked_connector.error_message = error_message
    _copy_verification_state(source=locked_connector, target=connector)
    return success, message, latency_ms


async def _verify_connector_once(
    connector: DataConnector,
    db: AsyncSession,
) -> tuple[bool, str, int]:
    persisted_outcome = _persisted_verification_outcome(connector)
    if persisted_outcome is not None:
        logger.info(
            "connector_credential_probe_reused",
            connector_id=str(connector.id),
            status=_connector_status(connector).value,
        )
        return persisted_outcome
    return await _test_and_persist_connector(connector, db)


async def create_or_reuse_connector(
    *,
    db: AsyncSession,
    auth: AuthContext,
    name: str,
    description: str | None,
    connector_type: str,
    config: dict[str, Any],
    visibility: str,
) -> DataConnector:
    config_json = _json_config(config)
    config_fp = config_fingerprint(config)
    owner_user_id = auth.get("user_id")
    owner_key_id = auth.get("key_id")
    workspace_id = workspace_id_for_write(auth)
    # Dedupe on the deterministic fingerprint (config_json is now encrypted →
    # non-deterministic, so equality matching no longer works).
    result = await db.execute(
        select(DataConnector).where(
            *workspace_scope_clauses(DataConnector, auth),
            DataConnector.name == name,
            DataConnector.connector_type == ConnectorType(connector_type),
            DataConnector.config_fingerprint == config_fp,
            DataConnector.visibility == visibility,
            DataConnector.owner_user_id == owner_user_id,
            DataConnector.owner_key_id == owner_key_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is not None:
        return connector

    connector = DataConnector(
        org_id=auth["org_id"],
        workspace_id=workspace_id,
        name=name,
        description=description,
        connector_type=ConnectorType(connector_type),
        config_json=encrypt_config_json(config_json, org_id=auth["org_id"]),
        config_fingerprint=config_fp,
        status=ConnectorStatus.UNTESTED,
        visibility=visibility,
        owner_user_id=owner_user_id,
        owner_key_id=owner_key_id,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return connector


async def connect_data(
    *,
    db: AsyncSession,
    auth: AuthContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from apps.api_server.routers.sources import RegisterRequest, _register_source_impl

    payload = normalize_connect_payload(payload)

    dataset_name = str(payload.get("dataset_name", "")).strip()
    if not dataset_name:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "missing_dataset_name",
                    "message": "dataset_name is required.",
                }
            },
        )

    visibility = normalize_visibility(payload.get("visibility"), auth)
    description = payload.get("description")
    connection_name = str(payload.get("connection_name") or f"{dataset_name} connection").strip()
    selection = payload.get("selection") or {}
    if not isinstance(selection, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_selection",
                    "message": "selection must be an object.",
                }
            },
        )
    connection_config = payload.get("connection_config") or {}
    if connection_config and not isinstance(connection_config, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_connection_config",
                    "message": "connection_config must be an object.",
                }
            },
        )

    connector: DataConnector | None = None
    connector_config: dict[str, Any] = dict(connection_config)
    discovery_labels = build_discovery_labels(
        str(payload.get("provider") or payload.get("connection_type") or "file"),
        config=connector_config,
    )
    discovery_metadata = build_discovery_metadata(
        str(payload.get("provider") or payload.get("connection_type") or "file"),
        config=connector_config,
    )
    connector_id = payload.get("connection_id")
    if connector_id:
        connector = await get_visible_connector(
            db,
            uuid.UUID(str(connector_id)),
            auth,
        )
        connector_config = json.loads(
            decrypt_config_json(
                connector.config_json,
                org_id=getattr(connector, "org_id", ""),
            )
            or "{}"
        )
        broad_type, provider = normalize_connection_provider(
            connector.connector_type.value,
            connector_config,
        )
        visibility = str(connector.visibility or visibility)
        discovery_labels = build_discovery_labels(
            connector.connector_type.value,
            config=connector_config,
        )
        discovery_metadata = build_discovery_metadata(
            connector.connector_type.value,
            config=connector_config,
        )
    else:
        broad_type, provider = normalize_connection_provider(
            str(payload.get("connection_type", "")),
            connection_config,
            provider=payload.get("provider"),
        )
        discovery_labels = build_discovery_labels(provider, config=connector_config)
        discovery_metadata = build_discovery_metadata(provider, config=connector_config)
    if connector is None and broad_type != "file_upload":
        connector = await create_or_reuse_connector(
            db=db,
            auth=auth,
            name=connection_name,
            description=description,
            connector_type=provider,
            config=connector_config,
            visibility=visibility,
        )

    if connector is not None:
        success, message, latency_ms = await _verify_connector_once(connector, db)
        if not success:
            return {
                "status": "failed",
                "message": message,
                "connection_id": str(connector.id),
                "connection_type": broad_type,
                "provider": provider,
                "visibility": visibility,
                "latency_ms": latency_ms,
            }
        needs_database_selection = broad_type == "database" and not _selection_is_complete(
            provider=provider,
            broad_type=broad_type,
            selection=selection,
            connector_config=connector_config,
        )
        needs_object_selection = broad_type == "object_storage" and not _selection_is_complete(
            provider=provider,
            broad_type=broad_type,
            selection=selection,
            connector_config=connector_config,
        )
        should_browse = needs_database_selection or needs_object_selection
        if should_browse:
            try:
                choices, browse_message, discovery_metadata = await browse_connector_real_detailed(
                    connector.connector_type.value,
                    connector_config,
                )
                discovery_labels = build_discovery_labels(
                    connector.connector_type.value,
                    config=connector_config,
                    provider_metadata=discovery_metadata,
                    items=choices,
                )
            except Exception:
                logger.exception(
                    "connect_data_browse_failed",
                    route="/v1/data/connect",
                    connector_id=str(connector.id),
                    connector_type=connector.connector_type.value,
                )
                return {
                    "status": "failed",
                    "message": "Browse failed.",
                    "error": {
                        "code": "browse_failed",
                        "message": "Browse failed.",
                    },
                    "connection_id": str(connector.id),
                    "connection_type": broad_type,
                    "provider": provider,
                    "visibility": visibility,
                    "latency_ms": latency_ms,
                }
        else:
            choices, browse_message = [], "Selection already provided."
    else:
        success, message, latency_ms = True, "Direct dataset payload accepted.", 0
        choices, browse_message = [], "Direct dataset payload"

    if broad_type == "database":
        if not _selection_is_complete(
            provider=provider,
            broad_type=broad_type,
            selection=selection,
            connector_config=connector_config,
        ):
            if len(choices) == 1:
                selection = dict(choices[0].get("selection") or {})
            elif len(choices) > 1:
                return {
                    "status": "needs_selection",
                    "message": browse_message,
                    "connection_id": str(connector.id) if connector else None,
                    "connection_type": broad_type,
                    "provider": provider,
                    "labels": discovery_labels,
                    "discovery": discovery_metadata,
                    "visibility": visibility,
                    "choices": (
                        choices
                        if _should_return_full_database_choices(connector_config)
                        else choices[:50]
                    ),
                }
    elif broad_type == "object_storage":
        if not (
            selection.get("object_path")
            or connector_config.get("object_path")
            or connector_config.get("key")
            or connector_config.get("blob")
            or connector_config.get("blob_url")
        ):
            if len(choices) == 1:
                selection = dict(choices[0].get("selection") or {})
            elif len(choices) > 1:
                return {
                    "status": "needs_selection",
                    "message": browse_message,
                    "connection_id": str(connector.id) if connector else None,
                    "connection_type": broad_type,
                    "provider": provider,
                    "labels": discovery_labels,
                    "discovery": discovery_metadata,
                    "visibility": visibility,
                    "choices": choices[:50],
                }

    source, refreshable, direct_definition = build_source_spec(
        dataset_name=dataset_name,
        connection_type=broad_type,
        provider=provider,
        connection_config=connector_config,
        selection=selection,
        direct_payload=payload,
    )

    register_result = await _register_source_impl(
        RegisterRequest(source=source, description=description),
        auth=auth,
        dataset_name=dataset_name,
        connector_id=str(connector.id) if connector else None,
        visibility=visibility,
        owner_user_id=_auth_user_id(auth),
        owner_key_id=_auth_key_id(auth),
        description=description,
        selection=selection or None,
        connection_type=broad_type,
        provider=provider,
        refreshable=refreshable,
        source_definition=direct_definition,
        discovery_labels=discovery_labels,
        discovery_metadata=discovery_metadata,
    )

    schema = register_result.get("schema", {})
    dataset_id = register_result.get("dataset_id") or register_result.get("source_id")
    return {
        "status": "ready",
        "dataset_id": dataset_id,
        "source_id": register_result.get("source_id") or dataset_id,
        "dataset_name": dataset_name,
        "schema": schema,
        "schema_summary": {
            "row_count": schema.get("row_count"),
            "columns": len(schema.get("columns", [])),
            "roles_summary": schema.get("roles_summary", {}),
        },
        "connection_id": str(connector.id) if connector else None,
        "connection_type": broad_type,
        "provider": provider,
        "labels": discovery_labels,
        "discovery": discovery_metadata,
        "visibility": visibility,
        "selection": selection or None,
        "refreshable": refreshable,
        "latency_ms": register_result.get("latency_ms"),
        "message": message,
    }


async def refresh_dataset(
    *,
    db: AsyncSession,
    auth: AuthContext,
    dataset_id: str,
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

    if not entry.get("refreshable"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "not_refreshable",
                    "message": (
                        "This dataset cannot be refreshed because its original "
                        "input was an inline upload."
                    ),
                }
            },
        )

    payload: dict[str, Any] = {
        "connection_type": entry.get("connection_type") or "file_upload",
        "provider": entry.get("provider"),
        "connection_id": entry.get("connector_id"),
        "selection": entry.get("selection") or None,
        "dataset_name": entry.get("dataset_name") or entry.get("name") or dataset_id,
        "description": entry.get("description"),
        "visibility": entry.get("visibility") or ConnectorVisibility.PRIVATE.value,
    }
    direct = entry.get("source_definition") or {}
    if isinstance(direct, dict) and isinstance(direct.get("direct"), dict):
        payload.update(direct["direct"])

    return await connect_data(db=db, auth=auth, payload=payload)
