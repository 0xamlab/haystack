# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def _coerce_pagination(*, page: int | None, limit: int | None) -> dict[str, int]:
    params: dict[str, int] = {}
    if page is not None:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("page must be an integer greater than or equal to 1.")
        params["page"] = page
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be an integer greater than or equal to 1.")
        params["limit"] = limit
    return params


def _validate_team_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        members = data
        total = len(members)
        return {
            "members": members,
            "total": total,
            "page": 1,
            "limit": total or 1,
            "pages": 1,
        }
    if not isinstance(data, dict):
        raise TypeError(
            f"Team response must be a list or JSON object, got {type(data).__name__}."
        )
    return data


def _validate_team_role(role: str) -> str:
    if not isinstance(role, str) or not role.strip():
        raise ValueError("role must be a non-empty string.")
    normalized = role.strip()
    if normalized not in {"owner", "admin", "member", "viewer"}:
        raise ValueError("role must be one of: owner, admin, member, viewer.")
    return normalized


def _validate_team_member_email(email: str) -> str:
    if not isinstance(email, str) or not email.strip():
        raise ValueError("email must be a non-empty string.")
    normalized = email.strip()
    if "@" not in normalized:
        raise ValueError("email must contain '@'.")
    return normalized


def _validate_team_member_id(user_id: str) -> str:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string.")
    return user_id.strip()


def _validate_update_execution_policy_request(
    *,
    min_confidence: float | None,
    risk_floor: float | None,
    require_calibration: bool | None,
    allow_reexecution: bool | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if min_confidence is not None:
        if isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float)):
            raise TypeError("min_confidence must be a number between 0 and 1.")
        normalized_confidence = float(min_confidence)
        if normalized_confidence < 0.0 or normalized_confidence > 1.0:
            raise ValueError("min_confidence must be between 0 and 1.")
        payload["min_confidence"] = normalized_confidence
    if risk_floor is not None:
        if isinstance(risk_floor, bool) or not isinstance(risk_floor, (int, float)):
            raise TypeError("risk_floor must be a non-negative number.")
        normalized_floor = float(risk_floor)
        if normalized_floor < 0.0:
            raise ValueError("risk_floor must be greater than or equal to 0.")
        payload["risk_floor"] = normalized_floor
    if require_calibration is not None:
        if not isinstance(require_calibration, bool):
            raise TypeError("require_calibration must be a boolean.")
        payload["require_calibration"] = require_calibration
    if allow_reexecution is not None:
        if not isinstance(allow_reexecution, bool):
            raise TypeError("allow_reexecution must be a boolean.")
        payload["allow_reexecution"] = allow_reexecution
    if not payload:
        raise ValueError(
            "update_execution_policy() requires at least one policy field to update."
        )
    return payload


def _validate_billing_plan(plan: str | None) -> dict[str, Any]:
    if plan is None:
        return {}
    if not isinstance(plan, str) or not plan.strip():
        raise ValueError("plan must be a non-empty string when provided.")
    normalized = plan.strip()
    if normalized not in {"developer", "pro"}:
        raise ValueError("plan must be one of: developer, pro.")
    return {"plan": normalized}


_METERING_EVENT_ALLOWED_KEYS = {
    "event_type",
    "module",
    "function",
    "engine_used",
    "latency_ms",
    "success",
    "timestamp",
    "request_id",
}


