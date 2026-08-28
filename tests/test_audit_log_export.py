"""B1: the audit log tells the truth, and an export can be verified.

TWO THINGS ARE UNDER TEST, and the first matters more than the second.

1. THE FABRICATED ROWS ARE GONE. `/v1/audit-logs` used to call `_generate_demo_audit_log()` whenever
   the query came back empty, returning three invented entries: actors that do not exist
   (owner@algenta.ai, admin@algenta.ai, viewer@algenta.ai), invented client IPs in 203.0.113.0/24,
   and an invented `access_denied` event against the audit log itself. An operator whose audit table
   was genuinely empty -- a fresh install, or a tenant with nothing logged yet -- saw security
   events that never happened and had no way to tell them from real ones. On an audit surface that
   is worse than an error: an error is visible, whereas plausible fiction is trusted. These tests
   assert the emptiness is honest AND that none of those specific fabrications can reappear.

2. `GET /v1/audit-logs/export.{fmt}` returns `X-Content-SHA256` over the exact bytes sent, so a
   recipient can prove the file was not altered in transit or afterwards. The tests verify by
   re-hashing the downloaded body -- the same operation an auditor would perform -- rather than by
   trusting the server's own arithmetic.

Everything here runs against the REAL router, the REAL SQLAlchemy models and a REAL Postgres (the
session-scoped migration fixture in conftest). Only the caller's identity is injected, via the
`get_current_org` dependency override that the existing audit tests use -- authentication is not
what is under test, and stubbing the database would make the hash assertions meaningless.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid

import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org

FABRICATED_MARKERS = (
    "owner@algenta.ai",
    "admin@algenta.ai",
    "viewer@algenta.ai",
    "203.0.113.",
    '"source": "demo"',
    '"source":"demo"',
)


def _admin(org_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> dict:
    return {
        "org_id": str(org_id),
        "user_id": "u",
        "key_id": "k",
        "role": "admin",
        "plan": "pro",
        "is_platform": True,
        "workspace_id": workspace_id,
    }


def _member(org_id: uuid.UUID) -> dict:
    return dict(_admin(org_id), role="member", is_platform=False)


async def _seed(org_id: uuid.UUID, rows: list[dict]) -> None:
    """Insert real audit_events rows for `org_id` through the real model.

    The org row is created first because `audit_events.org_id` carries a real foreign key to
    `organizations.id` -- inserting audit rows for an org that does not exist raises
    ForeignKeyViolationError. Worth stating plainly: that constraint is what makes these tests
    meaningful. A stubbed session would have accepted the orphaned rows and the hash assertions
    would have been checking bytes the database would never actually produce.
    """
    import os

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models.audit_event import AuditEvent
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(
                Organization(
                    id=org_id,
                    name=f"audit-export-test-{org_id}",
                    slug=f"audit-export-test-{org_id}",
                    plan=OrgPlan.PRO,
                    status=OrgStatus.ACTIVE,
                )
            )
            await session.flush()
            for r in rows:
                session.add(AuditEvent(org_id=org_id, **r))
            await session.commit()
    finally:
        await engine.dispose()


# ── 1. the fabrications are gone ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_an_empty_audit_table_returns_an_honestly_empty_page(client) -> None:
    """A fresh org has no audit events, so the page must report none -- not three invented ones."""
    org_id = uuid.uuid4()  # never seeded: genuinely empty
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        resp = await client.get("/v1/audit-logs")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 0, f"expected an empty audit log, got {body['total']} entries"
        assert body["entries"] == [], f"fabricated entries returned: {body['entries']}"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_no_fabricated_actor_or_ip_can_appear_in_the_response(client) -> None:
    """Belt-and-braces on the exact strings the stub produced, so a reintroduction is caught."""
    org_id = uuid.uuid4()
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        raw = (await client.get("/v1/audit-logs")).text
        for marker in FABRICATED_MARKERS:
            assert marker not in raw, f"fabricated audit data is back in the response: {marker!r}"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_the_generator_itself_is_gone_from_the_source() -> None:
    """The function must not merely be unreferenced -- it must not exist to be re-wired."""
    from pathlib import Path

    import apps.api_server.routers.team as team_mod

    src = Path(team_mod.__file__).read_text(encoding="utf-8")
    assert "def _generate_demo_audit_log" not in src, (
        "_generate_demo_audit_log has been reintroduced; an empty audit table must return an "
        "empty page, never invented entries"
    )
    assert not hasattr(team_mod, "_generate_demo_audit_log")


@pytest.mark.anyio
async def test_real_rows_are_returned_unchanged(client) -> None:
    """The honest-empty change must not have broken the path that returns actual rows."""
    org_id = uuid.uuid4()
    await _seed(org_id, [
        {"actor_email": "real.person@example.test", "action": "simulate",
         "resource_type": "simulation_run", "resource_id": "r-1",
         "ip_address": "198.51.100.7", "result": "success"},
    ])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        body = (await client.get("/v1/audit-logs")).json()
        assert body["total"] == 1, body
        assert body["entries"][0]["actor_email"] == "real.person@example.test"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


# ── 2. the export, and its hash ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize("fmt", ["csv", "json"])
async def test_the_content_hash_verifies_by_rehashing_the_download(client, fmt: str) -> None:
    """Re-hash the body exactly as an auditor would; it must equal the advertised digest."""
    org_id = uuid.uuid4()
    await _seed(org_id, [
        {"actor_email": f"a{i}@example.test", "action": "execute_decision",
         "resource_type": "decision", "resource_id": f"d-{i}",
         "ip_address": "198.51.100.1", "result": "success",
         "metadata_json": json.dumps({"policy_snapshot_id": f"ps-{i}"})}
        for i in range(3)
    ])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        resp = await client.get(f"/v1/audit-logs/export.{fmt}")
        assert resp.status_code == 200, resp.text
        advertised = resp.headers.get("X-Content-SHA256")
        assert advertised, "export must carry X-Content-SHA256"
        assert hashlib.sha256(resp.content).hexdigest() == advertised, (
            "the advertised digest does not match the bytes delivered -- the header would give a "
            "recipient false assurance"
        )
        assert resp.headers["X-Audit-Export-Rows"] == "3"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_the_export_is_byte_stable_across_identical_requests(client) -> None:
    """Two exports of the same rows must hash identically, or verification is not reproducible."""
    org_id = uuid.uuid4()
    await _seed(org_id, [
        {"actor_email": "z@example.test", "action": "b", "result": "success",
         "metadata_json": json.dumps({"b": 2, "a": 1})},
        {"actor_email": "y@example.test", "action": "a", "result": "failure"},
    ])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        first = await client.get("/v1/audit-logs/export.json")
        second = await client.get("/v1/audit-logs/export.json")
        assert first.content == second.content
        assert first.headers["X-Content-SHA256"] == second.headers["X-Content-SHA256"]
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_metadata_key_order_in_storage_cannot_change_the_digest(client) -> None:
    """Two rows whose metadata differs only in stored key ORDER must serialise identically.

    This is what `sort_keys=True` is for, and the reason it needs its own test: comparing two
    exports within one process cannot detect its absence, because dict iteration order is already
    stable there. Mutation-checked -- dropping sort_keys leaves the byte-stability test green and
    fails this one. Without it, two servers (or one server before and after a metadata rewrite)
    could produce different digests for identical audit content, and a verifier would report
    tampering that never happened.
    """
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    # Same mapping, opposite insertion order, byte-different JSON text in the column.
    await _seed(org_a, [{"actor_email": "m@example.test", "action": "k", "result": "success",
                         "metadata_json": '{"alpha": 1, "beta": 2}'}])
    await _seed(org_b, [{"actor_email": "m@example.test", "action": "k", "result": "success",
                         "metadata_json": '{"beta": 2, "alpha": 1}'}])

    def _metadata_blob(payload: str) -> str:
        entries = json.loads(payload)
        assert len(entries) == 1, entries
        return json.dumps(entries[0]["metadata"], sort_keys=False, separators=(",", ":"))

    app.dependency_overrides[get_current_org] = lambda: _admin(org_a)
    try:
        a_body = (await client.get("/v1/audit-logs/export.json")).text
    finally:
        app.dependency_overrides.pop(get_current_org, None)
    app.dependency_overrides[get_current_org] = lambda: _admin(org_b)
    try:
        b_body = (await client.get("/v1/audit-logs/export.json")).text
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    assert _metadata_blob(a_body) == _metadata_blob(b_body), (
        "stored metadata key order changed the exported bytes; the export must canonicalise it so "
        "identical audit content always yields the same digest"
    )


@pytest.mark.anyio
async def test_csv_export_parses_and_carries_the_declared_columns(client) -> None:
    org_id = uuid.uuid4()
    await _seed(org_id, [
        {"actor_email": "c@example.test", "action": "query", "resource_type": "dataset",
         "resource_id": "ds-9", "ip_address": "198.51.100.2", "result": "success"},
    ])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        resp = await client.get("/v1/audit-logs/export.csv")
        assert resp.headers["content-type"].startswith("text/csv")
        rows = list(csv.reader(io.StringIO(resp.text)))
        assert rows[0] == ["id", "timestamp", "actor_email", "action",
                           "resource_type", "resource_id", "ip_address", "result", "metadata"]
        assert rows[1][2] == "c@example.test"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_one_orgs_export_never_contains_anothers_rows(client) -> None:
    """workspace_scope_clauses is the tenant boundary; without it this is a cross-tenant leak."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await _seed(org_a, [{"actor_email": "a@tenant-a.test", "action": "x", "result": "success"}])
    await _seed(org_b, [{"actor_email": "b@tenant-b.test", "action": "y", "result": "success"}])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_a)
    try:
        text = (await client.get("/v1/audit-logs/export.json")).text
        assert "a@tenant-a.test" in text
        assert "b@tenant-b.test" not in text, "another tenant's audit rows leaked into this export"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_export_filters_agree_with_the_paginated_view(client) -> None:
    """Both surfaces share one filter helper, so an export must equal what the operator reviewed."""
    org_id = uuid.uuid4()
    await _seed(org_id, [
        {"actor_email": "keep@example.test", "action": "simulate", "result": "success"},
        {"actor_email": "drop@example.test", "action": "invite_member", "result": "success"},
    ])
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        page = (await client.get("/v1/audit-logs", params={"action": "simulate"})).json()
        exported = json.loads((await client.get(
            "/v1/audit-logs/export.json", params={"action": "simulate"})).text)
        assert page["total"] == 1
        assert [e["actor_email"] for e in exported] == [e["actor_email"] for e in page["entries"]]
        assert "drop@example.test" not in json.dumps(exported)
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_an_unsupported_format_is_refused(client) -> None:
    org_id = uuid.uuid4()
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        resp = await client.get("/v1/audit-logs/export.xlsx")
        assert resp.status_code == 400, resp.text
        assert "csv" in resp.text and "json" in resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_a_non_admin_cannot_export_the_audit_log(client) -> None:
    """The audit trail is admin-only; require_role("admin") must gate the export as well."""
    org_id = uuid.uuid4()
    app.dependency_overrides[get_current_org] = lambda: _member(org_id)
    try:
        resp = await client.get("/v1/audit-logs/export.json")
        assert resp.status_code == 403, f"a non-admin exported the audit log: {resp.status_code}"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_an_empty_export_is_still_hash_verifiable(client) -> None:
    """An org with nothing logged gets an empty, still-verifiable artifact -- not fabricated rows."""
    org_id = uuid.uuid4()
    app.dependency_overrides[get_current_org] = lambda: _admin(org_id)
    try:
        resp = await client.get("/v1/audit-logs/export.json")
        assert resp.status_code == 200
        assert json.loads(resp.text) == []
        assert hashlib.sha256(resp.content).hexdigest() == resp.headers["X-Content-SHA256"]
        for marker in FABRICATED_MARKERS:
            assert marker not in resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)
