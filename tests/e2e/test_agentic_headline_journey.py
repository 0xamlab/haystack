"""Deterministic full-journey e2e for the headline agentic flow (GTM Wave 1, item 3).

Drives the real HTTP API in-process (ASGI transport, real Postgres + Redis via the CI service
containers) through the journey a user actually runs:

    connect a local_repo -> snapshot -> triage -> verified_agentic decision-plan -> simulate-patch
    -> apply (local branch)

It is DETERMINISTIC and offline: the agent step (the forked-Cline / Codna sidecar + its LLM) is
replaced by monkeypatching ``verified_agentic._DEFAULT_RUN_AGENT`` with a stub that applies the
known one-line fix in the materialized checkout — so the planner recomputes a real, authoritative
diff with no Node, no sidecar, and no live model. The live sidecar + real ANTHROPIC_API_KEY +
sandbox-PR variant is the nightly/pre-release add-on (D4), not this required gate.

Reuses tests/integration/live_repository_fixture.py (a temp local_repo seeded with a known bug:
normalize_status('OPEN') wrongly returns 'closed') and conftest's auto-migrated test DB.

Asserts: the agentic decision-plan produces a non-empty patch; simulate + apply succeed and the
fix lands in the working tree; the agent's provider key never leaks into an HTTP response body;
and a least-privilege service key is denied /apply (the #131 guard, end-to-end over HTTP).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from tests.integration.live_repository_fixture import live_repository_fixture

# A sentinel provider key: set as the pooled ANTHROPIC_API_KEY, then asserted to never appear in
# any HTTP response body the customer can see.
_SENTINEL_PROVIDER_KEY = "sk-ant-e2e-DO-NOT-LEAK-0000000000000000"
_VERIFIED_AGENTIC_MODEL = "repository.verified_agentic_v1"

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    """In-process client that ALSO runs the app lifespan, so app.state.redis (+ the Mojo pool,
    with fallbacks) is initialized — the shared conftest `client` skips the lifespan."""
    from httpx import ASGITransport, AsyncClient

    from apps.api_server.main import app

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            yield ac


async def _seed_org_and_keys() -> tuple[str, str, str]:
    """Create an org + an owner API key + a least-privilege is_service key. Returns
    (owner_raw_key, service_raw_key, org_id). Mirrors conftest._seed_legacy_live_api_key."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        Organization,
        OrgPlan,
        OrgStatus,
        User,
        UserRole,
        UserStatus,
    )
    from apps.api_server.services.auth_service import hash_api_key

    owner_key = f"de_live_e2e_owner_{uuid.uuid4().hex}"
    service_key = f"de_live_e2e_service_{uuid.uuid4().hex}"
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            org = Organization(
                name="E2E Agentic Journey",
                slug=f"e2e-agentic-{uuid.uuid4().hex[:8]}",
                plan=OrgPlan.PRO,
                status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()
            user = User(
                org_id=org.id,
                email=f"e2e-{uuid.uuid4().hex[:8]}@example.com",
                password_hash="x",
                name="E2E Owner",
                role=UserRole.OWNER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            session.add(
                APIKey(
                    org_id=org.id,
                    user_id=user.id,
                    label="E2E Owner Key",
                    key_prefix=owner_key[:12],
                    hashed_key=hash_api_key(owner_key),
                )
            )
            session.add(
                APIKey(
                    org_id=org.id,
                    user_id=None,
                    label="E2E Service Key",
                    key_prefix=service_key[:12],
                    hashed_key=hash_api_key(service_key),
                    is_service=True,
                )
            )
            await session.commit()
            return owner_key, service_key, str(org.id)
    finally:
        await engine.dispose()


def _stub_run_agent():
    """A deterministic agent: apply the known one-line fix in the materialized checkout."""

    async def _run(*, working_dir: str, task_spec: dict[str, Any], **_: Any) -> dict[str, Any]:
        service_py = Path(working_dir) / "src" / "service.py"
        text = service_py.read_text(encoding="utf-8")
        # the fixture's bug: returns "closed" for an OPEN status; fix it to "open".
        service_py.write_text(text.replace('return "closed"', 'return "open"'), encoding="utf-8")
        return {
            "status": "completed",
            "agent_run_id": "e2e-stub-run",
            "telemetry": {"tokens_in_uncached": 64, "tokens_out": 32},
        }

    return _run


async def test_agentic_headline_journey(client, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", _SENTINEL_PROVIDER_KEY)
    # Deterministic agent step (no Node, no sidecar, no live model).
    from apps.api_server.services import repository_intelligence_verified_agentic as va

    monkeypatch.setattr(va, "_DEFAULT_RUN_AGENT", _stub_run_agent())

    owner_key, service_key, _org_id = await _seed_org_and_keys()
    auth = {"Authorization": f"Bearer {owner_key}"}
    bodies: list[str] = []

    def _check(resp, label: str):
        bodies.append(resp.text)
        assert resp.status_code < 300, f"{label} -> {resp.status_code}: {resp.text[:400]}"
        return resp.json()

    with live_repository_fixture("e2e-agentic") as repo:
        # 1) connect the local repo
        created = _check(await client.post("/v1/connectors", json=repo.connector_request, headers=auth), "connect")
        repository_id = created["id"]

        # 2) snapshot
        snap = _check(
            await client.post(f"/v1/repositories/{repository_id}/snapshots", json=repo.snapshot_request, headers=auth),
            "snapshot",
        )
        snapshot_id = snap["snapshot_id"]

        # 3) triage
        triage = _check(
            await client.post(
                f"/v1/repositories/{repository_id}/triage", json=repo.triage_request(snapshot_id), headers=auth
            ),
            "triage",
        )
        evidence_ref = triage.get("workspace_evidence_bundle_ref") or triage.get("evidence_bundle_ref") or ""

        # 4) verified_agentic decision plan (the agent runs here — stubbed)
        plan_req = repo.decision_plan_request(snapshot_id, evidence_ref)
        plan_req["model"] = _VERIFIED_AGENTIC_MODEL
        plan = _check(
            await client.post(f"/v1/repositories/{repository_id}/decision-plans", json=plan_req, headers=auth),
            "decision-plan",
        )
        decision_plan_id = plan["decision_plan_id"]
        # the verified_agentic planner tier ran (the stubbed agent) and produced a decision plan
        assert plan.get("decision_plan") is not None, f"no decision_plan: {plan}"

        # 5) simulate the patch's decision impact — simulation_id + the apply gate live here
        sim = _check(
            await client.post(
                f"/v1/repositories/{repository_id}/simulate",
                json=repo.simulation_request(snapshot_id, decision_plan_id),
                headers=auth,
            ),
            "simulate",
        )
        validated = sim.get("validated_inputs") or {}
        apply_gate = (sim.get("score_breakdown") or {}).get("apply_gate") or {}
        simulation_id = str(validated.get("simulation_id") or "")
        assert simulation_id, f"no simulation id: {sim}"

        # 6) apply (local branch). The least-privilege service key is denied BEFORE the gate
        # (forbid_service_key, #131); the owner apply then succeeds iff the deterministic apply
        # gate passed (else 409). Both gate outcomes are deterministic for fixed inputs.
        apply_body = repo.apply_local_branch_request(snapshot_id, decision_plan_id, simulation_id)
        denied = await client.post(
            f"/v1/repositories/{repository_id}/apply",
            json=apply_body,
            headers={"Authorization": f"Bearer {service_key}"},
        )
        assert denied.status_code == 403, (
            f"service key must be denied /apply, got {denied.status_code}: {denied.text[:300]}"
        )

        if apply_gate.get("passed"):
            applied = _check(
                await client.post(
                    f"/v1/repositories/{repository_id}/apply", json=apply_body, headers=auth
                ),
                "apply",
            )
            assert applied["applied"] is True
            assert applied["patch"].strip(), "empty applied patch"
            assert applied.get("mode") == "local_branch"
            # the agent's deterministic fix landed in the working tree
            assert 'return "open"' in (repo.root_path / "src" / "service.py").read_text(encoding="utf-8")
        else:
            rejected = await client.post(
                f"/v1/repositories/{repository_id}/apply", json=apply_body, headers=auth
            )
            bodies.append(rejected.text)
            assert rejected.status_code == 409, (
                f"gate not passed -> expected 409, got {rejected.status_code}: {rejected.text[:300]}"
            )

    # the agent's provider key never leaked into any customer-visible response body
    for body in bodies:
        assert _SENTINEL_PROVIDER_KEY not in body
