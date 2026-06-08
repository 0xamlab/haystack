"""Pydantic-response builders for bindings, providers, profiles.

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


def _binding_response(binding: CapabilityBinding) -> CapabilityBindingResponse:
    return CapabilityBindingResponse(
        binding_id=str(binding.id),
        provider_id=binding.provider_id,
        profile_id=binding.profile_id,
        binding_name=binding.binding_name,
        scope=binding.scope,
        scope_ref=str(binding.scope_ref or ""),
        status=binding.status,
        execution_owner=binding.execution_owner,
        config=_redact_binding_config(
            decrypt_config_dict(binding.config_json, org_id=getattr(binding, "org_id", ""))
        ),
        customer_metadata=binding.customer_metadata_json,
        system_managed=bool(binding.system_managed),
        last_tested_at=binding.last_tested_at,
        last_discovered_at=binding.last_discovered_at,
        authorized_at=binding.authorized_at,
        quarantine_reason=binding.quarantine_reason,
        discovery_error_message=binding.discovery_error_message,
        test_error_message=binding.test_error_message,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
    )


def _provider_profile_response(profile: CapabilityProviderProfile) -> CapabilityProviderProfileResponse:
    return CapabilityProviderProfileResponse(
        profile_id=profile.profile_id,
        provider_id=profile.provider_id,
        name=profile.name,
        description=profile.description,
        auth_kind=profile.auth_kind,
        default_execution_owner=profile.default_execution_owner,
        binding_scope_default=profile.binding_scope_default,
        supported_binding_scopes=list(profile.supported_binding_scopes_json or []),
        profile_metadata=profile.profile_metadata_json,
    )


def _provider_response(
    provider: CapabilityProvider,
    *,
    profiles: Sequence[CapabilityProviderProfile],
) -> CapabilityProviderResponse:
    return CapabilityProviderResponse(
        provider_id=provider.provider_id,
        provider_type=provider.provider_type,
        name=provider.name,
        description=provider.description,
        docs_url=provider.docs_url,
        auth_schema=provider.auth_schema_json,
        certification_summary=provider.certification_summary_json,
        policy_summary=provider.policy_summary_json,
        supported_execution_owners=list(provider.supported_execution_owners_json or []),
        install_metadata=provider.install_metadata_json,
        customer_metadata=provider.customer_metadata_json,
        active=bool(provider.active),
        profiles=[_provider_profile_response(profile) for profile in profiles],
    )


