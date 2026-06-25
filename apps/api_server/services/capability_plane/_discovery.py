"""Binding context + per-kind discovery + snapshot persist/load + catalog cache.

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
from apps.api_server.services.egress_guard import (
    EgressPolicyDeniedError,
    audit_context_from_auth,
)
from apps.api_server.services.capability_plane._mcp_client import (
    MCPClientError,
    list_remote_tools,
)

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


def _binding_context_from_model(binding: CapabilityBinding) -> ResolvedBindingContext:
    return ResolvedBindingContext(
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_name=binding.binding_name,
        scope=binding.scope,
        scope_ref=str(binding.scope_ref or ""),
        status=binding.status,
        execution_owner=binding.execution_owner,
        config=dict(
            decrypt_config_dict(binding.config_json, org_id=getattr(binding, "org_id", "")) or {}
        ),
        customer_metadata=dict(binding.customer_metadata_json or {}),
        system_managed=bool(binding.system_managed),
        last_discovered_at=binding.last_discovered_at,
    )


def _binding_context_from_preview(
    *,
    auth: AuthContext,
    payload: CapabilityBindingPreviewRequest,
    default_execution_owner: ExecutionOwner,
) -> ResolvedBindingContext:
    scope = payload.scope
    return ResolvedBindingContext(
        binding_id=None,
        provider_id=payload.provider_id,
        profile_id=payload.profile_id,
        binding_name="preview",
        scope=scope,
        scope_ref=_scope_ref_from_auth(auth, scope=scope, scope_ref=payload.scope_ref),
        status=BindingStatus.READY,
        execution_owner=payload.execution_owner or default_execution_owner,
        config=dict(payload.config or {}),
        customer_metadata=dict(payload.customer_metadata or {}),
        system_managed=False,
    )


async def _connector_config_for_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[str, dict[str, Any]] | None:
    config = dict(binding.config)
    connector_id_raw = config.get("connector_id")
    connector_type_raw = config.get("connector_type")
    connector_config_raw = config.get("config")
    if isinstance(connector_id_raw, str) and connector_id_raw.strip():
        try:
            connector_id = uuid.UUID(connector_id_raw)
        except ValueError:
            _raise_error(422, "invalid_connector_id", "connector_id must be a valid UUID.")
        # SECURITY: scope the saved-connector lookup to the caller's org + workspace.
        # The binding preview endpoints (POST /v1/capability-bindings/test|/discover) accept
        # a caller-controlled config.connector_id; a bare db.get(DataConnector, id) here was a
        # cross-tenant / cross-org IDOR (it would decrypt + live-connect a victim's connector).
        # get_visible_connector applies workspace_scope_clauses + connector_visible and 404s
        # out-of-scope ids, making a foreign connector indistinguishable from a missing one.
        connector = await get_visible_connector(db, connector_id, auth)
        try:
            stored_config = json.loads(
                decrypt_config_json(connector.config_json, org_id=connector.org_id) or "{}"
            )
        except json.JSONDecodeError:
            _raise_error(
                409,
                "invalid_connector_config",
                "Saved connector config is not valid JSON.",
            )
        return connector.connector_type.value, stored_config if isinstance(stored_config, dict) else {}
    if isinstance(connector_type_raw, str) and connector_type_raw.strip():
        normalized_config = connector_config_raw if isinstance(connector_config_raw, dict) else {}
        return connector_type_raw.strip(), normalized_config
    return None


async def _discover_data_connector_binding(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    connector = await _connector_config_for_binding(db, auth, binding)
    discovered_at = _utc_now()
    if connector is not None:
        connector_type, connector_config = connector
        items, message, discovery = await browse_connector_real_detailed(
            connector_type,
            connector_config,
        )
        manifest_payload = {
            "binding_kind": "data_connector_preview",
            "preview": True,
            "items": items,
            "discovery": discovery,
        }
        manifest_hash = _stable_hash(manifest_payload)
        capabilities = []
        for item in items:
            label = str(item.get("label") or item.get("name") or item.get("selection") or "preview")
            selection = item.get("selection") if isinstance(item.get("selection"), dict) else {}
            capability = CapabilityCatalogEntry(
                capability_id=f"cap.dataset.preview.{manifest_hash[:12]}.{_stable_hash(item)[:12]}",
                provider_id=binding.provider_id,
                profile_id=binding.profile_id,
                binding_id=str(binding.binding_id or ""),
                kind=CapabilityKind.DATASET,
                name=label,
                description=message,
                implementation_kind=ImplementationKind.CALLABLE,
                execution_owner=binding.execution_owner,
                input_schema_ref="schemas/capability-plane/dataset.preview-selection.json",
                output_schema_ref="schemas/capability-plane/dataset.preview.json",
                side_effect_class=SideEffectClass.read_only,
                risk_level=RiskLevel.low,
                required_policy="policy.governed_data.preview",
                replayability=Replayability.non_replayable,
                approval_required=False,
                trust_tier="customer_preview",
                manifest_hash=manifest_hash,
                artifact_affinities=_dedupe_strings([label]),
                tags=_dedupe_strings(
                    [
                        label,
                        connector_type,
                        *[str(item) for item in selection.values() if item is not None],
                    ]
                ),
                required_binding_ids=[str(binding.binding_id)] if binding.binding_id else [],
                binding_status=binding.status,
                discovered_at=discovered_at,
                customer_metadata={
                    "preview": True,
                    "selection": selection,
                    "connector_type": connector_type,
                },
            )
            capabilities.append(capability)
        return capabilities, {"message": message, "discovery": discovery}, message

    org_id = str(auth["org_id"])
    visible_entries = filter_visible_datasets(sreg.list_sources(org_id), auth)
    manifest_hash = _stable_hash(visible_entries)
    capabilities = [
        _build_dataset_capability(
            binding=binding,
            entry=entry,
            schema_meta=sreg.get_source_meta(org_id, str(entry.get("id") or entry.get("dataset_id") or "")),
            manifest_hash=manifest_hash,
            discovered_at=discovered_at,
        )
        for entry in visible_entries
    ]
    message = f"Discovered {len(capabilities)} governed dataset capabilities."
    return capabilities, {"visible_dataset_count": len(capabilities)}, message


async def _discover_runtime_library_binding(
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    descriptors = list_public_runtime_library_descriptors()
    health = get_public_runtime_library_health()
    discovered_at = _utc_now()
    manifest_hash = _stable_hash(
        [{"name": descriptor.name, "functions": list(descriptor.functions)} for descriptor in descriptors]
    )
    capabilities: list[CapabilityCatalogEntry] = []
    for descriptor in descriptors:
        for function_name in descriptor.functions:
            capabilities.append(
                _build_runtime_library_capability(
                    binding=binding,
                    module_name=descriptor.name,
                    function_name=function_name,
                    engine=descriptor.engine,
                    manifest_hash=manifest_hash,
                    discovered_at=discovered_at,
                )
            )
    message = f"Discovered {len(capabilities)} runtime-library capabilities."
    return (
        capabilities,
        {
            "runtime_available": health.runtime_available,
            "engine": health.engine,
            "module_count": health.module_count,
        },
        message,
    )


async def _discover_mcp_provider_binding(
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    """Connect to a customer-registered external MCP server, list its tools, and persist them as
    MCP_TOOL capabilities. All egress flows through the deployment's egress guard (fail-closed)."""
    config = dict(binding.config)
    server_url = str(config.get("server_url") or "").strip()
    if not server_url:
        _raise_error(422, "mcp_server_url_required", "MCP provider bindings require config.server_url.")
    auth_config = config.get("auth") if isinstance(config.get("auth"), dict) else None
    audit = audit_context_from_auth(auth)
    try:
        tools = await list_remote_tools(server_url, auth=auth_config, audit=audit)
    except EgressPolicyDeniedError:
        _raise_error(
            403,
            "mcp_egress_denied",
            "The MCP server destination is not permitted by this deployment's egress policy. "
            "Add its host to ALGENTA_EGRESS_ALLOWLIST.",
        )
    except MCPClientError as exc:
        _raise_error(
            502,
            "mcp_discovery_failed",
            f"Could not discover tools from the MCP server: {exc.message}",
        )
    discovered_at = _utc_now()
    manifest_hash = _stable_hash(
        [{"name": tool.get("name"), "description": tool.get("description")} for tool in tools]
    )
    _MAX_TOOLS = 500
    _MAX_SCHEMA_BYTES = 64 * 1024
    capabilities: list[CapabilityCatalogEntry] = []
    for tool in tools[:_MAX_TOOLS]:  # bound a hostile server's tool count
        tool_name = str(tool.get("name") or "").strip()
        if not tool_name:
            continue
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", tool_name)[:64]
        input_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else None
        if input_schema is not None and len(json.dumps(input_schema, default=str)) > _MAX_SCHEMA_BYTES:
            input_schema = None  # drop an oversized/hostile schema from the persisted catalog
        capabilities.append(
            CapabilityCatalogEntry(
                capability_id=f"cap.mcp_tool.{safe_name}.{_stable_hash([str(binding.binding_id), tool_name])[:8]}",
                provider_id=binding.provider_id,
                profile_id=binding.profile_id,
                binding_id=str(binding.binding_id or ""),
                kind=CapabilityKind.MCP_TOOL,
                name=tool_name,
                description=(
                    str(tool.get("description")).strip()
                    if isinstance(tool.get("description"), str)
                    else None
                ),
                implementation_kind=ImplementationKind.CALLABLE,
                execution_owner=binding.execution_owner,
                input_schema_ref=f"mcp://{safe_name}/input",
                output_schema_ref=f"mcp://{safe_name}/output",
                side_effect_class=SideEffectClass.network_external,
                risk_level=RiskLevel.medium,
                required_policy="policy.capability.mcp_tool",
                replayability=Replayability.non_replayable,
                approval_required=False,
                trust_tier="customer_external_mcp",
                manifest_hash=manifest_hash,
                artifact_affinities=_dedupe_strings([tool_name]),
                tags=_dedupe_strings([tool_name, "mcp"]),
                required_binding_ids=[str(binding.binding_id)] if binding.binding_id else [],
                selected_tool_name=tool_name,
                binding_status=binding.status,
                discovered_at=discovered_at,
                # No secrets here: this is persisted in the snapshot + returned in catalog responses.
                # Execution re-reads server_url + auth from the encrypted binding config, not from here.
                customer_metadata={"tool_name": tool_name, "input_schema": input_schema},
            )
        )
    message = f"Discovered {len(capabilities)} MCP tool capabilities."
    return capabilities, {"tool_count": len(capabilities), "server_configured": True}, message


