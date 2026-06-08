"""Generic capability-plane import service."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.capability_plane import (
    BindingScope,
    BindingStatus,
    CapabilityBinding,
    CapabilityProvider,
    CapabilityProviderProfile,
    CapabilityRoutingOutcome,
    CapabilitySnapshot,
    ExecutionOwner,
    ProviderType,
)


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class ImportedCapabilityProviderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    profile_id: str
    provider_id: str
    name: str
    description: str | None = None
    auth_kind: str = "none"
    default_execution_owner: ExecutionOwner
    binding_scope_default: BindingScope
    supported_binding_scopes: list[str] = Field(default_factory=list)
    profile_metadata: dict[str, Any] | None = None


class ImportedCapabilityProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    provider_id: str
    provider_type: ProviderType
    name: str
    description: str | None = None
    docs_url: str | None = None
    auth_schema: dict[str, Any] | None = None
    certification_summary: dict[str, Any] | None = None
    policy_summary: dict[str, Any] | None = None
    supported_execution_owners: list[str] = Field(default_factory=list)
    install_metadata: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None
    active: bool = True
    profiles: list[ImportedCapabilityProviderProfile] = Field(default_factory=list)


class ImportedCapabilityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    binding_id: uuid.UUID
    org_id: uuid.UUID
    provider_id: str
    profile_id: str
    binding_name: str
    scope: BindingScope
    scope_ref: str | None = None
    status: BindingStatus
    execution_owner: ExecutionOwner
    config: dict[str, Any] | None = None
    auth_state: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None
    system_managed: bool = False
    last_tested_at: datetime | None = None
    last_discovered_at: datetime | None = None
    authorized_at: datetime | None = None
    quarantine_reason: str | None = None
    discovery_error_message: str | None = None
    test_error_message: str | None = None


class ImportedCapabilitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    snapshot_id: uuid.UUID
    binding_id: uuid.UUID
    org_id: uuid.UUID
    manifest_hash: str
    content_hash: str
    manifest: dict[str, Any]
    discovery_metadata: dict[str, Any] | None = None
    discovered_at: datetime


class ImportedCapabilityRoutingOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    outcome_id: uuid.UUID
    org_id: uuid.UUID
    provider_id: str
    binding_id: uuid.UUID | None = None
    capability_id: str
    route_request: dict[str, Any] | None = None
    route_plan: dict[str, Any] | None = None
    result_status: str = "routed"
    success: bool | None = None
    score: float | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    error_code: str | None = None
    outcome_details: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CapabilityPlaneImportBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    providers: list[ImportedCapabilityProvider] = Field(default_factory=list)
    bindings: list[ImportedCapabilityBinding] = Field(default_factory=list)
    snapshots: list[ImportedCapabilitySnapshot] = Field(default_factory=list)
    routing_outcomes: list[ImportedCapabilityRoutingOutcome] = Field(default_factory=list)


class CapabilityPlaneImportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)

    dry_run: bool
    providers_upserted: int
    profiles_upserted: int
    bindings_upserted: int
    snapshots_inserted: int
    routing_outcomes_inserted: int


async def _upsert_provider(
    db: AsyncSession,
    payload: ImportedCapabilityProvider,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    provider = await db.get(CapabilityProvider, payload.provider_id)
    if provider is None:
        provider = CapabilityProvider(provider_id=payload.provider_id)
        if not dry_run:
            db.add(provider)
    provider.provider_type = payload.provider_type
    provider.name = payload.name
    provider.description = payload.description
    provider.docs_url = payload.docs_url
    provider.auth_schema_json = payload.auth_schema
    provider.certification_summary_json = payload.certification_summary
    provider.policy_summary_json = payload.policy_summary
    provider.supported_execution_owners_json = list(payload.supported_execution_owners)
    provider.install_metadata_json = payload.install_metadata
    provider.customer_metadata_json = payload.customer_metadata
    provider.active = payload.active

    profile_count = 0
    for profile_payload in payload.profiles:
        profile = await db.get(CapabilityProviderProfile, profile_payload.profile_id)
        if profile is None:
            profile = CapabilityProviderProfile(profile_id=profile_payload.profile_id)
            if not dry_run:
                db.add(profile)
        profile.provider_id = profile_payload.provider_id
        profile.name = profile_payload.name
        profile.description = profile_payload.description
        profile.auth_kind = profile_payload.auth_kind
        profile.default_execution_owner = profile_payload.default_execution_owner
        profile.binding_scope_default = profile_payload.binding_scope_default
        profile.supported_binding_scopes_json = list(profile_payload.supported_binding_scopes)
        profile.profile_metadata_json = profile_payload.profile_metadata
        profile_count += 1
    return 1, profile_count


async def _upsert_binding(
    db: AsyncSession,
    payload: ImportedCapabilityBinding,
    *,
    dry_run: bool,
) -> int:
    binding = await db.get(CapabilityBinding, payload.binding_id)
    if binding is None:
        binding = CapabilityBinding(id=payload.binding_id)
        if not dry_run:
            db.add(binding)
    binding.org_id = payload.org_id
    binding.provider_id = payload.provider_id
    binding.profile_id = payload.profile_id
    binding.binding_name = payload.binding_name
    binding.scope = payload.scope
    binding.scope_ref = payload.scope_ref
    binding.status = payload.status
    binding.execution_owner = payload.execution_owner
    binding.config_json = payload.config
    binding.auth_state_json = payload.auth_state
    binding.customer_metadata_json = payload.customer_metadata
    binding.system_managed = payload.system_managed
    binding.last_tested_at = payload.last_tested_at
    binding.last_discovered_at = payload.last_discovered_at
    binding.authorized_at = payload.authorized_at
    binding.quarantine_reason = payload.quarantine_reason
    binding.discovery_error_message = payload.discovery_error_message
    binding.test_error_message = payload.test_error_message
    return 1


async def _insert_snapshot(
    db: AsyncSession,
    payload: ImportedCapabilitySnapshot,
    *,
    dry_run: bool,
) -> int:
    existing = await db.get(CapabilitySnapshot, payload.snapshot_id)
    if existing is not None:
        return 0
    if dry_run:
        return 1
    db.add(
        CapabilitySnapshot(
            id=payload.snapshot_id,
            binding_id=payload.binding_id,
            org_id=payload.org_id,
            manifest_hash=payload.manifest_hash,
            content_hash=payload.content_hash,
            manifest_json=payload.manifest,
            discovery_metadata_json=payload.discovery_metadata,
            discovered_at=payload.discovered_at,
        )
    )
    return 1


async def _insert_routing_outcome(
    db: AsyncSession,
    payload: ImportedCapabilityRoutingOutcome,
    *,
    dry_run: bool,
) -> int:
    existing = await db.get(CapabilityRoutingOutcome, payload.outcome_id)
    if existing is not None:
        return 0
    if dry_run:
        return 1
    outcome = CapabilityRoutingOutcome(
        id=payload.outcome_id,
        org_id=payload.org_id,
        provider_id=payload.provider_id,
        binding_id=payload.binding_id,
        capability_id=payload.capability_id,
        route_request_json=payload.route_request,
        route_plan_json=payload.route_plan,
        result_status=payload.result_status,
        success=payload.success,
        score=payload.score,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
        outcome_details_json=payload.outcome_details,
    )
    if payload.created_at is not None:
        outcome.created_at = payload.created_at
    if payload.updated_at is not None:
        outcome.updated_at = payload.updated_at
    db.add(outcome)
    return 1


async def import_capability_plane_bundle(
    db: AsyncSession,
    bundle: CapabilityPlaneImportBundle,
    *,
    dry_run: bool = False,
) -> CapabilityPlaneImportSummary:
    providers_upserted = 0
    profiles_upserted = 0
    bindings_upserted = 0
    snapshots_inserted = 0
    routing_outcomes_inserted = 0

    for provider in bundle.providers:
        provider_count, profile_count = await _upsert_provider(db, provider, dry_run=dry_run)
        providers_upserted += provider_count
        profiles_upserted += profile_count

    if not dry_run:
        await db.flush()

    for binding in bundle.bindings:
        bindings_upserted += await _upsert_binding(db, binding, dry_run=dry_run)

    if not dry_run:
        await db.flush()

    for snapshot in bundle.snapshots:
        snapshots_inserted += await _insert_snapshot(db, snapshot, dry_run=dry_run)

    for outcome in bundle.routing_outcomes:
        routing_outcomes_inserted += await _insert_routing_outcome(
            db,
            outcome,
            dry_run=dry_run,
        )

    if not dry_run:
        await db.commit()

    return CapabilityPlaneImportSummary(
        dry_run=dry_run,
        providers_upserted=providers_upserted,
        profiles_upserted=profiles_upserted,
        bindings_upserted=bindings_upserted,
        snapshots_inserted=snapshots_inserted,
        routing_outcomes_inserted=routing_outcomes_inserted,
    )


def load_capability_plane_import_bundle(payload: dict[str, Any]) -> CapabilityPlaneImportBundle:
    return CapabilityPlaneImportBundle.model_validate(payload)
