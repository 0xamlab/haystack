from __future__ import annotations

from uuid import uuid4
import uuid

import pytest
from sqlalchemy import func, select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models import (
    CapabilityBinding,
    CapabilityProvider,
    CapabilityProviderProfile,
    CapabilityRoutingOutcome,
    CapabilitySnapshot,
    Organization,
    OrgPlan,
    OrgStatus,
)
from apps.api_server.services.capability_plane_importer import (
    import_capability_plane_bundle,
    load_capability_plane_import_bundle,
)


async def _seed_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="Capability Import Test Org",
            slug=f"capability-import-{uuid4().hex[:12]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.commit()
        return str(org.id)


@pytest.mark.anyio
async def test_capability_plane_importer_supports_dry_run_and_persisted_import() -> None:
    org_id = await _seed_org()
    binding_id = str(uuid4())
    snapshot_id = str(uuid4())
    outcome_id = str(uuid4())

    bundle = load_capability_plane_import_bundle(
        {
            "providers": [
                {
                    "provider_id": "provider.skill_pack.customer_import",
                    "provider_type": "skill_pack",
                    "name": "Imported Skills",
                    "supported_execution_owners": ["client_managed"],
                    "profiles": [
                        {
                            "profile_id": "profile.skill_pack.customer_import",
                            "provider_id": "provider.skill_pack.customer_import",
                            "name": "Imported User Skills",
                            "default_execution_owner": "client_managed",
                            "binding_scope_default": "user",
                            "supported_binding_scopes": ["user"],
                        }
                    ],
                }
            ],
            "bindings": [
                {
                    "binding_id": binding_id,
                    "org_id": org_id,
                    "provider_id": "provider.skill_pack.customer_import",
                    "profile_id": "profile.skill_pack.customer_import",
                    "binding_name": "Imported Escalation Skill",
                    "scope": "user",
                    "scope_ref": "user-123",
                    "status": "ready",
                    "execution_owner": "client_managed",
                    "config": {
                        "manifest": {
                            "capabilities": [
                                {
                                    "capability_id": "cap.skill.imported_escalation",
                                    "name": "Imported Escalation Skill",
                                    "kind": "skill",
                                }
                            ]
                        }
                    },
                }
            ],
            "snapshots": [
                {
                    "snapshot_id": snapshot_id,
                    "binding_id": binding_id,
                    "org_id": org_id,
                    "manifest_hash": "manifest-hash-1",
                    "content_hash": "content-hash-1",
                    "manifest": {"capabilities": [{"capability_id": "cap.skill.imported_escalation"}]},
                    "discovered_at": "2026-05-29T12:00:00Z",
                }
            ],
            "routing_outcomes": [
                {
                    "outcome_id": outcome_id,
                    "org_id": org_id,
                    "provider_id": "provider.skill_pack.customer_import",
                    "binding_id": binding_id,
                    "capability_id": "cap.skill.imported_escalation",
                    "route_request": {"objective": "Escalate incident"},
                    "route_plan": {"selected_capability_id": "cap.skill.imported_escalation"},
                    "result_status": "completed",
                    "success": True,
                    "confidence": 0.9,
                    "created_at": "2026-05-29T12:00:01Z",
                    "updated_at": "2026-05-29T12:00:02Z",
                }
            ],
        }
    )

    async with AsyncSessionLocal() as session:
        dry_run = await import_capability_plane_bundle(session, bundle, dry_run=True)
        assert dry_run.dry_run is True
        assert dry_run.providers_upserted == 1
        assert dry_run.profiles_upserted == 1
        assert dry_run.bindings_upserted == 1
        assert dry_run.snapshots_inserted == 1
        assert dry_run.routing_outcomes_inserted == 1

    async with AsyncSessionLocal() as session:
        persisted = await import_capability_plane_bundle(session, bundle, dry_run=False)
        assert persisted.dry_run is False
        assert persisted.providers_upserted == 1
        assert persisted.profiles_upserted == 1
        assert persisted.bindings_upserted == 1
        assert persisted.snapshots_inserted == 1
        assert persisted.routing_outcomes_inserted == 1

    async with AsyncSessionLocal() as session:
        provider_count = await session.scalar(
            select(func.count()).select_from(CapabilityProvider).where(
                CapabilityProvider.provider_id == "provider.skill_pack.customer_import"
            )
        )
        profile_count = await session.scalar(
            select(func.count()).select_from(CapabilityProviderProfile).where(
                CapabilityProviderProfile.profile_id == "profile.skill_pack.customer_import"
            )
        )
        binding_count = await session.scalar(
            select(func.count()).select_from(CapabilityBinding).where(
                CapabilityBinding.id == uuid.UUID(binding_id)
            )
        )
        snapshot_count = await session.scalar(
            select(func.count()).select_from(CapabilitySnapshot).where(
                CapabilitySnapshot.id == uuid.UUID(snapshot_id)
            )
        )
        outcome_count = await session.scalar(
            select(func.count()).select_from(CapabilityRoutingOutcome).where(
                CapabilityRoutingOutcome.id == uuid.UUID(outcome_id)
            )
        )
        assert provider_count == 1
        assert profile_count == 1
        assert binding_count == 1
        assert snapshot_count == 1
        assert outcome_count == 1
