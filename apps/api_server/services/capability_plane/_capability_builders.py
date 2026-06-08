"""Dataset/runtime-library/manifest capability builders + provider-type mapping.

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


def _dataset_tags(entry: dict[str, Any], schema_meta: dict[str, Any] | None) -> list[str]:
    values = [
        str(entry.get("id") or ""),
        str(entry.get("dataset_name") or entry.get("name") or ""),
        *[str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)],
    ]
    if isinstance(schema_meta, dict):
        values.extend(
            str(item)
            for item in (schema_meta.get("query_hints") or [])
            if isinstance(item, str)
        )
    return _dedupe_strings(values)


def _dataset_artifact_affinities(entry: dict[str, Any]) -> list[str]:
    return _dedupe_strings(
        [
            str(entry.get("dataset_name") or entry.get("name") or ""),
            *[str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)],
        ]
    )


def _build_dataset_capability(
    *,
    binding: ResolvedBindingContext,
    entry: dict[str, Any],
    schema_meta: dict[str, Any] | None,
    manifest_hash: str,
    discovered_at: datetime,
) -> CapabilityCatalogEntry:
    dataset_id = str(entry.get("id") or entry.get("dataset_id") or "")
    dataset_name = str(entry.get("dataset_name") or entry.get("name") or dataset_id)
    source_names = [str(item) for item in (entry.get("source_names") or []) if isinstance(item, str)]
    description_parts = [f"dataset_id={dataset_id}"]
    if source_names:
        description_parts.append(f"sources={', '.join(source_names[:5])}")
    if isinstance(schema_meta, dict) and schema_meta.get("row_count") is not None:
        description_parts.append(f"rows={schema_meta.get('row_count')}")
    return CapabilityCatalogEntry(
        capability_id=f"cap.dataset.{dataset_id}",
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=CapabilityKind.DATASET,
        name=dataset_name,
        description="; ".join(description_parts),
        implementation_kind=ImplementationKind.CALLABLE,
        execution_owner=binding.execution_owner,
        input_schema_ref="schemas/capability-plane/dataset.summary-or-governed-query.json",
        output_schema_ref="schemas/capability-plane/dataset.summary.json",
        side_effect_class=SideEffectClass.read_only,
        risk_level=RiskLevel.low,
        required_policy="policy.governed_data.query",
        replayability=Replayability.artifact_backed,
        approval_required=False,
        trust_tier="algenta_governed",
        manifest_hash=manifest_hash,
        artifact_affinities=_dataset_artifact_affinities(entry),
        tags=_dataset_tags(entry, schema_meta),
        required_binding_ids=[str(binding.binding_id)],
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata={"dataset_id": dataset_id, "source_names": source_names},
    )


def _build_runtime_library_capability(
    *,
    binding: ResolvedBindingContext,
    module_name: str,
    function_name: str,
    engine: str,
    manifest_hash: str,
    discovered_at: datetime,
) -> CapabilityCatalogEntry:
    dotted_name = f"{module_name}.{function_name}"
    return CapabilityCatalogEntry(
        capability_id=f"cap.runtime_library.{module_name}.{function_name}",
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=CapabilityKind.RUNTIME_LIBRARY,
        name=dotted_name,
        description=f"Runtime library function `{dotted_name}` backed by engine `{engine}`.",
        implementation_kind=ImplementationKind.CALLABLE,
        execution_owner=binding.execution_owner,
        input_schema_ref=f"runtime-library://{module_name}/{function_name}/input",
        output_schema_ref=f"runtime-library://{module_name}/{function_name}/output",
        side_effect_class=SideEffectClass.read_only,
        risk_level=RiskLevel.low,
        required_policy="policy.runtime_library.execute",
        replayability=Replayability.deterministic,
        approval_required=False,
        trust_tier="algenta_runtime",
        manifest_hash=manifest_hash,
        artifact_affinities=[module_name],
        tags=_dedupe_strings([module_name, function_name, dotted_name]),
        required_binding_ids=[str(binding.binding_id)],
        selected_tool_name=function_name,
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata={"module": module_name, "function": function_name},
    )


def _provider_type_from_capability_kind(kind: CapabilityKind) -> ProviderType:
    if kind is CapabilityKind.DATASET:
        return ProviderType.DATA_CONNECTOR
    if kind in {CapabilityKind.MCP_TOOL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}:
        return ProviderType.MCP_PROVIDER
    if kind is CapabilityKind.SKILL:
        return ProviderType.SKILL_PACK
    if kind is CapabilityKind.NATIVE_TOOL:
        return ProviderType.NATIVE_TOOL_PACK
    return ProviderType.RUNTIME_LIBRARY_PACK


def _manifest_capability_kind_allowed(
    *,
    provider_id: str,
    kind: CapabilityKind,
) -> bool:
    if provider_id == MCP_PROVIDER_ID:
        return kind in {CapabilityKind.MCP_TOOL, CapabilityKind.MCP_PROMPT, CapabilityKind.MCP_RESOURCE}
    if provider_id == SKILL_PACK_PROVIDER_ID:
        return kind is CapabilityKind.SKILL
    if provider_id == NATIVE_TOOL_PROVIDER_ID:
        return kind is CapabilityKind.NATIVE_TOOL
    return True


def _manifest_capability_entry_to_catalog(
    *,
    binding: ResolvedBindingContext,
    manifest_hash: str,
    discovered_at: datetime,
    payload: dict[str, Any],
) -> CapabilityCatalogEntry:
    capability_id = str(payload.get("capability_id") or "").strip()
    if not capability_id:
        _raise_error(422, "invalid_capability_manifest", "Capability manifest entries require capability_id.")
    try:
        kind = CapabilityKind(str(payload.get("kind") or "").strip())
    except ValueError as exc:
        _raise_error(
            422,
            "invalid_capability_manifest",
            "Capability manifest entries require a valid kind.",
            {"capability_id": capability_id, "field": "kind"},
        )
    if not _manifest_capability_kind_allowed(provider_id=binding.provider_id, kind=kind):
        _raise_error(
            422,
            "invalid_capability_manifest",
            f"Capability kind '{kind.value}' is not allowed for provider '{binding.provider_id}'.",
        )
    try:
        implementation_kind = ImplementationKind(
            str(payload.get("implementation_kind") or ImplementationKind.CALLABLE.value)
        )
        execution_owner = ExecutionOwner(
            str(payload.get("execution_owner") or binding.execution_owner.value)
        )
        side_effect_class = SideEffectClass(
            str(payload.get("side_effect_class") or SideEffectClass.read_only.value)
        )
        risk_level = RiskLevel(str(payload.get("risk_level") or RiskLevel.low.value))
        replayability = Replayability(
            str(payload.get("replayability") or Replayability.deterministic.value)
        )
    except ValueError as exc:
        _raise_error(
            422,
            "invalid_capability_manifest",
            "Capability manifest contains an invalid enum value.",
            {"capability_id": capability_id},
        )
    instruction_text = payload.get("instruction")
    instruction_artifact_ref = payload.get("instruction_artifact_ref")
    if isinstance(instruction_text, str) and instruction_text.strip() and not instruction_artifact_ref:
        instruction_artifact_ref = f"artifact://capability-snapshot/{manifest_hash}/{capability_id}"
    selected_tool_name = payload.get("selected_tool_name")
    return CapabilityCatalogEntry(
        capability_id=capability_id,
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_id=str(binding.binding_id),
        kind=kind,
        name=str(payload.get("name") or capability_id),
        description=(
            str(payload.get("description")).strip()
            if isinstance(payload.get("description"), str)
            else None
        ),
        implementation_kind=implementation_kind,
        execution_owner=execution_owner,
        input_schema_ref=str(
            payload.get("input_schema_ref") or f"capability://{capability_id}/input"
        ),
        output_schema_ref=str(
            payload.get("output_schema_ref") or f"capability://{capability_id}/output"
        ),
        side_effect_class=side_effect_class,
        risk_level=risk_level,
        required_policy=str(payload.get("required_policy") or "policy.capability.execute"),
        replayability=replayability,
        approval_required=bool(payload.get("approval_required") or False),
        trust_tier=str(payload.get("trust_tier") or "customer_managed"),
        manifest_hash=manifest_hash,
        artifact_affinities=_dedupe_strings(payload.get("artifact_affinities") or []),
        tags=_dedupe_strings(payload.get("tags") or []),
        required_binding_ids=_dedupe_strings(
            payload.get("required_binding_ids") or [str(binding.binding_id)]
        ),
        selected_tool_name=selected_tool_name if isinstance(selected_tool_name, str) else None,
        instruction_artifact_ref=(
            str(instruction_artifact_ref).strip()
            if isinstance(instruction_artifact_ref, str) and str(instruction_artifact_ref).strip()
            else None
        ),
        binding_status=binding.status,
        discovered_at=discovered_at,
        customer_metadata=payload.get("customer_metadata") if isinstance(payload.get("customer_metadata"), dict) else None,
        instruction_text=instruction_text if isinstance(instruction_text, str) else None,
    )


async def _ensure_org_exists(db: AsyncSession, org_id: uuid.UUID) -> None:
    org = await db.get(Organization, org_id)
    if org is None:
        _raise_error(404, "organization_not_found", "Organization not found.")

