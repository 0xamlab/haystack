"""_create/_complete_execution_session + execute_capability_service + record_capability_outcome_service.

Extracted from apps/api_server/services/capability_plane.py during modularization.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.capability_plane import (
    AuthorizationSessionStatus,
    BindingScope,
    BindingStatus,
    CapabilityBinding,
    CapabilityExecutionPlan,
    CapabilityExecutionSession,
    CapabilityKind,
    CapabilityPlanLifecycleState,
    CapabilityProvider,
    CapabilityProviderProfile,
    CapabilityRoutingOutcome,
    CapabilitySnapshot,
    ExecutionOwner,
    ExecutionSessionStatus,
    ImplementationKind,
    ProviderType,
)
from apps.api_server.models.data_connector import DataConnector
from apps.api_server.models.organization import Organization
from apps.api_server.schemas.receipt import ExecutionReceipt
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.config_crypto import (
    decrypt_config_dict,
    decrypt_config_json,
    encrypt_config_dict,
)
from apps.api_server.services.egress_guard import (
    EgressPolicyDeniedError,
    audit_context_from_auth,
)
from apps.api_server.services.capability_plane._mcp_client import (
    MCPClientError,
    call_remote_tool,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.workspace_scope import (
    workspace_id_for_write,
    workspace_scope_clauses,
)
from apps.api_server.services.connectors import test_connector_real_detailed
from apps.api_server.services.data_connection_browse import browse_connector_real_detailed
from apps.api_server.services.data_visibility import (
    filter_visible_datasets,
    get_visible_connector,
    get_visible_dataset_entry,
)
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime_manifest import Replayability, RiskLevel, SideEffectClass

POLICY_SNAPSHOT_ID = "capability-plane-policy-v1"
SYSTEM_BINDING_REFRESH_TTL = timedelta(minutes=5)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")

# Approving a capability execution plan is a privileged act: admin-or-owner only, mirroring
# decision_cases.py's _APPROVAL_MIN_ROLE exactly. Service keys are pinned to 'viewer' by the
# auth layer, so they can never satisfy this gate -- an agent holding only a service key can
# never approve its own pending plan.
_CAPABILITY_APPROVAL_MIN_ROLE = "admin"

# Role hierarchy for the minimum-role gate. Unknown/missing roles rank below everything, so a
# scope with no role (or a made-up one) can never satisfy a gate -- fail closed. Mirrors
# decision_service/service.py's _ROLE_RANK (duplicated rather than imported: that name is
# module-private to a different service, and the hierarchy is tiny and stable).
_CAPABILITY_ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

# Approval challenges expire this long after the plan was PROPOSED (a leaked propose response
# must not be approvable days later) -- mirrors decision_service/service.py's
# _APPROVAL_NONCE_TTL exactly.
_CAPABILITY_APPROVAL_NONCE_TTL = timedelta(hours=24)


from apps.api_server.services.capability_plane._constants import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._constants import (
    _CATALOG_CACHE_TTL,
    _catalog_cache,
    _invalidate_catalog_cache,
)
from apps.api_server.services.capability_plane._errors import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._errors import (
    _raise_error,
)
from apps.api_server.services.capability_plane._utils import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._utils import (
    _utc_now,
    _stable_hash,
    _dedupe_strings,
    _tokenize,
    _auth_org_id,
    _scope_ref_from_auth,
    _redact_binding_config,
    _system_binding_name,
)
from apps.api_server.services.capability_plane._models import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._models import (
    _ScoredCapability,
)
from apps.api_server.services.capability_plane._response_builders import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._response_builders import (
    _binding_response,
    _provider_profile_response,
    _provider_response,
)
from apps.api_server.services.capability_plane._capability_builders import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._capability_builders import (
    _dataset_tags,
    _dataset_artifact_affinities,
    _build_dataset_capability,
    _build_runtime_library_capability,
    _provider_type_from_capability_kind,
    _manifest_capability_kind_allowed,
    _manifest_capability_entry_to_catalog,
    _ensure_org_exists,
)
from apps.api_server.services.capability_plane._seeding import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._seeding import (
    _ensure_system_binding,
    _ensure_system_bindings,
    _require_provider,
    _require_profile,
    _require_binding,
)
from apps.api_server.services.capability_plane._discovery import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._discovery import (
    _binding_context_from_model,
    _binding_context_from_preview,
    _connector_config_for_binding,
    _discover_data_connector_binding,
    _discover_runtime_library_binding,
    _discover_manifest_binding,
    _discover_binding_capabilities,
    _persist_snapshot,
    _latest_snapshot_map,
    _capabilities_from_snapshot,
    _refresh_system_binding_snapshot_if_needed,
)
from apps.api_server.services.capability_plane._binding_services import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._binding_services import (
    _catalog_for_org,
    _record_routing_outcome,
    _test_binding,
)
from apps.api_server.services.capability_plane._authorization import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._capability_services import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._routing import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._routing import (
    _historical_outcome_adjustments,
    _score_capability,
)


async def _create_execution_session(
    db: AsyncSession,
    auth: AuthContext,
    capability: CapabilityCatalogEntry,
    request: CapabilityExecutionRequest,
) -> CapabilityExecutionSession:
    session = CapabilityExecutionSession(
        org_id=_auth_org_id(auth),
        provider_id=capability.provider_id,
        binding_id=uuid.UUID(capability.binding_id),
        capability_id=capability.capability_id,
        execution_owner=capability.execution_owner,
        status=ExecutionSessionStatus.STARTED,
        request_id=request.request_id,
        request_payload_json=request.model_dump(mode="json"),
        started_at=_utc_now(),
    )
    db.add(session)
    await db.flush()
    return session


async def _complete_execution_session(
    db: AsyncSession,
    auth: AuthContext,
    *,
    session: CapabilityExecutionSession,
    capability: CapabilityCatalogEntry,
    status: ExecutionSessionStatus,
    output: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> CapabilityExecutionResponse:
    session.status = status
    session.success = status is ExecutionSessionStatus.SUCCEEDED
    session.error_code = error.get("code") if isinstance(error, dict) else None
    session.response_payload_json = {"output": output, "error": error}
    session.completed_at = _utc_now()
    await db.flush()
    await _record_routing_outcome(
        db,
        auth,
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=capability.binding_id,
        route_request=None,
        route_plan=None,
        result_status="succeeded" if session.success else "failed",
        success=session.success,
        score=None,
        confidence=None,
        error_code=session.error_code,
        details=error or output,
    )
    return CapabilityExecutionResponse(
        execution_session_id=str(session.id),
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=capability.binding_id,
        execution_owner=capability.execution_owner,
        status=status,
        output=output,
        error=error,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


async def execute_capability_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityExecutionRequest,
) -> CapabilityExecutionResponse:
    capability = await get_capability_service(
        db,
        auth,
        payload.capability_id,
        include_instruction=True,
    )
    if payload.binding_id and payload.binding_id != capability.binding_id:
        _raise_error(
            409,
            "binding_mismatch",
            "binding_id does not match the selected capability binding.",
        )
    if payload.plan_id and not capability.approval_required:
        _raise_error(
            400,
            "plan_id_not_applicable",
            "This capability does not require approval; do not pass plan_id.",
        )
    # Approval gate (Track C1b): a capability whose catalog entry sets approval_required=True
    # must never reach the dispatch branches below on the strength of a bare request alone.
    # This is the ONLY new control-flow fork for the default (approval_required=False) case --
    # every capability below this branch executes exactly as it did before this gate existed.
    if capability.approval_required:
        if payload.plan_id:
            return await _execute_approved_capability_plan(db, auth, capability, payload)
        return await _propose_capability_execution(db, auth, capability, payload)

    session = await _create_execution_session(db, auth, capability, payload)
    request_input = dict(payload.input or {})
    return await _dispatch_capability_execution(
        db,
        auth,
        session=session,
        capability=capability,
        request_input=request_input,
        request_id=payload.request_id,
    )


async def _dispatch_capability_execution(
    db: AsyncSession,
    auth: AuthContext,
    *,
    session: CapabilityExecutionSession,
    capability: CapabilityCatalogEntry,
    request_input: dict[str, Any],
    request_id: str | None,
) -> CapabilityExecutionResponse:
    """The actual per-kind execution logic. Unchanged from before the approval gate existed --
    only the caller changed (execute_capability_service for the direct path, or
    _execute_approved_capability_plan once a plan has been approved)."""
    if capability.execution_owner is ExecutionOwner.CLIENT_MANAGED:
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.FAILED,
            error={
                "code": "client_managed_capability_requires_adapter",
                "message": (
                    "This capability is marked client_managed and must execute through "
                    "a customer-provided adapter."
                ),
            },
        )
    if capability.kind is CapabilityKind.DATASET:
        dataset_id = (
            capability.customer_metadata.get("dataset_id")
            if isinstance(capability.customer_metadata, dict)
            else None
        )
        if not isinstance(dataset_id, str) or not dataset_id:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "preview_capability_not_executable",
                    "message": "Preview dataset capabilities cannot execute directly.",
                },
            )
        operation = str(request_input.get("operation") or "summary").strip().lower()
        if operation not in {"summary", "schema"}:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "dataset_execution_requires_governed_query_path",
                    "message": (
                        "Dataset capabilities currently execute via summary/schema only. "
                        "Use the governed query path for query execution."
                    ),
                },
            )
        org_id = str(auth["org_id"])
        entry = get_visible_dataset_entry(org_id, dataset_id, auth)
        if entry is None:
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "dataset_not_found",
                    "message": f"Dataset '{dataset_id}' is no longer visible.",
                },
            )
        schema_meta = sreg.get_source_meta(org_id, dataset_id)
        output = {"dataset": entry, "schema": schema_meta} if operation == "schema" else {
            "dataset_id": dataset_id,
            "summary": {
                "dataset_id": dataset_id,
                "name": capability.name,
                "source_names": entry.get("source_names") or [],
                "row_count": schema_meta.get("row_count") if isinstance(schema_meta, dict) else None,
                "column_count": len(schema_meta.get("columns") or [])
                if isinstance(schema_meta, dict)
                else None,
                "query_hints": (schema_meta.get("query_hints") or [])[:10]
                if isinstance(schema_meta, dict)
                else [],
            },
        }
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output=output,
        )
    if capability.kind is CapabilityKind.RUNTIME_LIBRARY:
        metadata = capability.customer_metadata or {}
        module = metadata.get("module")
        function = metadata.get("function")
        if not isinstance(module, str) or not isinstance(function, str):
            return await _complete_execution_session(
                db,
                auth,
                session=session,
                capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "runtime_library_metadata_missing",
                    "message": "Runtime-library capability metadata is incomplete.",
                },
            )
        execution = await execute_public_runtime_library(
            module=module,
            function=function,
            args=request_input.get("args"),
            request_id=request_id,
        )
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output={
                "module": execution.module,
                "function": execution.function,
                "result": execution.result,
                "latency_ms": execution.latency_ms,
                "engine_used": execution.engine_used,
                "request_id": execution.request_id,
            },
        )
    if capability.kind is CapabilityKind.MCP_TOOL:
        tool_name = capability.selected_tool_name or (
            capability.customer_metadata.get("tool_name")
            if isinstance(capability.customer_metadata, dict)
            else None
        )
        if not isinstance(tool_name, str) or not tool_name:
            return await _complete_execution_session(
                db, auth, session=session, capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={"code": "mcp_tool_name_missing", "message": "MCP capability is missing its tool name."},
            )
        # Re-read the external server + auth from the binding's ENCRYPTED config, scoped to the
        # caller's org/workspace (_require_binding 404s a foreign binding — no cross-tenant IDOR).
        binding = await _require_binding(db, auth, capability.binding_id)
        binding_config = dict(decrypt_config_dict(binding.config_json, org_id=binding.org_id) or {})
        server_url = str(binding_config.get("server_url") or "").strip()
        if not server_url:
            return await _complete_execution_session(
                db, auth, session=session, capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={"code": "mcp_server_url_missing", "message": "MCP binding is missing config.server_url."},
            )
        auth_config = binding_config.get("auth") if isinstance(binding_config.get("auth"), dict) else None
        arguments = request_input.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {k: v for k, v in request_input.items() if k != "arguments"}
        try:
            result = await call_remote_tool(
                server_url,
                tool_name=tool_name,
                arguments=arguments,
                auth=auth_config,
                audit=audit_context_from_auth(auth),
                request_id=request_id,
            )
        except EgressPolicyDeniedError:
            return await _complete_execution_session(
                db, auth, session=session, capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={
                    "code": "mcp_egress_denied",
                    "message": (
                        "The MCP server destination is not permitted by this deployment's egress "
                        "policy. Add its host to ALGENTA_EGRESS_ALLOWLIST."
                    ),
                },
            )
        except MCPClientError as exc:
            return await _complete_execution_session(
                db, auth, session=session, capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={"code": "mcp_tool_execution_failed", "message": exc.message},
            )
        if result.get("isError"):
            return await _complete_execution_session(
                db, auth, session=session, capability=capability,
                status=ExecutionSessionStatus.FAILED,
                error={"code": "mcp_tool_reported_error", "message": "The MCP tool reported an error."},
                output={"tool": tool_name, "result": result},
            )
        return await _complete_execution_session(
            db, auth, session=session, capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output={"tool": tool_name, "result": result},
        )
    if capability.kind in {CapabilityKind.SKILL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}:
        payload_output: dict[str, Any] = {
            "instruction_artifact_ref": capability.instruction_artifact_ref,
            "instruction_text": capability.instruction_text,
            "capability_id": capability.capability_id,
        }
        return await _complete_execution_session(
            db,
            auth,
            session=session,
            capability=capability,
            status=ExecutionSessionStatus.SUCCEEDED,
            output=payload_output,
        )
    return await _complete_execution_session(
        db,
        auth,
        session=session,
        capability=capability,
        status=ExecutionSessionStatus.FAILED,
        error={
            "code": "algenta_managed_capability_not_executable",
            "message": (
                "This capability type does not yet have an Algenta-managed execution path. "
                "Use routeCapabilities() plus the customer execution node."
            ),
        },
    )


# ── approval gate (Track C1b) ──────────────────────────────────────────────────────────────
#
# For a capability whose catalog entry sets approval_required=True, execute_capability_service
# no longer dispatches directly. It mints a CapabilityExecutionPlan (PROPOSED), then a
# separate, credentialed HTTP call (approve_capability_execution_service -- never an MCP/LLM
# tool, mirroring decision_cases.py's own stated principle) flips it to APPROVED, and a second
# execute_capability_service call carrying plan_id actually dispatches it. The check ORDER in
# approve_capability_execution_service mirrors decision_service.service.DecisionService.approve
# exactly: role gate, then idempotency replay, then plan_hash/nonce/TTL, then a
# compare-and-set state transition.


def _require_capability_role(role: str | None, required_role: str, *, action: str) -> None:
    """Enforce a MINIMUM role (hierarchy-aware). Mirrors decision_service.service's
    _require_min_role. Unknown/missing roles fail closed."""
    have = _CAPABILITY_ROLE_RANK.get((role or "").lower(), -1)
    need = _CAPABILITY_ROLE_RANK.get(required_role.lower())
    if need is None:
        need = max(_CAPABILITY_ROLE_RANK.values()) + 1  # unsatisfiable requirement, fail closed
    if have < need:
        _raise_error(
            403, "insufficient_role", f"{action} requires role '{required_role}' or higher."
        )


def _approver_principal(auth: AuthContext) -> str:
    user_id = auth.get("user_id")
    return str(user_id) if user_id else f"key:{auth.get('key_id')}"


async def _require_capability_plan(
    db: AsyncSession, auth: AuthContext, plan_id: str
) -> CapabilityExecutionPlan:
    try:
        parsed = uuid.UUID(plan_id)
    except ValueError:
        _raise_error(422, "invalid_plan_id", "plan_id must be a valid UUID.")
    plan = await db.get(CapabilityExecutionPlan, parsed)
    ws = auth.get("workspace_id")
    if (
        plan is None
        or plan.org_id != _auth_org_id(auth)
        or (ws is not None and plan.workspace_id != ws)
    ):
        _raise_error(
            404,
            "capability_execution_plan_not_found",
            f"Capability execution plan '{plan_id}' not found.",
        )
    return plan


async def _find_capability_plan_by_idempotency(
    db: AsyncSession, auth: AuthContext, idempotency_key: str
) -> CapabilityExecutionPlan | None:
    # Org-wide lookup -- matches the scope of uq_capability_execution_plans_org_idempotency
    # exactly, or a same-key insert from another workspace would bypass this pre-check.
    result = await db.execute(
        select(CapabilityExecutionPlan)
        .where(CapabilityExecutionPlan.org_id == _auth_org_id(auth))
        .where(CapabilityExecutionPlan.idempotency_key == idempotency_key)
    )
    return result.scalars().first()


async def _transition_capability_plan(
    db: AsyncSession,
    plan: CapabilityExecutionPlan,
    *,
    from_state: str,
    values: dict[str, Any],
) -> bool:
    """Conditional UPDATE -- the WHERE on lifecycle_state makes the transition win-once under
    READ COMMITTED (a concurrent loser's UPDATE matches 0 rows once the winner's row-level
    lock releases). Mirrors decision_service/sql_repository.py's transition_plan_state."""
    stmt = (
        update(CapabilityExecutionPlan)
        .where(
            CapabilityExecutionPlan.id == plan.id,
            CapabilityExecutionPlan.lifecycle_state == from_state,
        )
        .values(**values)
    )
    result = await db.execute(stmt)
    await db.flush()
    return bool(getattr(result, "rowcount", 0))


