"""account/billing/credits/metering/keys/team/devices/execution-policy runtime requests.

Extracted from packages/algenta-core/algenta/runtime_execution_surface.py during modularization.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")


from algenta.runtime_execution_surface._api_client_local import *  # noqa: F401, F403
from algenta.runtime_execution_surface._api_client_local import (
    _run_sync,
)
from algenta.runtime_execution_surface._validation import *  # noqa: F401, F403
from algenta.runtime_execution_surface._validation import (
    _validate_contract_payload,
    _build_runtime_validation_error_details,
    _validate_runtime_proof_payload,
    _validate_runtime_api_payload,
    _validate_runtime_api_mapping_payload,
    _validate_runtime_api_structured_mapping_payload,
    _validate_runtime_api_mapping_list_payload,
    _validate_runtime_api_stream,
    _validate_runtime_api_payload_list,
    _request_runtime_contract_payload,
)
from algenta.runtime_execution_surface._query_jobs_triggers import *  # noqa: F401, F403
from algenta.runtime_execution_surface._decision_repo_product_deploy import *  # noqa: F401, F403



def me_runtime_request(runtime: Any) -> dict[str, Any]:
    runtime._require_api_transport("me")
    return _validate_runtime_api_structured_mapping_payload(
        "me",
        runtime._client().me(),
        _runtime_model_control_plane_module().MeOutput,
    )


def update_me_runtime_request(
    runtime: Any,
    *,
    name: str | None = None,
    org_name: str | None = None,
) -> Any:
    runtime._require_api_transport("update_me")
    return _validate_runtime_api_structured_mapping_payload(
        "update_me",
        runtime._client().update_me(name=name, org_name=org_name),
        _runtime_model_control_plane_module().MeOutput,
    )


def usage_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("usage")
    return _validate_runtime_api_payload(
        "usage",
        runtime._client().usage(),
        _runtime_model_account_module().UsageOutput,
    )


def limits_runtime_request(runtime: Any) -> dict[str, Any]:
    runtime._require_api_transport("limits")
    return _validate_runtime_api_mapping_payload("limits", runtime._client().limits())


def get_billing_info_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_billing_info")
    return _validate_runtime_api_payload(
        "get_billing_info",
        runtime._client().get_billing_info(),
        _runtime_model_control_plane_module().BillingInfoOutput,
    )


def create_billing_checkout_runtime_request(
    runtime: Any,
    *,
    plan: str | None = None,
) -> Any:
    runtime._require_api_transport("create_billing_checkout")
    return _validate_runtime_api_payload(
        "create_billing_checkout",
        runtime._client().create_billing_checkout(plan=plan),
        _runtime_model_control_plane_module().BillingSessionOutput,
    )


def create_billing_portal_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("create_billing_portal")
    return _validate_runtime_api_payload(
        "create_billing_portal",
        runtime._client().create_billing_portal(),
        _runtime_model_control_plane_module().BillingSessionOutput,
    )


def refresh_credits_runtime_request(
    runtime: Any,
    *,
    device_id: str,
    billing_period: str,
    credits_used: int = 0,
) -> Any:
    runtime._require_api_transport("refresh_credits")
    return _validate_runtime_api_payload(
        "refresh_credits",
        runtime._client().refresh_credits(
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        ),
        _runtime_model_control_plane_module().CreditRefreshOutput,
    )


def ingest_metering_events_runtime_request(
    runtime: Any,
    *,
    device_id: str,
    events: list[dict[str, Any]],
) -> Any:
    runtime._require_api_transport("ingest_metering_events")
    return _validate_runtime_api_payload(
        "ingest_metering_events",
        runtime._client().ingest_metering_events(device_id=device_id, events=events),
        _runtime_model_control_plane_module().MeteringBatchOutput,
    )


def list_api_keys_runtime_request(runtime: Any) -> list[Any]:
    runtime._require_api_transport("list_api_keys")
    return _validate_runtime_api_payload_list(
        "list_api_keys",
        runtime._client().list_api_keys(),
        _runtime_model_account_module().APIKeyInfoOutput,
    )


def create_api_key_runtime_request(
    runtime: Any,
    *,
    label: str | None = None,
    name: str | None = None,
    expires_at: Any = None,
    device_limit: int | None = None,
) -> Any:
    runtime._require_api_transport("create_api_key")
    return _validate_runtime_api_payload(
        "create_api_key",
        runtime._client().create_api_key(
            label=label,
            name=name,
            expires_at=expires_at,
            device_limit=device_limit,
        ),
        _runtime_model_account_module().APIKeyCreatedOutput,
    )


def revoke_api_key_runtime_request(runtime: Any, key_id: str) -> dict[str, Any]:
    runtime._require_api_transport("revoke_api_key")
    return _validate_runtime_api_mapping_payload(
        "revoke_api_key",
        runtime._client().revoke_api_key(key_id),
    )


def distributions_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("distributions")
    return _validate_runtime_api_payload(
        "distributions",
        runtime._client().distributions(),
        _runtime_model_control_plane_module().DistributionListOutput,
    )


def templates_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("templates")
    return _validate_runtime_api_payload(
        "templates",
        runtime._client().templates(),
        _runtime_model_control_plane_module().TemplateListOutput,
    )


def list_team_members_runtime_request(
    runtime: Any,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    runtime._require_api_transport("list_team_members")
    return _validate_runtime_api_payload(
        "list_team_members",
        runtime._client().list_team_members(page=page, limit=limit),
        _runtime_model_control_plane_module().TeamListOutput,
    )


def invite_team_member_runtime_request(
    runtime: Any,
    *,
    email: str,
    role: str = "member",
) -> Any:
    runtime._require_api_transport("invite_team_member")
    return _validate_runtime_api_payload(
        "invite_team_member",
        runtime._client().invite_team_member(email=email, role=role),
        _runtime_model_control_plane_module().TeamInviteOutput,
    )


def update_team_member_role_runtime_request(
    runtime: Any,
    user_id: str,
    *,
    role: str,
) -> Any:
    runtime._require_api_transport("update_team_member_role")
    return _validate_runtime_api_payload(
        "update_team_member_role",
        runtime._client().update_team_member_role(user_id, role=role),
        _runtime_model_control_plane_module().TeamRoleUpdateOutput,
    )


def remove_team_member_runtime_request(runtime: Any, user_id: str) -> Any:
    runtime._require_api_transport("remove_team_member")
    payload = runtime._client().remove_team_member(user_id)
    if not isinstance(payload, dict):
        raise TypeError(
            f"remove_team_member returned {type(payload).__name__}, expected a JSON object."
        )
    return _validate_runtime_api_payload(
        "remove_team_member",
        {"removed": True, "user_id": user_id, **payload},
        _runtime_model_control_plane_module().TeamRemoveOutput,
    )


def get_audit_logs_runtime_request(
    runtime: Any,
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
    runtime._require_api_transport("get_audit_logs")
    return _validate_runtime_api_payload(
        "get_audit_logs",
        runtime._client().get_audit_logs(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
        ),
        _runtime_model_control_plane_module().AuditLogOutput,
    )


def get_audit_log_artifacts_runtime_request(
    runtime: Any,
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
    runtime._require_api_transport("get_audit_log_artifacts")
    return _validate_runtime_api_payload(
        "get_audit_log_artifacts",
        runtime._client().get_audit_log_artifacts(
            page=page,
            limit=limit,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            result=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
            content_hash=content_hash,
        ),
        _runtime_model_control_plane_module().AuditLogOutput,
    )


def get_execution_policy_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_execution_policy")
    return _validate_runtime_api_payload(
        "get_execution_policy",
        runtime._client().get_execution_policy(),
        _runtime_model_control_plane_module().ExecutionPolicyOutput,
    )


def list_execution_policy_snapshots_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("list_execution_policy_snapshots")
    return _validate_runtime_api_payload(
        "list_execution_policy_snapshots",
        runtime._client().list_execution_policy_snapshots(),
        _runtime_model_control_plane_module().ExecutionPolicySnapshotListOutput,
    )


def list_devices_runtime_request(
    runtime: Any,
    *,
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    runtime._require_api_transport("list_devices")
    return _validate_runtime_api_payload(
        "list_devices",
        runtime._client().list_devices(page=page, limit=limit),
        _runtime_model_control_plane_module().DeviceListOutput,
    )


def revoke_device_runtime_request(runtime: Any, registration_id: str) -> Any:
    runtime._require_api_transport("revoke_device")
    return _validate_runtime_api_payload(
        "revoke_device",
        runtime._client().revoke_device(registration_id),
        _runtime_model_control_plane_module().DeviceRevokeOutput,
    )


def update_execution_policy_runtime_request(
    runtime: Any,
    *,
    min_confidence: float | None = None,
    risk_floor: float | None = None,
    require_calibration: bool | None = None,
    allow_reexecution: bool | None = None,
) -> Any:
    runtime._require_api_transport("update_execution_policy")
    return _validate_runtime_api_payload(
        "update_execution_policy",
        runtime._client().update_execution_policy(
            min_confidence=min_confidence,
            risk_floor=risk_floor,
            require_calibration=require_calibration,
            allow_reexecution=allow_reexecution,
        ),
        _runtime_model_control_plane_module().ExecutionPolicyOutput,
    )