def _validate_metering_request(
    *,
    device_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be a non-empty string.")
    if not isinstance(events, list) or not events:
        raise ValueError("events must be a non-empty list.")
    normalized_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TypeError(f"events[{index}] must be a JSON object.")
        unexpected_keys = sorted(set(event) - _METERING_EVENT_ALLOWED_KEYS)
        if unexpected_keys:
            raise ValueError(
                f"events[{index}] contains unsupported fields: {', '.join(unexpected_keys)}."
            )
        normalized_event: dict[str, Any] = {}
        for field_name in ("event_type", "module", "function", "engine_used", "request_id"):
            if field_name not in event:
                continue
            value = event[field_name]
            if not isinstance(value, str):
                raise TypeError(f"events[{index}].{field_name} must be a string.")
            normalized_event[field_name] = value.strip()
        if "latency_ms" in event:
            value = event["latency_ms"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"events[{index}].latency_ms must be a number.")
            normalized_event["latency_ms"] = float(value)
        if "timestamp" in event:
            value = event["timestamp"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"events[{index}].timestamp must be a number.")
            normalized_event["timestamp"] = float(value)
        if "success" in event:
            value = event["success"]
            if not isinstance(value, bool):
                raise TypeError(f"events[{index}].success must be a boolean.")
            normalized_event["success"] = value
        normalized_events.append(normalized_event)
    return {"device_id": device_id.strip(), "events": normalized_events}


def _validate_credit_refresh_request(
    *,
    device_id: str,
    billing_period: str,
    credits_used: int = 0,
) -> dict[str, Any]:
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be a non-empty string.")
    if not isinstance(billing_period, str) or len(billing_period) != 7:
        raise ValueError("billing_period must be a YYYY-MM string.")
    year_text, dash, month_text = billing_period.partition("-")
    if (
        dash != "-"
        or not year_text.isdigit()
        or len(year_text) != 4
        or not month_text.isdigit()
        or len(month_text) != 2
    ):
        raise ValueError("billing_period must be a YYYY-MM string.")
    month = int(month_text)
    if month < 1 or month > 12:
        raise ValueError("billing_period month must be between 01 and 12.")
    if isinstance(credits_used, bool) or not isinstance(credits_used, int):
        raise TypeError("credits_used must be a non-negative integer.")
    if credits_used < 0:
        raise ValueError("credits_used must be a non-negative integer.")
    return {
        "device_id": device_id.strip(),
        "billing_period": billing_period,
        "credits_used": credits_used,
    }


def list_team_members(
    client: DecisionEngineClient,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    data = client._request("GET", "/v1/team", params=params or None)
    return _validate_model("TeamListResult", _validate_team_payload(data))


def invite_team_member(
    client: DecisionEngineClient,
    *,
    email: str,
    role: str = "member",
) -> Any:
    payload = {
        "email": _validate_team_member_email(email),
        "role": _validate_team_role(role),
    }
    data = client._request("POST", "/v1/team/invite", json=payload)
    return _validate_model("TeamInviteResult", data)


def update_team_member_role(
    client: DecisionEngineClient,
    user_id: str,
    *,
    role: str,
) -> Any:
    normalized_user_id = _validate_team_member_id(user_id)
    data = client._request(
        "PATCH",
        f"/v1/team/{normalized_user_id}/role",
        json={"role": _validate_team_role(role)},
    )
    return _validate_model("TeamRoleUpdateResult", data)


def remove_team_member(client: DecisionEngineClient, user_id: str) -> Any:
    normalized_user_id = _validate_team_member_id(user_id)
    data = client._request("DELETE", f"/v1/team/{normalized_user_id}")
    if not isinstance(data, dict):
        raise TypeError(
            f"Team remove response must be a JSON object, got {type(data).__name__}."
        )
    normalized = {
        "removed": True,
        "user_id": normalized_user_id,
        **data,
    }
    return _validate_model("TeamRemoveResult", normalized)


def get_billing_info(client: DecisionEngineClient) -> Any:
    data = client._request("GET", "/v1/billing/info")
    return _validate_model("BillingInfoResult", data)


def create_billing_checkout(
    client: DecisionEngineClient,
    *,
    plan: str | None = None,
) -> Any:
    data = client._request("POST", "/v1/billing/checkout", json=_validate_billing_plan(plan))
    return _validate_model("BillingSessionResult", data)


def create_billing_portal(client: DecisionEngineClient) -> Any:
    data = client._request("POST", "/v1/billing/portal", json={})
    return _validate_model("BillingSessionResult", data)


def refresh_credits(
    client: DecisionEngineClient,
    *,
    device_id: str,
    billing_period: str,
    credits_used: int = 0,
) -> Any:
    data = client._request(
        "POST",
        "/v1/credits/refresh",
        json=_validate_credit_refresh_request(
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        ),
    )
    return _validate_model("CreditRefreshResult", data)


def ingest_metering_events(
    client: DecisionEngineClient,
    *,
    device_id: str,
    events: list[dict[str, Any]],
) -> Any:
    data = client._request(
        "POST",
        "/v1/metering",
        json=_validate_metering_request(device_id=device_id, events=events),
    )
    return _validate_model("MeteringBatchResult", data)


def get_audit_logs(
    client: DecisionEngineClient,
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
    data = client._request("GET", "/v1/audit-logs", params=params)
    return _validate_model("AuditLogResult", data)


def get_audit_log_artifacts(
    client: DecisionEngineClient,
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
    data = client._request("GET", "/v1/audit-logs/artifacts", params=params)
    return _validate_model("AuditLogResult", data)


def get_execution_policy(client: DecisionEngineClient) -> Any:
    data = client._request("GET", "/v1/execution/policy")
    return _validate_model("ExecutionPolicyResult", data)


def list_execution_policy_snapshots(client: DecisionEngineClient) -> Any:
    data = client._request("GET", "/v1/execution/policy/snapshots")
    return _validate_model("ExecutionPolicySnapshotListResult", data)


def list_devices(
    client: DecisionEngineClient,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    params = _coerce_pagination(page=page, limit=limit)
    data = client._request("GET", "/v1/device/list", params=params or None)
    return _validate_model("DeviceListResult", data)


def revoke_device(client: DecisionEngineClient, registration_id: str) -> Any:
    if not isinstance(registration_id, str) or not registration_id.strip():
        raise ValueError("registration_id must be a non-empty string.")
    data = client._request("DELETE", f"/v1/device/{registration_id}")
    return _validate_model("DeviceRevokeResult", data)


def update_execution_policy(
    client: DecisionEngineClient,
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
    data = client._request("PATCH", "/v1/execution/policy", json=payload)
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