def _capability_approval_response(plan: CapabilityExecutionPlan) -> CapabilityApprovalResponse:
    return CapabilityApprovalResponse(
        plan_id=str(plan.id),
        capability_id=plan.capability_id,
        provider_id=plan.provider_id,
        binding_id=str(plan.binding_id) if plan.binding_id else None,
        lifecycle_state=plan.lifecycle_state,
        approver_principal=plan.approver_principal,
        decided_at=plan.decided_at,
    )


async def _propose_capability_execution(
    db: AsyncSession,
    auth: AuthContext,
    capability: CapabilityCatalogEntry,
    payload: CapabilityExecutionRequest,
) -> CapabilityExecutionResponse:
    """Mint a pending approval-gate instead of executing. No MCP tool call, no runtime-library
    invocation, no dataset read has happened yet -- the execution session stays STARTED (never
    completed) until a separate approval flips this plan to APPROVED and a second
    execute_capability_service call (carrying plan_id) actually dispatches it."""
    session = await _create_execution_session(db, auth, capability, payload)
    input_snapshot = dict(payload.input or {})
    plan_hash = _stable_hash(
        {
            "capability_id": capability.capability_id,
            "binding_id": capability.binding_id,
            "input": input_snapshot,
            "manifest_hash": capability.manifest_hash,
        }
    )
    nonce = uuid.uuid4().hex
    plan = CapabilityExecutionPlan(
        org_id=_auth_org_id(auth),
        workspace_id=workspace_id_for_write(auth),
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=uuid.UUID(capability.binding_id),
        execution_session_id=session.id,
        input_json=input_snapshot,
        manifest_hash=capability.manifest_hash,
        plan_hash=plan_hash,
        nonce=nonce,
        nonce_consumed=False,
        lifecycle_state=CapabilityPlanLifecycleState.PROPOSED.value,
    )
    db.add(plan)
    await db.flush()
    receipt = ExecutionReceipt(
        status="approval_required",
        request_id=payload.request_id,
        execution_id=uuid.uuid4(),
        plan_hash=plan_hash,
        approval_state="pending",
        result={
            "plan_id": str(plan.id),
            "capability_id": capability.capability_id,
            "message": (
                f"This capability requires approval. Approve via POST "
                f"/v1/capability-executions/{plan.id}/approve, then call execute again with "
                "plan_id set."
            ),
        },
    )
    return CapabilityExecutionResponse(
        execution_session_id=str(session.id),
        capability_id=capability.capability_id,
        provider_id=capability.provider_id,
        binding_id=capability.binding_id,
        execution_owner=capability.execution_owner,
        status=ExecutionSessionStatus.STARTED,
        output=None,
        error=None,
        started_at=session.started_at,
        completed_at=None,
        plan_id=str(plan.id),
        plan_hash=plan_hash,
        nonce=nonce,
        receipt=receipt.to_stored(),
    )


