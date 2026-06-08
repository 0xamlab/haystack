"""enable_skill_service.

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
from apps.api_server.services.capability_plane._execution import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._execution import (
    _create_execution_session,
    _complete_execution_session,
)


async def enable_skill_service(
    db: AsyncSession,
    auth: AuthContext,
    payload: SkillEnableRequest,
) -> CapabilityDiscoverResponse:
    binding = await create_capability_binding_service(
        db,
        auth,
        CapabilityBindingCreateRequest(
            provider_id=SKILL_PACK_PROVIDER_ID,
            profile_id=SKILL_PACK_PROFILE_ID,
            binding_name=payload.skill_name,
            scope=BindingScope.USER,
            execution_owner=payload.execution_owner,
            config={
                "manifest": {
                    "capabilities": [
                        {
                            "capability_id": f"cap.skill.{payload.skill_name.lower().replace(' ', '_')}",
                            "name": payload.skill_name,
                            "description": payload.description,
                            "kind": CapabilityKind.SKILL.value,
                            "implementation_kind": ImplementationKind.INSTRUCTION_ONLY.value,
                            "execution_owner": payload.execution_owner.value,
                            "instruction": payload.instruction,
                            "artifact_affinities": payload.artifact_affinities,
                            "tags": payload.tags,
                            "replayability": Replayability.deterministic.value,
                        }
                    ]
                }
            },
        ),
    )
    return await discover_capability_binding_service(db, auth, binding.binding_id)
