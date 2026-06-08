"""_historical_outcome_adjustments + _score_capability + route_capabilities_service.

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


async def _historical_outcome_adjustments(
    db: AsyncSession,
    auth: AuthContext,
) -> dict[str, tuple[int, int]]:
    result = await db.execute(
        select(CapabilityRoutingOutcome)
        .where(CapabilityRoutingOutcome.org_id == _auth_org_id(auth))
        .where(CapabilityRoutingOutcome.success.is_not(None))
    )
    counts: dict[str, tuple[int, int]] = {}
    for outcome in result.scalars():
        success_count, failure_count = counts.get(outcome.capability_id, (0, 0))
        if outcome.success:
            success_count += 1
        else:
            failure_count += 1
        counts[outcome.capability_id] = (success_count, failure_count)
    return counts


def _score_capability(
    capability: CapabilityCatalogEntry,
    *,
    objective: str,
    artifact_affinities: Sequence[str],
    requested_tags: Sequence[str],
    historical_counts: tuple[int, int],
) -> _ScoredCapability:
    objective_tokens = set(_tokenize(objective))
    tag_tokens = set(_tokenize(" ".join(capability.tags)))
    name_tokens = set(_tokenize(capability.name))
    description_tokens = set(_tokenize(capability.description or ""))
    affinity_tokens = set(_tokenize(" ".join(capability.artifact_affinities)))
    overlap = objective_tokens & (tag_tokens | name_tokens | description_tokens | affinity_tokens)
    score = float(len(overlap) * 10)
    reasons: list[str] = []
    if overlap:
        reasons.append(f"token overlap: {', '.join(sorted(overlap)[:6])}")
    if capability.binding_status is BindingStatus.READY:
        score += 15
        reasons.append("binding ready")
    elif capability.binding_status is BindingStatus.DEGRADED:
        score -= 10
        reasons.append("binding degraded")
    elif capability.binding_status is BindingStatus.QUARANTINED:
        score -= 50
        reasons.append("binding quarantined")
    if any(tag in capability.tags for tag in requested_tags):
        score += 8
        reasons.append("requested tag match")
    if any(affinity in capability.artifact_affinities for affinity in artifact_affinities):
        score += 8
        reasons.append("artifact affinity match")
    success_count, failure_count = historical_counts
    score += float(success_count * 2)
    score -= float(failure_count * 3)
    if success_count or failure_count:
        reasons.append(f"historical outcomes: +{success_count}/-{failure_count}")
    if capability.approval_required:
        score -= 2
        reasons.append("approval required")
    confidence = max(0.05, min(0.99, score / 100.0))
    return _ScoredCapability(
        capability=capability,
        score=confidence,
        reason="; ".join(reasons) if reasons else "default catalog ranking",
    )


async def route_capabilities_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: CapabilityRouteRequest,
) -> CapabilityRoutePlan:
    entries = await _catalog_for_org(db, auth, include_instruction=False)
    filtered = []
    binding_ids = set(payload.binding_ids)
    provider_ids = set(payload.provider_ids)
    kinds = set(payload.kinds)
    execution_owners = set(payload.execution_owners)
    for entry in entries:
        if binding_ids and entry.binding_id not in binding_ids:
            continue
        if provider_ids and entry.provider_id not in provider_ids:
            continue
        if kinds and entry.kind not in kinds:
            continue
        if execution_owners and entry.execution_owner not in execution_owners:
            continue
        if entry.binding_status is BindingStatus.QUARANTINED:
            continue
        filtered.append(entry)
    if not filtered:
        _raise_error(
            404,
            "capability_route_not_found",
            "No capabilities matched the requested route filters.",
        )
    historical = await _historical_outcome_adjustments(db, auth)
    scored = sorted(
        (
            _score_capability(
                entry,
                objective=payload.objective,
                artifact_affinities=payload.artifact_affinities,
                requested_tags=payload.tags,
                historical_counts=historical.get(entry.capability_id, (0, 0)),
            )
            for entry in filtered
        ),
        key=lambda item: (item.score, item.capability.name),
        reverse=True,
    )
    selected = scored[0]
    fallbacks = [
        CapabilityRouteFallback(
            capability_id=item.capability.capability_id,
            provider_id=item.capability.provider_id,
            binding_id=item.capability.binding_id,
            kind=item.capability.kind,
            execution_owner=item.capability.execution_owner,
            confidence=round(item.score, 4),
            reason=item.reason,
            selected_tool_name=item.capability.selected_tool_name,
            instruction_artifact_ref=item.capability.instruction_artifact_ref,
        )
        for item in scored[1 : 1 + payload.max_fallbacks]
    ]
    route_plan = CapabilityRoutePlan(
        selected_capability_id=selected.capability.capability_id,
        selected_provider_id=selected.capability.provider_id,
        selected_binding_id=selected.capability.binding_id,
        kind=selected.capability.kind,
        execution_owner=selected.capability.execution_owner,
        requires_approval=selected.capability.approval_required,
        confidence=round(selected.score, 4),
        reason=selected.reason,
        fallbacks=fallbacks,
        policy_snapshot_id=POLICY_SNAPSHOT_ID,
        selected_tool_name=selected.capability.selected_tool_name,
        instruction_artifact_ref=selected.capability.instruction_artifact_ref,
    )
    await _record_routing_outcome(
        db,
        auth,
        capability_id=selected.capability.capability_id,
        provider_id=selected.capability.provider_id,
        binding_id=selected.capability.binding_id,
        route_request=payload.model_dump(mode="json"),
        route_plan=route_plan.model_dump(mode="json"),
        result_status="routed",
        success=None,
        score=selected.score,
        confidence=selected.score,
    )
    return route_plan

