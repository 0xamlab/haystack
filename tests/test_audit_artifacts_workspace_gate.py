"""Endpoint behavior for #7 (full fix): the Parquet audit-artifact endpoint now accepts a
workspace-scoped admin and returns results filtered to that workspace (per-workspace
filtering is proven at the service level in test_audit_service.py). Previously it returned an
interim 403; that gate is now replaced by real workspace_id filtering. Non-admins are still
blocked by require_role("admin").
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org


def _admin_auth(workspace_id) -> dict:
    return {
        "org_id": str(uuid.uuid4()),
        "user_id": "u",
        "key_id": "k",
        "role": "admin",
        "plan": "pro",
        "is_platform": True,
        "workspace_id": workspace_id,
    }


@pytest.mark.anyio
async def test_audit_artifacts_accepts_workspace_scoped_admin(client) -> None:
    # A workspace-scoped admin is now allowed (results are workspace-filtered, not 403-gated).
    async def _ws_admin() -> dict:
        return _admin_auth(uuid.uuid4())

    app.dependency_overrides[get_current_org] = _ws_admin
    try:
        resp = await client.get("/v1/audit-logs/artifacts")
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_audit_artifacts_allows_org_wide_admin(client) -> None:
    async def _org_admin() -> dict:
        return _admin_auth(None)  # unscoped platform / org-wide → sees all

    app.dependency_overrides[get_current_org] = _org_admin
    try:
        resp = await client.get("/v1/audit-logs/artifacts")
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)
