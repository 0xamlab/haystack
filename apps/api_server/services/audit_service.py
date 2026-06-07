"""Audit service — write and query immutable audit events."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _runtime_dir() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))


def _audit_event_dir(org_id: str) -> Path:
    return _runtime_dir() / "audit_events" / org_id


def _audit_event_path(org_id: str, event_id: str) -> Path:
    return _audit_event_dir(org_id) / f"{event_id}.parquet"


def _stable_json_dumps(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _extract_lineage_metadata(metadata: dict[str, Any] | None) -> dict[str, str | None]:
    if metadata is None:
        return {
            "policy_snapshot_id": None,
            "schema_snapshot_id": None,
            "manifest_version": None,
            "request_hash": None,
        }
    return {
        "policy_snapshot_id": str(metadata["policy_snapshot_id"])
        if metadata.get("policy_snapshot_id") is not None
        else None,
        "schema_snapshot_id": str(metadata["schema_snapshot_id"])
        if metadata.get("schema_snapshot_id") is not None
        else None,
        "manifest_version": str(metadata["manifest_version"])
        if metadata.get("manifest_version") is not None
        else None,
        "request_hash": (
            str(metadata["request_hash"])
            if metadata.get("request_hash") is not None
            else None
        ),
    }


def _persist_audit_event_artifact(
    *,
    event: Any,
    org_id: uuid.UUID,
    metadata: dict[str, Any] | None,
) -> None:
    from apps.api_server.services.runtime_internal_contracts import (
        AuditEventRecord,
        parquet_bytes_from_records,
    )

    metadata_json = _stable_json_dumps(metadata)
    lineage = _extract_lineage_metadata(metadata)
    created_at = getattr(event, "created_at", None) or datetime.now(UTC)
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        created_at = created_at.replace(tzinfo=UTC)
    workspace_id = getattr(event, "workspace_id", None)
    workspace_id_str = str(workspace_id) if workspace_id else None
    content_payload = {
        "event_id": str(event.id),
        "org_id": str(org_id),
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_email": event.actor_email,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "ip_address": event.ip_address,
        "result": event.result,
        "metadata_json": metadata_json,
        **lineage,
        "created_at": created_at.astimezone(UTC).isoformat(),
        "workspace_id": workspace_id_str,
    }
    content_hash = hashlib.sha256(
        json.dumps(
            content_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    record = AuditEventRecord(
        event_id=str(event.id),
        org_id=str(org_id),
        actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
        actor_email=event.actor_email,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        ip_address=event.ip_address,
        result=event.result,
        metadata_json=metadata_json,
        policy_snapshot_id=lineage["policy_snapshot_id"],
        schema_snapshot_id=lineage["schema_snapshot_id"],
        manifest_version=lineage["manifest_version"],
        request_hash=lineage["request_hash"],
        content_hash=content_hash,
        created_at=created_at,
        workspace_id=workspace_id_str,
    )
    path = _audit_event_path(str(org_id), str(event.id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(parquet_bytes_from_records([record], record_type=AuditEventRecord))


def _read_audit_event_artifact(path: Path) -> list[Any]:
    from apps.api_server.services.runtime_internal_contracts import (
        AuditEventRecord,
        table_from_parquet_bytes_tolerant,
        validate_table_schema,
    )

    # Tolerant read: pre-#7 artifacts lack the workspace_id column; the tolerant reader
    # backfills it as null (org-wide/legacy) so the strict validator + model parse succeed.
    table = table_from_parquet_bytes_tolerant(path.read_bytes(), AuditEventRecord)
    validate_table_schema(table, AuditEventRecord)
    return [AuditEventRecord.model_validate(row) for row in table.to_pylist()]


def query_audit_event_artifacts(
    *,
    org_id: str,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
    content_hash: str | None = None,
    workspace_id: str | None = None,
) -> list[Any]:
    directory = _audit_event_dir(org_id)
    if not directory.exists():
        return []

    def _matches(record: Any) -> bool:
        # Workspace gate (sub-tenancy): a None workspace_id is org-wide and sees everything
        # (incl. legacy records with no workspace_id); a scoped caller sees only its own
        # workspace's records — legacy (None) records are invisible to a scoped caller.
        if workspace_id is not None and str(getattr(record, "workspace_id", None) or "") != str(
            workspace_id
        ):
            return False
        if actor_email is not None and record.actor_email != actor_email:
            return False
        if action is not None and record.action != action:
            return False
        if resource_type is not None and record.resource_type != resource_type:
            return False
        if result is not None and record.result != result:
            return False
        if policy_snapshot_id is not None and record.policy_snapshot_id != policy_snapshot_id:
            return False
        if schema_snapshot_id is not None and record.schema_snapshot_id != schema_snapshot_id:
            return False
        if manifest_version is not None and record.manifest_version != manifest_version:
            return False
        if request_hash is not None and record.request_hash != request_hash:
            return False
        if content_hash is not None and record.content_hash != content_hash:
            return False
        return True

    records: list[Any] = []
    for path in sorted(directory.glob("*.parquet")):
        for record in _read_audit_event_artifact(path):
            if _matches(record):
                records.append(record)
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


async def write_audit_event(
    db: AsyncSession,
    org_id: uuid.UUID,
    action: str,
    actor_email: str = "system",
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    result: str = "success",
    metadata: dict[str, Any] | None = None,
    workspace_id: uuid.UUID | None = None,
) -> None:
    """Write an audit event — fire-and-forget, never raises."""
    async def _write_once() -> None:
        from apps.api_server.models.audit_event import AuditEvent

        metadata_json = _stable_json_dumps(metadata)

        event = AuditEvent(
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            result=result,
            metadata_json=metadata_json,
        )
        db.add(event)
        await db.flush()
        _persist_audit_event_artifact(event=event, org_id=org_id, metadata=metadata)
        logger.debug("audit_event_written", action=action, org_id=str(org_id))

    try:
        if isinstance(db, AsyncSession):
            async with db.begin_nested():
                await _write_once()
        else:
            await _write_once()
    except Exception as exc:
        # Audit writes must never break the main flow.
        logger.error("audit_event_write_failed", action=action, error=str(exc))


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
