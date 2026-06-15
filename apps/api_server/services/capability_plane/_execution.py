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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.capability_plane import (
    AuthorizationSessionStatus,
    BindingScope,
    BindingStatus,
    CapabilityBinding,
    CapabilityExecutionSession,
    CapabilityKind,
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
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.config_crypto import (
    decrypt_config_dict,
    decrypt_config_json,
    encrypt_config_dict,
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
    session = await _create_execution_session(db, auth, capability, payload)
    request_input = dict(payload.input or {})
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
            request_id=payload.request_id,
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
                "This capability type does not yet have an Codna-managed execution path. "
                "Use routeCapabilities() plus the customer execution node."
            ),
        },
    )


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


