"""MCP tools for team, audit-log, and execution-policy control-plane surfaces."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_TEAM_MEMBERS_SPEC: dict[str, Any] = {
    "name": "list_team_members",
    "description": "List team members for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
}

INVITE_TEAM_MEMBER_SPEC: dict[str, Any] = {
    "name": "invite_team_member",
    "description": "Invite a team member to the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "minLength": 3},
            "role": {"type": "string", "enum": ["owner", "admin", "member", "viewer"]},
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

UPDATE_TEAM_MEMBER_ROLE_SPEC: dict[str, Any] = {
    "name": "update_team_member_role",
    "description": "Update one current organization team member role by user id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "minLength": 1},
            "role": {"type": "string", "enum": ["owner", "admin", "member", "viewer"]},
        },
        "required": ["user_id", "role"],
        "additionalProperties": False,
    },
}

REMOVE_TEAM_MEMBER_SPEC: dict[str, Any] = {
    "name": "remove_team_member",
    "description": "Remove one team member from the current organization by user id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "minLength": 1},
        },
        "required": ["user_id"],
        "additionalProperties": False,
    },
}

LIST_DEVICES_SPEC: dict[str, Any] = {
    "name": "list_devices",
    "description": "List registered devices for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "additionalProperties": False,
    },
}

REVOKE_DEVICE_SPEC: dict[str, Any] = {
    "name": "revoke_device",
    "description": "Revoke one registered device by registration id for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "registration_id": {"type": "string", "minLength": 1},
        },
        "required": ["registration_id"],
        "additionalProperties": False,
    },
}

GET_AUDIT_LOGS_SPEC: dict[str, Any] = {
    "name": "get_audit_logs",
    "description": "Get paginated audit logs for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "actor_email": {"type": "string", "minLength": 1},
            "action": {"type": "string", "minLength": 1},
            "resource_type": {"type": "string", "minLength": 1},
            "result": {"type": "string", "minLength": 1},
            "policy_snapshot_id": {"type": "string", "minLength": 1},
            "schema_snapshot_id": {"type": "string", "minLength": 1},
            "manifest_version": {"type": "string", "minLength": 1},
            "request_hash": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

GET_AUDIT_LOG_ARTIFACTS_SPEC: dict[str, Any] = {
    "name": "get_audit_log_artifacts",
    "description": "Get paginated immutable audit-log artifacts for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "actor_email": {"type": "string", "minLength": 1},
            "action": {"type": "string", "minLength": 1},
            "resource_type": {"type": "string", "minLength": 1},
            "result": {"type": "string", "minLength": 1},
            "policy_snapshot_id": {"type": "string", "minLength": 1},
            "schema_snapshot_id": {"type": "string", "minLength": 1},
            "manifest_version": {"type": "string", "minLength": 1},
            "request_hash": {"type": "string", "minLength": 1},
            "content_hash": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

GET_EXECUTION_POLICY_SPEC: dict[str, Any] = {
    "name": "get_execution_policy",
    "description": "Get the current autonomous execution policy for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_EXECUTION_POLICY_SNAPSHOTS_SPEC: dict[str, Any] = {
    "name": "list_execution_policy_snapshots",
    "description": "List persisted execution-policy snapshots for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_BILLING_INFO_SPEC: dict[str, Any] = {
    "name": "get_billing_info",
    "description": "Get current billing plan and subscription info for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_BILLING_CHECKOUT_SPEC: dict[str, Any] = {
    "name": "create_billing_checkout",
    "description": "Create a Stripe Checkout session for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "plan": {"type": "string", "enum": ["developer", "pro"]},
        },
        "additionalProperties": False,
    },
}

CREATE_BILLING_PORTAL_SPEC: dict[str, Any] = {
    "name": "create_billing_portal",
    "description": "Create a Stripe Billing Portal session for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

REFRESH_CREDITS_SPEC: dict[str, Any] = {
    "name": "refresh_credits",
    "description": "Issue a compatibility credit batch for a quota-governed managed runtime.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "minLength": 1},
            "billing_period": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
            "credits_used": {"type": "integer", "minimum": 0},
        },
        "required": ["device_id", "billing_period"],
        "additionalProperties": False,
    },
}

INGEST_METERING_EVENTS_SPEC: dict[str, Any] = {
    "name": "ingest_metering_events",
    "description": "Ingest an explicitly enabled managed-runtime analytics batch.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "minLength": 1},
            "events": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "event_type": {"type": "string"},
                        "module": {"type": "string"},
                        "function": {"type": "string"},
                        "engine_used": {"type": "string"},
                        "latency_ms": {"type": "number"},
                        "success": {"type": "boolean"},
                        "timestamp": {"type": "number"},
                        "request_id": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "required": ["device_id", "events"],
        "additionalProperties": False,
    },
}

UPDATE_EXECUTION_POLICY_SPEC: dict[str, Any] = {
    "name": "update_execution_policy",
    "description": "Update one or more execution-policy thresholds for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "min_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "risk_floor": {"type": "number", "minimum": 0},
            "require_calibration": {"type": "boolean"},
            "allow_reexecution": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
}


def _positive_int(arguments: dict[str, Any], field_name: str) -> int | None:
    value = arguments.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _optional_non_empty_string(arguments: dict[str, Any], field_name: str) -> str | None:
    value = arguments.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


async def list_team_members_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    page = _positive_int(arguments, "page")
    limit = _positive_int(arguments, "limit")
    if page is not None:
        params["page"] = page
    if limit is not None:
        params["limit"] = limit
    return json.dumps(await api("GET", "/v1/team", params=params or None), indent=2)


async def invite_team_member_handler(arguments: dict[str, Any]) -> str:
    email = arguments.get("email")
    if not isinstance(email, str) or not email.strip() or "@" not in email:
        raise ValueError("invite_team_member requires a valid email.")
    role = arguments.get("role", "member")
    if role not in {"owner", "admin", "member", "viewer"}:
        raise ValueError("invite_team_member.role must be one of: owner, admin, member, viewer.")
    return json.dumps(
        await api("POST", "/v1/team/invite", json={"email": email.strip(), "role": role}),
        indent=2,
    )


async def update_team_member_role_handler(arguments: dict[str, Any]) -> str:
    user_id = arguments.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("update_team_member_role requires a non-empty user_id.")
    role = arguments.get("role")
    if role not in {"owner", "admin", "member", "viewer"}:
        raise ValueError(
            "update_team_member_role.role must be one of: owner, admin, member, viewer."
        )
    return json.dumps(
        await api("PATCH", f"/v1/team/{user_id.strip()}/role", json={"role": role}),
        indent=2,
    )


async def remove_team_member_handler(arguments: dict[str, Any]) -> str:
    user_id = arguments.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("remove_team_member requires a non-empty user_id.")
    payload = await api("DELETE", f"/v1/team/{user_id.strip()}")
    normalized = {"removed": True, "user_id": user_id.strip()}
    if isinstance(payload, dict):
        normalized.update(payload)
    return json.dumps(normalized, indent=2)


async def list_devices_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    page = _positive_int(arguments, "page")
    limit = _positive_int(arguments, "limit")
    if page is not None:
        params["page"] = page
    if limit is not None:
        params["limit"] = limit
    return json.dumps(await api("GET", "/v1/device/list", params=params or None), indent=2)


async def revoke_device_handler(arguments: dict[str, Any]) -> str:
    registration_id = arguments.get("registration_id")
    if not isinstance(registration_id, str) or not registration_id.strip():
        raise ValueError("revoke_device requires a non-empty registration_id.")
    return json.dumps(await api("DELETE", f"/v1/device/{registration_id}"), indent=2)


async def get_audit_logs_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    page = _positive_int(arguments, "page")
    limit = _positive_int(arguments, "limit")
    if page is not None:
        params["page"] = page
    if limit is not None:
        params["limit"] = limit
    for field_name in (
        "actor_email",
        "action",
        "resource_type",
        "result",
        "policy_snapshot_id",
        "schema_snapshot_id",
        "manifest_version",
        "request_hash",
    ):
        value = _optional_non_empty_string(arguments, field_name)
        if value is not None:
            params[field_name] = value
    return json.dumps(await api("GET", "/v1/audit-logs", params=params or None), indent=2)


async def get_audit_log_artifacts_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    page = _positive_int(arguments, "page")
    limit = _positive_int(arguments, "limit")
    if page is not None:
        params["page"] = page
    if limit is not None:
        params["limit"] = limit
    for field_name in (
        "actor_email",
        "action",
        "resource_type",
        "result",
        "policy_snapshot_id",
        "schema_snapshot_id",
        "manifest_version",
        "request_hash",
        "content_hash",
    ):
        value = _optional_non_empty_string(arguments, field_name)
        if value is not None:
            params[field_name] = value
    return json.dumps(await api("GET", "/v1/audit-logs/artifacts", params=params or None), indent=2)


async def get_execution_policy_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_execution_policy does not accept arguments.")
    return json.dumps(await api("GET", "/v1/execution/policy"), indent=2)


async def list_execution_policy_snapshots_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_execution_policy_snapshots does not accept arguments.")
    return json.dumps(await api("GET", "/v1/execution/policy/snapshots"), indent=2)


async def get_billing_info_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_billing_info does not accept arguments.")
    return json.dumps(await api("GET", "/v1/billing/info"), indent=2)


async def create_billing_checkout_handler(arguments: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    if "plan" in arguments:
        plan = arguments["plan"]
        if plan not in {"developer", "pro"}:
            raise ValueError("create_billing_checkout.plan must be one of: developer, pro.")
        payload["plan"] = plan
    return json.dumps(await api("POST", "/v1/billing/checkout", json=payload), indent=2)


async def create_billing_portal_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("create_billing_portal does not accept arguments.")
    return json.dumps(await api("POST", "/v1/billing/portal", json={}), indent=2)


async def refresh_credits_handler(arguments: dict[str, Any]) -> str:
    device_id = arguments.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("refresh_credits requires a non-empty device_id.")
    billing_period = arguments.get("billing_period")
    if not isinstance(billing_period, str) or len(billing_period) != 7:
        raise ValueError("refresh_credits requires a YYYY-MM billing_period.")
    year_text, dash, month_text = billing_period.partition("-")
    if (
        dash != "-"
        or not year_text.isdigit()
        or len(year_text) != 4
        or not month_text.isdigit()
        or len(month_text) != 2
    ):
        raise ValueError("refresh_credits requires a YYYY-MM billing_period.")
    month = int(month_text)
    if month < 1 or month > 12:
        raise ValueError("refresh_credits.billing_period month must be between 01 and 12.")
    credits_used = arguments.get("credits_used", 0)
    if isinstance(credits_used, bool) or not isinstance(credits_used, int) or credits_used < 0:
        raise ValueError("refresh_credits.credits_used must be a non-negative integer.")
    payload = {
        "device_id": device_id.strip(),
        "billing_period": billing_period,
        "credits_used": credits_used,
    }
    return json.dumps(await api("POST", "/v1/credits/refresh", json=payload), indent=2)


async def ingest_metering_events_handler(arguments: dict[str, Any]) -> str:
    device_id = arguments.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("ingest_metering_events requires a non-empty device_id.")
    events = arguments.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("ingest_metering_events requires a non-empty events list.")
    allowed_keys = {
        "event_type",
        "module",
        "function",
        "engine_used",
        "latency_ms",
        "success",
        "timestamp",
        "request_id",
    }
    normalized_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"ingest_metering_events.events[{index}] must be a JSON object.")
        unexpected_keys = sorted(set(event) - allowed_keys)
        if unexpected_keys:
            raise ValueError(
                "ingest_metering_events.events"
                f"[{index}] contains unsupported fields: {', '.join(unexpected_keys)}."
            )
        normalized_event: dict[str, Any] = {}
        for key in ("event_type", "module", "function", "engine_used", "request_id"):
            if key in event:
                value = event[key]
                if not isinstance(value, str):
                    raise ValueError(f"ingest_metering_events.events[{index}].{key} must be a string.")
                normalized_event[key] = value.strip()
        for key in ("latency_ms", "timestamp"):
            if key in event:
                value = event[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"ingest_metering_events.events[{index}].{key} must be a number.")
                normalized_event[key] = float(value)
        if "success" in event:
            value = event["success"]
            if not isinstance(value, bool):
                raise ValueError(
                    f"ingest_metering_events.events[{index}].success must be a boolean."
                )
            normalized_event["success"] = value
        normalized_events.append(normalized_event)
    payload = {"device_id": device_id.strip(), "events": normalized_events}
    return json.dumps(await api("POST", "/v1/metering", json=payload), indent=2)


async def update_execution_policy_handler(arguments: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    if "min_confidence" in arguments:
        value = arguments["min_confidence"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("min_confidence must be a number between 0 and 1.")
        payload["min_confidence"] = float(value)
    if "risk_floor" in arguments:
        value = arguments["risk_floor"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("risk_floor must be a non-negative number.")
        payload["risk_floor"] = float(value)
    if "require_calibration" in arguments:
        value = arguments["require_calibration"]
        if not isinstance(value, bool):
            raise ValueError("require_calibration must be a boolean.")
        payload["require_calibration"] = value
    if "allow_reexecution" in arguments:
        value = arguments["allow_reexecution"]
        if not isinstance(value, bool):
            raise ValueError("allow_reexecution must be a boolean.")
        payload["allow_reexecution"] = value
    if not payload:
        raise ValueError("update_execution_policy requires at least one update field.")
    return json.dumps(await api("PATCH", "/v1/execution/policy", json=payload), indent=2)
