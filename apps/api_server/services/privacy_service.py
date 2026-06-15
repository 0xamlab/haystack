from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select

from apps.api_server.config import get_settings
from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.audit_event import AuditAction, AuditEvent
from apps.api_server.services.audit_service import write_audit_event
from apps.privacy_policy import EgressDecision

PRIVACY_RESOURCE_TYPE = "privacy_egress"


async def record_service_egress_event(
    *,
    org_id: uuid.UUID,
    decision: EgressDecision,
    actor_email: str = "system",
) -> None:
    action = (
        AuditAction.PRIVACY_EGRESS_ALLOW.value
        if decision.decision == "allow"
        else AuditAction.PRIVACY_EGRESS_BLOCK.value
    )
    async with AsyncSessionLocal() as db:
        await write_audit_event(
            db,
            org_id=org_id,
            action=action,
            actor_email=actor_email,
            resource_type=PRIVACY_RESOURCE_TYPE,
            resource_id=decision.destination_host_hash[:16],
            result="success" if decision.decision == "allow" else "blocked",
            metadata=decision.to_audit_metadata(),
        )
        await db.commit()


def _parse_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        data = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _local_license_active() -> bool:
    try:
        from apps.runtime.license import local_license_status

        return local_license_status().get("active", False) is True
    except Exception:
        return False


async def get_egress_policy_payload() -> dict[str, Any]:
    policy = get_settings().privacy_policy
    payload = policy.as_report_dict()
    payload["algenta_owned_host_patterns"] = list(policy.algenta_owned_hosts)
    payload["vpc_mode_note"] = (
        "vpc remains a managed deployment mode and may use Codna-operated control-plane services "
        "unless private-profile flags explicitly override that behavior."
    )
    return payload


async def list_egress_events(
    *,
    org_id: uuid.UUID,
    page: int,
    limit: int,
) -> dict[str, Any]:
    base_q = select(AuditEvent).where(
        AuditEvent.org_id == org_id,
        AuditEvent.resource_type == PRIVACY_RESOURCE_TYPE,
        AuditEvent.action.in_(
            [AuditAction.PRIVACY_EGRESS_ALLOW.value, AuditAction.PRIVACY_EGRESS_BLOCK.value]
        ),
    )
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one()
        offset = (page - 1) * limit
        events = (
            (
                await db.execute(
                    base_q.order_by(desc(AuditEvent.created_at)).offset(offset).limit(limit)
                )
            )
            .scalars()
            .all()
        )

    entries = []
    for event in events:
        metadata = _parse_metadata(event.metadata_json)
        entries.append(
            {
                "surface": metadata.get("surface", "unknown"),
                "egress_class": metadata.get("egress_class", "undeclared_public"),
                "destination_host_hash": metadata.get("destination_host_hash", ""),
                "destination_host_redacted": metadata.get("destination_host_redacted", "public-host"),
                "decision": metadata.get("decision", "deny"),
                "reason": metadata.get("reason", ""),
                "timestamp": event.created_at,
                "deployment_mode": metadata.get("deployment_mode", get_settings().privacy_policy.deployment_mode),
                "service_name": metadata.get("service_name", "api-server"),
                "request_id": metadata.get("request_id"),
            }
        )

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
    }


async def get_privacy_report(*, org_id: uuid.UUID) -> dict[str, Any]:
    policy = get_settings().privacy_policy
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    base_q = select(AuditEvent).where(
        AuditEvent.org_id == org_id,
        AuditEvent.resource_type == PRIVACY_RESOURCE_TYPE,
        AuditEvent.created_at >= cutoff,
        AuditEvent.action.in_(
            [AuditAction.PRIVACY_EGRESS_ALLOW.value, AuditAction.PRIVACY_EGRESS_BLOCK.value]
        ),
    )
    async with AsyncSessionLocal() as db:
        events = ((await db.execute(base_q.order_by(desc(AuditEvent.created_at)))).scalars().all())

    algenta_owned_egress_count = 0
    blocked_egress_attempt_count = 0
    last_outbound_request_at: datetime | None = None
    last_algenta_owned_egress_at: datetime | None = None

    for event in events:
        metadata = _parse_metadata(event.metadata_json)
        created_at = event.created_at
        if last_outbound_request_at is None or created_at > last_outbound_request_at:
            last_outbound_request_at = created_at
        decision = metadata.get("decision")
        egress_class = metadata.get("egress_class")
        if decision == "deny":
            blocked_egress_attempt_count += 1
        if decision == "allow" and egress_class == "algenta_cloud":
            algenta_owned_egress_count += 1
            if last_algenta_owned_egress_at is None or created_at > last_algenta_owned_egress_at:
                last_algenta_owned_egress_at = created_at

    return {
        "deployment_mode": policy.deployment_mode,
        "algenta_cloud_enabled": policy.algenta_cloud_enabled,
        "vendor_telemetry_enabled": policy.vendor_telemetry_enabled,
        "customer_connector_egress_enabled": policy.customer_connector_egress_enabled,
        "undeclared_public_egress_allowed": policy.undeclared_public_egress_allowed,
        "local_license_required": policy.require_local_license,
        "local_license_active": _local_license_active(),
        "mandatory_heartbeat_enabled": policy.mandatory_heartbeat_enabled,
        "metering_flush_enabled": policy.metering_flush_enabled,
        "telemetry_mode": policy.telemetry_mode,
        "metering_mode": policy.metering_mode,
        "algenta_owned_egress_count_24h": algenta_owned_egress_count,
        "blocked_egress_attempt_count_24h": blocked_egress_attempt_count,
        "last_outbound_request_at": last_outbound_request_at,
        "last_algenta_owned_egress_at": last_algenta_owned_egress_at,
    }