async def _execute_approved_capability_plan(
    db: AsyncSession,
    auth: AuthContext,
    capability: CapabilityCatalogEntry,
    payload: CapabilityExecutionRequest,
) -> CapabilityExecutionResponse:
    plan = await _require_capability_plan(db, auth, payload.plan_id)
    if plan.capability_id != capability.capability_id:
        _raise_error(
            409,
            "plan_capability_mismatch",
            "plan_id does not reference a plan for this capability_id.",
        )
    if plan.lifecycle_state != CapabilityPlanLifecycleState.APPROVED.value:
        _raise_error(
            409,
            "plan_not_approved",
            f"Capability execution plan is '{plan.lifecycle_state}', not 'approved'.",
        )
    if plan.manifest_hash != capability.manifest_hash:
        _raise_error(
            409,
            "stale_capability_plan",
            "The capability definition changed since this plan was approved; re-propose.",
        )
    # Compare-and-set BEFORE the real side-effecting call: a concurrent double-execute must be
    # stopped here, not after an MCP tool / runtime library has already been invoked twice.
    won = await _transition_capability_plan(
        db,
        plan,
        from_state=CapabilityPlanLifecycleState.APPROVED.value,
        values={"lifecycle_state": CapabilityPlanLifecycleState.EXECUTING.value},
    )
    if not won:
        _raise_error(
            409, "plan_not_approved", "The plan was concurrently executed or invalidated."
        )
    plan.lifecycle_state = CapabilityPlanLifecycleState.EXECUTING.value

    session = await db.get(CapabilityExecutionSession, plan.execution_session_id)
    if session is None:
        _raise_error(
            500,
            "execution_session_missing",
            "The execution session for this approved plan is missing.",
        )
    request_input = dict(plan.input_json or {})
    response = await _dispatch_capability_execution(
        db,
        auth,
        session=session,
        capability=capability,
        request_input=request_input,
        request_id=payload.request_id,
    )
    receipt = ExecutionReceipt(
        status="executed" if response.status is ExecutionSessionStatus.SUCCEEDED else "failed",
        code=(response.error or {}).get("code") if response.error else None,
        request_id=payload.request_id,
        execution_id=uuid.uuid4(),
        plan_hash=plan.plan_hash,
        approval_state="approved",
        executed_at=_utc_now(),
        result=response.output,
    )
    plan.lifecycle_state = CapabilityPlanLifecycleState.EXECUTED.value
    plan.receipt_json = receipt.to_stored()
    await db.flush()
    response.plan_id = str(plan.id)
    response.plan_hash = plan.plan_hash
    response.nonce = None  # never re-expose the nonce after propose time
    response.receipt = receipt.to_stored()
    return response


