from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_loader import validate_model as _validate_model
from .client_control_plane_surface import (
    _validate_billing_plan,
    _validate_credit_refresh_request,
    _validate_metering_request,
    _coerce_pagination,
    _validate_team_member_email,
    _validate_team_member_id,
    _validate_team_payload,
    _validate_team_role,
    _validate_update_execution_policy_request,
)

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def list_team_members(
    client: AsyncDecisionEngineClient,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    data = await client._request("GET", "/v1/team", params=params or None)
    return _validate_model("TeamListResult", _validate_team_payload(data))


async def invite_team_member(
    client: AsyncDecisionEngineClient,
    *,
    email: str,
    role: str = "member",
) -> Any:
    data = await client._request(
        "POST",
        "/v1/team/invite",
        json={"email": _validate_team_member_email(email), "role": _validate_team_role(role)},
    )
    return _validate_model("TeamInviteResult", data)


async def update_team_member_role(
    client: AsyncDecisionEngineClient,
    user_id: str,
    *,
    role: str,
) -> Any:
    normalized_user_id = _validate_team_member_id(user_id)
    data = await client._request(
        "PATCH",
        f"/v1/team/{normalized_user_id}/role",
        json={"role": _validate_team_role(role)},
    )
    return _validate_model("TeamRoleUpdateResult", data)


async def remove_team_member(client: AsyncDecisionEngineClient, user_id: str) -> Any:
    normalized_user_id = _validate_team_member_id(user_id)
    data = await client._request("DELETE", f"/v1/team/{normalized_user_id}")
    if not isinstance(data, dict):
        raise TypeError(
            f"Team remove response must be a JSON object, got {type(data).__name__}."
        )
    normalized = {"removed": True, "user_id": normalized_user_id, **data}
    return _validate_model("TeamRemoveResult", normalized)


async def get_billing_info(client: AsyncDecisionEngineClient) -> Any:
    data = await client._request("GET", "/v1/billing/info")
    return _validate_model("BillingInfoResult", data)


async def create_billing_checkout(
    client: AsyncDecisionEngineClient,
    *,
    plan: str | None = None,
) -> Any:
    data = await client._request("POST", "/v1/billing/checkout", json=_validate_billing_plan(plan))
    return _validate_model("BillingSessionResult", data)


async def create_billing_portal(client: AsyncDecisionEngineClient) -> Any:
    data = await client._request("POST", "/v1/billing/portal", json={})
    return _validate_model("BillingSessionResult", data)


async def refresh_credits(
    client: AsyncDecisionEngineClient,
    *,
    device_id: str,
    billing_period: str,
    credits_used: int = 0,
) -> Any:
    data = await client._request(
        "POST",
        "/v1/credits/refresh",
        json=_validate_credit_refresh_request(
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        ),
    )
    return _validate_model("CreditRefreshResult", data)


async def ingest_metering_events(
    client: AsyncDecisionEngineClient,
    *,
    device_id: str,
    events: list[dict[str, Any]],
) -> Any:
    data = await client._request(
        "POST",
        "/v1/metering",
        json=_validate_metering_request(device_id=device_id, events=events),
    )
    return _validate_model("MeteringBatchResult", data)


async def get_audit_logs(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    optional_filters = {
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "result": result,
        "policy_snapshot_id": policy_snapshot_id,
        "schema_snapshot_id": schema_snapshot_id,
        "manifest_version": manifest_version,
        "request_hash": request_hash,
    }
    for field_name, value in optional_filters.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string when provided.")
        params[field_name] = value.strip()
    data = await client._request("GET", "/v1/audit-logs", params=params)
    return _validate_model("AuditLogResult", data)


async def get_audit_log_artifacts(
    client: AsyncDecisionEngineClient,
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
    content_hash: str | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    optional_filters = {
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "result": result,
        "policy_snapshot_id": policy_snapshot_id,
        "schema_snapshot_id": schema_snapshot_id,
        "manifest_version": manifest_version,
        "request_hash": request_hash,
        "content_hash": content_hash,
    }
    for field_name, value in optional_filters.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string when provided.")
        params[field_name] = value.strip()
    data = await client._request("GET", "/v1/audit-logs/artifacts", params=params)
    return _validate_model("AuditLogResult", data)


async def get_execution_policy(client: AsyncDecisionEngineClient) -> Any:
    data = await client._request("GET", "/v1/execution/policy")
    return _validate_model("ExecutionPolicyResult", data)


async def list_execution_policy_snapshots(client: AsyncDecisionEngineClient) -> Any:
    data = await client._request("GET", "/v1/execution/policy/snapshots")
    return _validate_model("ExecutionPolicySnapshotListResult", data)


async def list_devices(
    client: AsyncDecisionEngineClient,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    data = await client._request("GET", "/v1/device/list", params=params or None)
    return _validate_model("DeviceListResult", data)


async def revoke_device(client: AsyncDecisionEngineClient, registration_id: str) -> Any:
    if not isinstance(registration_id, str) or not registration_id.strip():
        raise ValueError("registration_id must be a non-empty string.")
    data = await client._request("DELETE", f"/v1/device/{registration_id}")
    return _validate_model("DeviceRevokeResult", data)


async def update_execution_policy(
    client: AsyncDecisionEngineClient,
    *,
    min_confidence: float | None = None,
    risk_floor: float | None = None,
    require_calibration: bool | None = None,
    allow_reexecution: bool | None = None,
) -> Any:
    payload = _validate_update_execution_policy_request(
        min_confidence=min_confidence,
        risk_floor=risk_floor,
        require_calibration=require_calibration,
        allow_reexecution=allow_reexecution,
    )
    data = await client._request("PATCH", "/v1/execution/policy", json=payload)
    return _validate_model("ExecutionPolicyResult", data)


__all__ = [
    "create_billing_checkout",
    "create_billing_portal",
    "refresh_credits",
    "ingest_metering_events",
    "get_billing_info",
    "list_devices",
    "get_audit_logs",
    "get_audit_log_artifacts",
    "get_execution_policy",
    "list_execution_policy_snapshots",
    "invite_team_member",
    "list_team_members",
    "remove_team_member",
    "revoke_device",
    "update_team_member_role",
    "update_execution_policy",
]
