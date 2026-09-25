"""Idempotent delete/cancel family — live end-to-end coverage (real API + Postgres).

One test per DB-backed tool: first delete/cancel performs the real mutation exactly
once, a repeat returns success with already_absent (no 404, no duplicate audit or
state churn), and a never-existing id returns success with already_absent. The
delete_decision test additionally asserts the audit_events table records the real
deletion exactly once across repeats.

Requires the live fixtures (real Postgres, CI). The DB-free siblings (delete_trigger,
cancel_agent_run, annotation contract, MCP envelope) live in
tests/test_idempotent_delete_family.py.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path

import httpx
import pytest

from tests._mcp_live_server_fixture import live_api_server, seed_owner_org_and_key


@pytest.fixture(scope="module")
def runtime_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="idem-del-live-runtime-"))


@pytest.fixture(scope="module")
def live_server(runtime_dir: Path):
    with live_api_server(runtime_dir=runtime_dir) as base_url:
        yield base_url


@pytest.fixture(scope="module")
def owner_auth(live_server: str) -> tuple[str, str]:
    del live_server
    return asyncio.run(seed_owner_org_and_key("idem-del"))


def _client(owner_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {owner_key}"},
        timeout=30.0,
    )


async def _audit_count(action: str, resource_id: str) -> int:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models.audit_event import AuditEvent

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == action, AuditEvent.resource_id == resource_id)
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def test_delete_connector_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    async with _client(owner_key) as client:
        created = (
            await client.post(
                f"{live_server}/v1/connectors",
                json={"name": "idem-pg", "connector_type": "postgres"},
            )
        )
        assert created.status_code == 201, created.text
        connector_id = created.json()["id"]

        first = await client.delete(f"{live_server}/v1/connectors/{connector_id}")
        assert first.status_code == 204, first.text

        second = await client.delete(f"{live_server}/v1/connectors/{connector_id}")
        assert second.status_code == 200, second.text
        assert second.json() == {
            "connector_id": connector_id,
            "deleted": True,
            "already_absent": True,
        }

        ghost = await client.delete(f"{live_server}/v1/connectors/{uuid.uuid4()}")
        assert ghost.status_code == 200
        assert ghost.json()["already_absent"] is True


async def test_disconnect_data_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    async with _client(owner_key) as client:
        registered = (
            await client.post(
                f"{live_server}/v1/sources/register",
                json={"source": {"name": "idem_src", "records": [{"a": 1}, {"a": 2}]}},
            )
        )
        assert registered.status_code == 200, registered.text
        source_id = registered.json()["source_id"]

        first = await client.delete(f"{live_server}/v1/data/{source_id}")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "deleted"
        assert "already_absent" not in first.json()

        second = await client.delete(f"{live_server}/v1/data/{source_id}")
        assert second.status_code == 200
        assert second.json()["already_absent"] is True

        ghost = await client.delete(f"{live_server}/v1/data/ds-ghost-{uuid.uuid4().hex[:8]}")
        assert ghost.status_code == 200
        assert ghost.json()["already_absent"] is True


async def test_delete_decision_first_repeat_ghost_and_single_audit(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    async with _client(owner_key) as client:
        logged = (
            await client.post(
                f"{live_server}/v1/decisions",
                json={"chosen_action": "hold", "context": "idempotency fixture"},
            )
        )
        assert logged.status_code in (200, 201), logged.text
        decision_id = logged.json()["id"]

        first = await client.delete(f"{live_server}/v1/decisions/{decision_id}")
        assert first.status_code == 204, first.text

        for _ in range(2):
            repeat = await client.delete(f"{live_server}/v1/decisions/{decision_id}")
            assert repeat.status_code == 200, repeat.text
            assert repeat.json() == {
                "decision_id": decision_id,
                "deleted": True,
                "already_absent": True,
            }

        ghost = await client.delete(f"{live_server}/v1/decisions/{uuid.uuid4()}")
        assert ghost.status_code == 200
        assert ghost.json()["already_absent"] is True

    assert await _audit_count("decision.delete", decision_id) == 1


async def test_delete_deployment_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    async with _client(owner_key) as client:
        created = (
            await client.post(
                f"{live_server}/v1/deployments",
                json={"provider": "algenta_shared", "region": "algenta-shared"},
            )
        )
        assert created.status_code == 202, created.text
        deployment_id = created.json()["deployment_id"]

        first = await client.delete(f"{live_server}/v1/deployments/{deployment_id}")
        assert first.status_code == 202, first.text
        assert first.json()["status"] == "deprovisioning"

        # The deprovision task is async; wait for it to settle before the repeat so
        # the already-absent branch is exercised deterministically (the provision/
        # deprovision race is inherent to the async design, not to the contract).
        await _wait_for_deployment_status(deployment_id, "deprovisioned")

        second = await client.delete(f"{live_server}/v1/deployments/{deployment_id}")
        assert second.status_code == 202, second.text
        assert second.json()["already_absent"] is True

        ghost = await client.delete(f"{live_server}/v1/deployments/{uuid.uuid4()}")
        assert ghost.status_code == 202
        assert ghost.json()["already_absent"] is True


async def _wait_for_deployment_status(deployment_id: str, want: str, timeout_s: float = 20.0) -> None:
    import time

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models.deployment import Deployment

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            async with factory() as session:
                row = (
                    await session.execute(
                        select(Deployment.status).where(Deployment.id == uuid.UUID(deployment_id))
                    )
                ).scalar_one_or_none()
                if row == want or (row is not None and getattr(row, "value", row) == want):
                    return
            await asyncio.sleep(0.25)
    finally:
        await engine.dispose()
    raise AssertionError(f"deployment {deployment_id} never reached {want}")


async def test_disable_skill_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    skill = f"idem-skill-{uuid.uuid4().hex[:8]}"
    async with _client(owner_key) as client:
        created = (
            await client.post(
                f"{live_server}/v1/capability-bindings",
                json={
                    "provider_id": "provider.skill_pack.algenta",
                    "profile_id": "profile.skill_pack.user",
                    "binding_name": skill,
                    "scope": "user",
                    "execution_owner": "client_managed",
                    "config": {
                        "manifest": {
                            "capabilities": [
                                {
                                    "capability_id": f"cap.skill.{skill}",
                                    "name": skill,
                                    "kind": "skill",
                                    "implementation_kind": "instruction_only",
                                    "execution_owner": "client_managed",
                                    "instruction": "Always answer tersely.",
                                }
                            ]
                        }
                    },
                },
            )
        )
        assert created.status_code == 201, created.text
        binding_id = created.json()["binding_id"]

        first = await client.delete(f"{live_server}/v1/capability-bindings/{binding_id}")
        assert first.status_code == 204, first.text

        second = await client.delete(f"{live_server}/v1/capability-bindings/{binding_id}")
        assert second.status_code == 200, second.text
        assert second.json() == {
            "binding_id": binding_id,
            "disabled": True,
            "already_absent": True,
        }

        ghost = await client.delete(f"{live_server}/v1/capability-bindings/{uuid.uuid4()}")
        assert ghost.status_code == 200
        assert ghost.json()["already_absent"] is True


async def test_cancel_job_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, _ = owner_auth
    async with _client(owner_key) as client:
        submitted = (
            await client.post(
                f"{live_server}/v1/jobs",
                json={
                    "request": {
                        "mode": "auto",
                        "scenario": {
                            "name": "idempotency fixture",
                            "variables": {"revenue": {"low": 1, "high": 2}},
                            "objective": "maximize_net_value",
                        },
                        "runs": 1000,
                    }
                },
            )
        )
        assert submitted.status_code in (200, 201, 202), submitted.text
        job_id = submitted.json()["job_id"]

        first = await client.post(f"{live_server}/v1/jobs/{job_id}/cancel")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "cancelled"
        assert "already_absent" not in first.json()
        completed_at_first = first.json()["completed_at"]

        second = await client.post(f"{live_server}/v1/jobs/{job_id}/cancel")
        assert second.status_code == 200, second.text
        assert second.json()["already_absent"] is True
        assert second.json()["status"] == "cancelled"
        assert second.json()["completed_at"] == completed_at_first, (
            "repeat must not re-transition the job row"
        )

        ghost = await client.post(f"{live_server}/v1/jobs/{uuid.uuid4()}/cancel")
        assert ghost.status_code == 200
        assert ghost.json() == {
            "job_id": ghost.json()["job_id"],
            "status": "cancelled",
            "already_absent": True,
        }


async def test_remove_team_member_first_repeat_and_ghost(live_server: str, owner_auth) -> None:
    owner_key, org_id = owner_auth
    member_id = await _seed_member(org_id, "idem-member")
    async with _client(owner_key) as client:
        first = await client.delete(f"{live_server}/v1/team/{member_id}")
        assert first.status_code == 204, first.text

        second = await client.delete(f"{live_server}/v1/team/{member_id}")
        assert second.status_code == 200, second.text
        assert second.json() == {
            "removed": True,
            "user_id": member_id,
            "already_absent": True,
        }

        ghost = await client.delete(f"{live_server}/v1/team/{uuid.uuid4()}")
        assert ghost.status_code == 200
        assert ghost.json()["already_absent"] is True


async def _seed_member(org_id: str, label: str) -> str:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import User, UserRole, UserStatus

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = User(
                org_id=uuid.UUID(org_id),
                email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
                password_hash="x",
                name=label,
                role=UserRole.MEMBER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.commit()
            return str(user.id)
    finally:
        await engine.dispose()