async def approve_capability_execution_service(
    db: AsyncSession,
    auth: AuthContext,
    plan_id: str,
    payload: CapabilityApprovalRequest,
) -> CapabilityApprovalResponse:
    """Approve a proposed capability execution plan.

    A separately-authenticated, credentialed HTTP operation -- deliberately NOT exposed as an
    MCP/LLM tool (mirrors decision_cases.py's /v1/decision-plans/{plan_id}/approve). Check
    order mirrors DecisionService.approve exactly: role gate first (so a below-min-role caller
    can never receive approval material via idempotency replay), then the idempotency
    fast-path, then plan_hash/nonce/TTL, then a staleness guard, then the compare-and-set
    transition.
    """
    _require_capability_role(
        auth.get("role"), _CAPABILITY_APPROVAL_MIN_ROLE, action="capability approval"
    )

    if payload.idempotency_key:
        existing = await _find_capability_plan_by_idempotency(db, auth, payload.idempotency_key)
        if existing is not None:
            # A key is only a safe replay if the request fingerprint matches the stored plan
            # EXACTLY -- otherwise a reused key would silently return a different plan's
            # approval (misrouting + approval-material disclosure).
            if (
                str(existing.id) != plan_id
                or existing.plan_hash != payload.plan_hash
                or existing.nonce != payload.nonce
            ):
                _raise_error(
                    409,
                    "idempotency_key_conflict",
                    "idempotency_key was already used for a different capability approval "
                    "request.",
                )
            return _capability_approval_response(existing)

    plan = await _require_capability_plan(db, auth, plan_id)
    if plan.lifecycle_state != CapabilityPlanLifecycleState.PROPOSED.value:
        _raise_error(
            409,
            "plan_not_approvable",
            f"Capability execution plan is '{plan.lifecycle_state}', not 'proposed'.",
        )
    if plan.plan_hash != payload.plan_hash:
        _raise_error(403, "plan_hash_mismatch", "plan_hash does not match the current plan.")
    if plan.nonce != payload.nonce or plan.nonce_consumed:
        _raise_error(403, "invalid_nonce", "approval nonce is invalid or already used.")
    # The approval challenge expires by the nonce TTL measured from when the plan was
    # PROPOSED, so a leaked propose-response can't be approved days later.
    if _utc_now() > plan.created_at + _CAPABILITY_APPROVAL_NONCE_TTL:
        _raise_error(
            403,
            "approval_expired",
            "the approval challenge for this plan has expired; re-propose",
        )
    # Staleness guard: there is no "revision" concept for a single capability invocation, so
    # the manifest_hash snapshot plays that role -- a re-discovery that changed the
    # capability's definition since propose invalidates the plan rather than silently
    # authorizing a definition the approver never saw.
    try:
        current = await get_capability_service(
            db, auth, plan.capability_id, include_instruction=False
        )
    except CapabilityPlaneError:
        current = None
    if current is None or current.manifest_hash != plan.manifest_hash:
        _raise_error(
            409,
            "stale_capability_plan",
            "the capability definition changed since this plan was proposed; re-propose",
        )

    approver_principal = _approver_principal(auth)
    now = _utc_now()
    try:
        # Win the state transition FIRST (compare-and-set on 'proposed'): under concurrency
        # exactly one approve consumes the nonce; the loser sees plan_not_approvable.
        won = await _transition_capability_plan(
            db,
            plan,
            from_state=CapabilityPlanLifecycleState.PROPOSED.value,
            values={
                "lifecycle_state": CapabilityPlanLifecycleState.APPROVED.value,
                "nonce_consumed": True,
                "approver_principal": approver_principal,
                "required_role": _CAPABILITY_APPROVAL_MIN_ROLE,
                "idempotency_key": payload.idempotency_key,
                "decided_at": now,
            },
        )
    except IntegrityError as exc:
        # uq_capability_execution_plans_org_idempotency -- a concurrent first-use of the same
        # key beat us to it. Map the designed backstop to a workflow error, not a 500.
        raise CapabilityPlaneError(
            status_code=409,
            code="idempotency_key_conflict",
            message=(
                "idempotency_key was concurrently used by another capability approval request."
            ),
        ) from exc
    if not won:
        _raise_error(
            409, "plan_not_approvable", "the plan was concurrently approved or invalidated."
        )
    plan.lifecycle_state = CapabilityPlanLifecycleState.APPROVED.value
    plan.nonce_consumed = True
    plan.approver_principal = approver_principal
    plan.required_role = _CAPABILITY_APPROVAL_MIN_ROLE
    plan.idempotency_key = payload.idempotency_key
    plan.decided_at = now
    return _capability_approval_response(plan)


async def record_capability_outcome_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityOutcomeRecordRequest,
) -> CapabilityOutcomeRecord:
    outcome = await _record_routing_outcome(
        db,
        auth,
        capability_id=payload.capability_id,
        provider_id=payload.provider_id,
        binding_id=payload.binding_id,
        route_request=None,
        route_plan=None,
        result_status=payload.result_status,
        success=payload.success,
        score=payload.confidence,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
        details=payload.details,
    )
    return CapabilityOutcomeRecord(
        outcome_id=str(outcome.id),
        capability_id=payload.capability_id,
        provider_id=payload.provider_id,
        binding_id=payload.binding_id,
        success=payload.success,
        result_status=payload.result_status,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
        details=payload.details,
        created_at=outcome.created_at,
    )