def _discover_manifest_binding(
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    manifest = binding.config.get("manifest")
    if not isinstance(manifest, dict):
        _raise_error(
            422,
            "manifest_required",
            "Manifest-backed bindings require config.manifest.",
        )
    raw_capabilities = manifest.get("capabilities")
    if not isinstance(raw_capabilities, list):
        _raise_error(
            422,
            "manifest_required",
            "config.manifest.capabilities must be an array.",
        )
    discovered_at = _utc_now()
    manifest_hash = _stable_hash(manifest)
    capabilities = [
        _manifest_capability_entry_to_catalog(
            binding=binding,
            manifest_hash=manifest_hash,
            discovered_at=discovered_at,
            payload=item,
        )
        for item in raw_capabilities
        if isinstance(item, dict)
    ]
    message = f"Discovered {len(capabilities)} manifest-backed capabilities."
    metadata = {
        "capability_count": len(capabilities),
        "provider_type": _provider_type_from_capability_kind(capabilities[0].kind).value
        if capabilities
        else None,
    }
    return capabilities, metadata, message


async def _discover_binding_capabilities(
    db: AsyncSession,
    auth: AuthContext,
    binding: ResolvedBindingContext,
) -> tuple[list[CapabilityCatalogEntry], dict[str, Any], str]:
    if binding.provider_id == DATA_CONNECTOR_PROVIDER_ID:
        return await _discover_data_connector_binding(db, auth, binding)
    if binding.provider_id == MCP_PROVIDER_ID:
        return await _discover_mcp_provider_binding(auth, binding)
    if binding.provider_id == RUNTIME_LIBRARY_PROVIDER_ID:
        return await _discover_runtime_library_binding(binding)
    return _discover_manifest_binding(binding)


async def _persist_snapshot(
    db: AsyncSession,
    auth: AuthContext,
    binding: CapabilityBinding,
    *,
    capabilities: list[CapabilityCatalogEntry],
    metadata: dict[str, Any],
) -> CapabilitySnapshot:
    discovered_at = _utc_now()
    manifest = {
        "binding_id": str(binding.id),
        "provider_id": binding.provider_id,
        "profile_id": binding.profile_id,
        "capabilities": [capability.model_dump(mode="json") for capability in capabilities],
    }
    snapshot = CapabilitySnapshot(
        binding_id=binding.id,
        org_id=_auth_org_id(auth),
        manifest_hash=_stable_hash(manifest),
        content_hash=_stable_hash({"manifest": manifest, "metadata": metadata}),
        manifest_json=manifest,
        discovery_metadata_json=metadata,
        discovered_at=discovered_at,
    )
    db.add(snapshot)
    binding.last_discovered_at = discovered_at
    binding.status = BindingStatus.READY if capabilities else BindingStatus.DEGRADED
    binding.discovery_error_message = None if capabilities else "No capabilities discovered."
    await db.flush()
    return snapshot


async def _latest_snapshot_map(
    db: AsyncSession,
    *,
    binding_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, CapabilitySnapshot]:
    if not binding_ids:
        return {}
    result = await db.execute(
        select(CapabilitySnapshot)
        .where(CapabilitySnapshot.binding_id.in_(list(binding_ids)))
        .order_by(CapabilitySnapshot.binding_id.asc(), CapabilitySnapshot.discovered_at.desc())
    )
    snapshots: dict[uuid.UUID, CapabilitySnapshot] = {}
    for snapshot in result.scalars():
        snapshots.setdefault(snapshot.binding_id, snapshot)
    return snapshots


def _capabilities_from_snapshot(
    binding: CapabilityBinding,
    snapshot: CapabilitySnapshot,
    *,
    include_instruction: bool = False,
) -> list[CapabilityCatalogEntry]:
    raw_capabilities = snapshot.manifest_json.get("capabilities")
    if not isinstance(raw_capabilities, list):
        return []
    entries: list[CapabilityCatalogEntry] = []
    for item in raw_capabilities:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        payload["binding_id"] = str(binding.id)
        payload["binding_status"] = binding.status.value
        payload["provider_id"] = binding.provider_id
        payload["profile_id"] = binding.profile_id
        payload["manifest_hash"] = snapshot.manifest_hash
        if not include_instruction:
            payload.pop("instruction_text", None)
        entries.append(CapabilityCatalogEntry.model_validate(payload))
    return entries


async def _refresh_system_binding_snapshot_if_needed(
    db: AsyncSession,
    auth: AuthContext,
    binding: CapabilityBinding,
    snapshot_map: dict[uuid.UUID, CapabilitySnapshot],
) -> None:
    if not binding.system_managed:
        return
    current_snapshot = snapshot_map.get(binding.id)
    if current_snapshot is not None and current_snapshot.discovered_at >= _utc_now() - SYSTEM_BINDING_REFRESH_TTL:
        return
    binding_context = _binding_context_from_model(binding)
    capabilities, metadata, _message = await _discover_binding_capabilities(db, auth, binding_context)
    snapshot = await _persist_snapshot(db, auth, binding, capabilities=capabilities, metadata=metadata)
    snapshot_map[binding.id] = snapshot


