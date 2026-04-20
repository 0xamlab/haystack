"""Audit service — write immutable audit events to the database."""
import json
import uuid
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


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
) -> None:
    """Write an audit event — fire-and-forget, never raises."""
    try:
        from apps.api_server.models.audit_event import AuditEvent

        event = AuditEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            result=result,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
        await db.flush()
        logger.debug("audit_event_written", action=action, org_id=str(org_id))
    except Exception as exc:
        # Audit writes must never break the main flow
        logger.error("audit_event_write_failed", action=action, error=str(exc))


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
