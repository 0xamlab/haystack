"""Wave 2 cleanup: per-org storage-cap enforcement (the deferred half of PR-3's storage_gb cap).

The cap source of truth is a live S3 ListObjectsV2 sum (no counter to drift; objects expire via the
bucket's 90-day lifecycle). Enforcement is OFF by default (ALGENTA_ENFORCE_STORAGE_CAP) and never
fires off-S3, so self-host + CI are unaffected. Covers the cap math, the env switches, the
fail-closed 413 gate, off-S3 short-circuit, and the /v1/usage surface.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.services import storage_accounting_service as sas
from apps.api_server.services import storage_service

_GIB = 1024**3


# ── Cap math + switches (pure) ──────────────────────────────────────────────────


def test_resolve_storage_cap_bytes_per_plan():
    assert sas.resolve_storage_cap_bytes("free") == 1 * _GIB
    assert sas.resolve_storage_cap_bytes("developer") == 10 * _GIB
    assert sas.resolve_storage_cap_bytes("pro") == 100 * _GIB
    assert sas.resolve_storage_cap_bytes("enterprise") == 0  # unlimited


def test_enforcement_switch_reads_env(monkeypatch):
    monkeypatch.delenv("ALGENTA_ENFORCE_STORAGE_CAP", raising=False)
    assert sas.storage_enforcement_enabled() is False
    monkeypatch.setenv("ALGENTA_ENFORCE_STORAGE_CAP", "1")
    assert sas.storage_enforcement_enabled() is True
    monkeypatch.setenv("ALGENTA_ENFORCE_STORAGE_CAP", "off")
    assert sas.storage_enforcement_enabled() is False


def test_compute_org_storage_bytes_short_circuits_off_s3(monkeypatch):
    # Off-S3 (node-local self-host): no S3 call, returns 0. Proven by making _get_client explode —
    # compute must short-circuit before reaching it.
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)

    def _boom(*a, **k):
        raise AssertionError("S3 client must not be built when the RI store is node-local")

    monkeypatch.setattr(storage_service, "_get_client", _boom)
    assert storage_service.compute_org_storage_bytes(uuid.uuid4()) == 0


def test_compute_org_storage_bytes_fails_open_on_error(monkeypatch):
    # On-S3 but the list errors → fail OPEN (0), never raise into the request.
    monkeypatch.setenv("ALGENTA_RI_OBJECT_STORE", "s3")
    monkeypatch.setattr(storage_service, "_get_client", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("s3 down")))
    assert storage_service.compute_org_storage_bytes(uuid.uuid4()) == 0


# ── The gate ────────────────────────────────────────────────────────────────────


def _patch_used(monkeypatch, used_bytes: int):
    async def _fake_used(org_id):
        return used_bytes

    monkeypatch.setattr(sas, "get_org_storage_bytes", _fake_used)


async def test_gate_noop_when_disabled_even_over_cap(monkeypatch):
    monkeypatch.delenv("ALGENTA_ENFORCE_STORAGE_CAP", raising=False)
    _patch_used(monkeypatch, 5 * _GIB)  # way over free's 1 GB
    await sas.gate_storage_cap(uuid.uuid4(), "free")  # no raise — enforcement off


async def test_gate_blocks_over_cap_with_413(monkeypatch):
    monkeypatch.setenv("ALGENTA_ENFORCE_STORAGE_CAP", "1")
    _patch_used(monkeypatch, 2 * _GIB)  # over free's 1 GB
    with pytest.raises(HTTPException) as exc:
        await sas.gate_storage_cap(uuid.uuid4(), "free")
    assert exc.value.status_code == 413
    assert exc.value.detail["error"]["code"] == "storage_cap_exceeded"


async def test_gate_allows_under_cap(monkeypatch):
    monkeypatch.setenv("ALGENTA_ENFORCE_STORAGE_CAP", "1")
    _patch_used(monkeypatch, 100 * 1024 * 1024)  # 100 MB < 1 GB
    await sas.gate_storage_cap(uuid.uuid4(), "free")  # no raise


async def test_gate_unlimited_plan_never_blocks(monkeypatch):
    monkeypatch.setenv("ALGENTA_ENFORCE_STORAGE_CAP", "1")
    # enterprise = unlimited (cap 0): over_storage_cap short-circuits without even summing.
    called = {"n": 0}

    async def _used(org_id):
        called["n"] += 1
        return 999 * _GIB

    monkeypatch.setattr(sas, "get_org_storage_bytes", _used)
    await sas.gate_storage_cap(uuid.uuid4(), "enterprise")  # no raise
    assert called["n"] == 0  # unlimited path never queries usage


# ── /v1/usage surface ─────────────────────────────────────────────────────────────


async def test_usage_response_surfaces_storage(monkeypatch):
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
    from apps.api_server.routers.account import usage

    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)  # off-S3 → used = 0
    async with AsyncSessionLocal() as s:
        org = Organization(
            name="Storage Surface", slug=f"stor-{uuid.uuid4().hex[:8]}",
            plan=OrgPlan.FREE, status=OrgStatus.ACTIVE,
        )
        s.add(org)
        await s.commit()
        org_id = org.id

    auth = {"org_id": org_id, "plan": "free", "workspace_id": None}
    async with AsyncSessionLocal() as s:
        resp = await usage(auth=auth, db=s)  # type: ignore[arg-type]
    assert resp.storage_gb_limit == 1  # FREE plan cap
    assert resp.storage_bytes_used == 0  # off-S3 in tests
