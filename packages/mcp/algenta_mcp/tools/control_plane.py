"""MCP tools for team, audit-log, and execution-policy control-plane surfaces."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_TEAM_MEMBERS_SPEC: dict[str, Any] = {
    "name": "list_team_members",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the active users of the caller's organization with user_id, name, email, "
        "role, and status. Called with no arguments it returns the full member array; "
        "passing page or limit switches to a paginated envelope {members, total, page, "
        "limit, pages} (defaults page 1, limit 25). Use the returned user_id with "
        "update_team_member_role or remove_team_member. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based page number; enables the paginated envelope.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Members per page (default 25 when paginating).",
            },
        },
        "additionalProperties": False,
    },
}

INVITE_TEAM_MEMBER_SPEC: dict[str, Any] = {
    "name": "invite_team_member",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Invite someone to the caller's organization by email and return the pending "
        "invite. This creates a pending invitation, emails an accept link, and reserves a "
        "seat until the invite is accepted. The caller's API key must have an admin role "
        "and the plan must have seats available — single-seat plans fail with "
        "seats_not_available. Use list_team_members to see who is already in the org. "
        "Role defaults to member."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "minLength": 3,
                "description": "Email address the invite link is sent to.",
            },
            "role": {
                "type": "string",
                "enum": ["owner", "admin", "member", "viewer"],
                "description": "Org role granted on accept; defaults to member.",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

UPDATE_TEAM_MEMBER_ROLE_SPEC: dict[str, Any] = {
    "name": "update_team_member_role",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Change one organization member's role by user_id (find ids with "
        "list_team_members). Requires an admin API key. Guardrails: you cannot change your "
        "own role (self_role_change_forbidden), only an owner can grant the owner role "
        "(owner_grant_forbidden), and demoting the last active owner is refused "
        "(last_owner). An unknown user_id fails with not_found. Returns the updated user_id "
        "and a confirmation message. Use remove_team_member to take the member out of the "
        "organization instead."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "minLength": 1,
                "description": "Target member's user_id from list_team_members.",
            },
            "role": {
                "type": "string",
                "enum": ["owner", "admin", "member", "viewer"],
                "description": "New org role for the member.",
            },
        },
        "required": ["user_id", "role"],
        "additionalProperties": False,
    },
}

REMOVE_TEAM_MEMBER_SPEC: dict[str, Any] = {
    "name": "remove_team_member",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Remove one member from the caller's organization by user_id (find ids with "
        "list_team_members). Requires an admin API key. The member is suspended immediately "
        "— their API keys stop authenticating at once — and removing the last active owner "
        "is refused (last_owner). An unknown user_id fails with not_found. Returns removed: "
        "true with the removed user_id. Use update_team_member_role to change access "
        "without removing the member."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "minLength": 1,
                "description": "Member's user_id from list_team_members.",
            },
        },
        "required": ["user_id"],
        "additionalProperties": False,
    },
}

LIST_DEVICES_SPEC: dict[str, Any] = {
    "name": "list_devices",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the devices registered to the caller's organization, paginated, together "
        "with the plan's device_limit and plan name. Requires an API-key identity "
        "(user-session keys fail with api_key_identity_required). Use a device's "
        "registration_id with revoke_device to free a slot. Read-only. Returns devices, "
        "device_count, total, page, pages, device_limit, and plan."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Devices per page, up to 200; defaults to 25.",
            },
        },
        "additionalProperties": False,
    },
}

REVOKE_DEVICE_SPEC: dict[str, Any] = {
    "name": "revoke_device",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Revoke one registered device by registration_id (find ids with list_devices), "
        "freeing one device slot. The device loses access on its next license refresh. An "
        "unknown registration_id fails with not_found. Returns revoked: true with the "
        "registration_id. Use list_devices to find registration ids."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "registration_id": {
                "type": "string",
                "minLength": 1,
                "description": "Device registration id from list_devices.",
            },
        },
        "required": ["registration_id"],
        "additionalProperties": False,
    },
}

GET_AUDIT_LOGS_SPEC: dict[str, Any] = {
    "name": "get_audit_logs",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Query the organization's audit-event log, newest first, with pagination "
        "(defaults page 1, limit 25) and exact-match filters. Every entry records who "
        "did what to which resource with which result; an org with no events returns an "
        "honest empty page. Requires an admin API key. Use get_audit_log_artifacts for "
        "the immutable Parquet artifact copy, and filter by policy_snapshot_id, "
        "schema_snapshot_id, manifest_version, or request_hash to trace one execution. "
        "Read-only. Returns entries plus total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Entries per page, up to 100; defaults to 25.",
            },
            "actor_email": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events by this actor email.",
            },
            "action": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events with this action, e.g. execution_policy.update.",
            },
            "resource_type": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events against this resource type.",
            },
            "result": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events with this result value.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events tied to this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events tied to this schema snapshot.",
            },
            "manifest_version": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events tied to this runtime manifest version.",
            },
            "request_hash": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only events tied to this request hash.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AUDIT_LOG_ARTIFACTS_SPEC: dict[str, Any] = {
    "name": "get_audit_log_artifacts",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Query the organization's immutable Parquet audit-log artifacts with pagination "
        "(defaults page 1, limit 25) and exact-match filters, including content_hash for "
        "pinpointing one artifact. Artifacts are the tamper-evident copy of the audit "
        "trail; use get_audit_logs for the live audit-event table. Requires an admin API "
        "key; a workspace-scoped key sees only its own workspace's artifacts. Read-only. "
        "Returns entries plus total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Entries per page, up to 100; defaults to 25.",
            },
            "actor_email": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts by this actor email.",
            },
            "action": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts with this action.",
            },
            "resource_type": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts against this resource type.",
            },
            "result": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts with this result value.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts tied to this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts tied to this schema snapshot.",
            },
            "manifest_version": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts tied to this runtime manifest version.",
            },
            "request_hash": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only artifacts tied to this request hash.",
            },
            "content_hash": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only the artifact with this content hash.",
            },
        },
        "additionalProperties": False,
    },
}

GET_EXECUTION_POLICY_SPEC: dict[str, Any] = {
    "name": "get_execution_policy",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the current autonomous execution policy for the active organization. Read-only "
        "and non-destructive; not separately rate-limited. Read this before "
        "update_execution_policy. Returns min_confidence, risk_floor, require_calibration, "
        "allow_reexecution, and the current snapshot metadata."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_EXECUTION_POLICY_SNAPSHOTS_SPEC: dict[str, Any] = {
    "name": "list_execution_policy_snapshots",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the organization's persisted execution-policy snapshots in revision order "
        "with total_snapshots. Every policy update writes a new snapshot, so these ids "
        "are the lineage trail for replay and audit inspection; get_execution_policy "
        "returns only the current one. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_BILLING_INFO_SPEC: dict[str, Any] = {
    "name": "get_billing_info",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get current billing plan and subscription info for the active organization. "
        "Read-only and non-destructive; not separately rate-limited. Use "
        "create_billing_checkout or create_billing_portal to change anything. Returns plan, "
        "stripe_customer_id, subscription_status, and current_period_end."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_BILLING_CHECKOUT_SPEC: dict[str, Any] = {
    "name": "create_billing_checkout",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Create a Stripe Checkout session for the active organization and return its "
        "hosted checkout URL. The user completes the purchase in the browser; nothing is "
        "charged by this call itself. Requires an owner API key. plan defaults to "
        "developer; an unsupported plan fails with invalid_plan. Use get_billing_info to "
        "check the current plan and create_billing_portal to manage an existing "
        "subscription."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "string",
                "enum": ["developer", "pro"],
                "description": "Plan to purchase; defaults to developer.",
            },
        },
        "additionalProperties": False,
    },
}

CREATE_BILLING_PORTAL_SPEC: dict[str, Any] = {
    "name": "create_billing_portal",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Create a Stripe Billing Portal session for the active organization and return "
        "its URL, where the user manages payment methods, invoices, and the "
        "subscription. Requires an owner API key and an existing billing account — an "
        "org that has never checked out fails with no_billing_account (call "
        "create_billing_checkout first). This call itself changes nothing."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

REFRESH_CREDITS_SPEC: dict[str, Any] = {
    "name": "refresh_credits",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Issue a compatibility credit batch to a quota-governed managed runtime. This "
        "exists for non-Algenta managed plans; Algenta editions are unmetered and do "
        "not need execution credits. Requires an API-key identity "
        "(api_key_identity_required otherwise) and a registered device_id. "
        "credits_used reports consumption since the last refresh and defaults to 0. "
        "Returns credits_granted, credits_issued_this_month, monthly_limit (0 means "
        "unlimited), monthly_remaining, expires_at, refresh_after, and server_time."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "minLength": 1,
                "description": "Registered device id the credits are issued to.",
            },
            "billing_period": {
                "type": "string",
                "pattern": "^\\d{4}-\\d{2}$",
                "description": "Billing month in YYYY-MM form.",
            },
            "credits_used": {
                "type": "integer",
                "minimum": 0,
                "description": "Credits consumed since the last refresh; defaults to 0.",
            },
        },
        "required": ["device_id", "billing_period"],
        "additionalProperties": False,
    },
}

INGEST_METERING_EVENTS_SPEC: dict[str, Any] = {
    "name": "ingest_metering_events",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Ingest one batch of execution-analytics events from a managed runtime that "
        "explicitly enabled control-plane sync. This endpoint is analytics-only: "
        "received events are counted for dashboards and structured-logged, never used "
        "for billing or quota enforcement, and self-hosted Algenta profiles never call "
        "it automatically. Every event field is optional; events without a timestamp "
        "count toward the current billing month. An empty events list fails with "
        "empty_events. Returns accepted (event count) and the primary billing_period."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "minLength": 1,
                "description": "Managed-runtime device id that produced the events.",
            },
            "events": {
                "type": "array",
                "minItems": 1,
                "description": "Analytics events; every field below is optional.",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "description": "Event kind label, e.g. execution.",
                        },
                        "module": {
                            "type": "string",
                            "description": "Runtime module that ran.",
                        },
                        "function": {
                            "type": "string",
                            "description": "Function within the module that ran.",
                        },
                        "engine_used": {
                            "type": "string",
                            "description": "Compute engine that executed the call.",
                        },
                        "latency_ms": {
                            "type": "number",
                            "description": "Observed execution latency in milliseconds.",
                        },
                        "success": {
                            "type": "boolean",
                            "description": "Whether the execution succeeded.",
                        },
                        "timestamp": {
                            "type": "number",
                            "description": (
                                "Unix timestamp of the event; determines its billing "
                                "period."
                            ),
                        },
                        "request_id": {
                            "type": "string",
                            "description": "Caller-side request id for correlation.",
                        },
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
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Partially update the organization's autonomous execution policy: only the "
        "fields supplied change, the rest keep their values. min_confidence blocks "
        "decisions below that confidence, risk_floor blocks decisions whose worst-case "
        "(p5) loss exceeds it, require_calibration makes auto-execution wait for enough "
        "recorded outcomes, and allow_reexecution is the idempotency gate. Changes take "
        "effect immediately, are recorded in the audit log, and write a new policy "
        "snapshot (see list_execution_policy_snapshots). Read the current values first "
        "with get_execution_policy. Returns the full updated policy."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "min_confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Block executions whose confidence is below this, 0-1.",
            },
            "risk_floor": {
                "type": "number",
                "minimum": 0,
                "description": "Block executions whose worst-case (p5) loss exceeds this.",
            },
            "require_calibration": {
                "type": "boolean",
                "description": "Require recorded outcomes before auto-execution.",
            },
            "allow_reexecution": {
                "type": "boolean",
                "description": "Idempotency gate preventing double-actions.",
            },
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
