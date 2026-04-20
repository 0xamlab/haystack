"""
RBAC middleware unit tests.

Tests the require_role() dependency factory and role-rank logic
without any database or HTTP stack.
"""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ── Role rank helpers ─────────────────────────────────────────────────────────

def test_role_rank_ordering():
    """viewer < member < admin < owner."""
    from apps.api_server.middleware.rbac import _rank
    assert _rank("viewer") < _rank("member")
    assert _rank("member") < _rank("admin")
    assert _rank("admin") < _rank("owner")


def test_role_rank_unknown_defaults_to_viewer():
    """Unknown roles get viewer rank (0); known roles are normalized to lowercase."""
    from apps.api_server.middleware.rbac import _rank
    assert _rank("superuser") == 0
    assert _rank("") == 0
    assert _rank("OWNER") == _rank("owner")


def test_require_role_invalid_minimum_raises():
    """Passing an unknown minimum_role should raise ValueError at import time."""
    from apps.api_server.middleware.rbac import require_role
    with pytest.raises(ValueError, match="Unknown role"):
        require_role("superadmin")


# ── Dependency behaviour ──────────────────────────────────────────────────────

def _make_auth(role: str) -> dict:
    return {
        "org_id": uuid4(),
        "key_id": uuid4(),
        "plan": "developer",
        "role": role,
        "email": f"{role}@example.com",
    }


def _make_request():
    req = MagicMock()
    req.url.path = "/v1/test"
    req.method = "POST"
    return req


@pytest.mark.asyncio
async def test_require_role_passes_sufficient_role():
    """An owner calling require_role("admin") must succeed."""
    from apps.api_server.middleware.rbac import require_role

    dep = require_role("admin")
    auth = _make_auth("owner")

    # Patch get_current_org to return our auth directly
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "apps.api_server.middleware.rbac.get_current_org", return_value=auth
    ):
        # We call the inner _dependency directly
        result = await dep(request=_make_request(), auth=auth)
        assert result["role"] == "owner"


@pytest.mark.asyncio
async def test_require_role_passes_exact_role():
    """An admin calling require_role("admin") must succeed."""

    from apps.api_server.middleware.rbac import require_role

    dep = require_role("admin")
    auth = _make_auth("admin")

    result = await dep(request=_make_request(), auth=auth)
    assert result["role"] == "admin"


@pytest.mark.asyncio
async def test_require_role_blocks_insufficient_role():
    """A viewer calling require_role("admin") must raise HTTP 403."""
    from fastapi import HTTPException

    from apps.api_server.middleware.rbac import require_role

    dep = require_role("admin")
    auth = _make_auth("viewer")

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=_make_request(), auth=auth)

    assert exc_info.value.status_code == 403
    detail: dict = exc_info.value.detail  # type: ignore[assignment]
    error: dict = detail["error"]
    assert error["code"] == "access_scope_denied"
    assert error["required_role"] == "admin"
    assert error["your_role"] == "viewer"
    assert error["details"] == [{"field": "role", "issue": "insufficient_role"}]


@pytest.mark.asyncio
async def test_require_role_member_blocks_viewer():
    """A viewer calling require_role("member") must raise 403."""
    from fastapi import HTTPException

    from apps.api_server.middleware.rbac import require_role

    dep = require_role("member")
    auth = _make_auth("viewer")

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=_make_request(), auth=auth)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_owner_only_blocks_admin():
    """An admin calling require_role("owner") must raise 403."""
    from fastapi import HTTPException

    from apps.api_server.middleware.rbac import require_role

    dep = require_role("owner")
    auth = _make_auth("admin")

    with pytest.raises(HTTPException) as exc_info:
        await dep(request=_make_request(), auth=auth)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_viewer_read_allowed():
    """A viewer calling require_role("viewer") (read-only) must succeed."""
    from apps.api_server.middleware.rbac import require_role

    dep = require_role("viewer")
    auth = _make_auth("viewer")

    result = await dep(request=_make_request(), auth=auth)
    assert result["role"] == "viewer"


# ── AuthContext role/email fields ─────────────────────────────────────────────

def test_auth_context_has_role_and_email():
    """AuthContext TypedDict must declare role and email fields."""
    from apps.api_server.services.auth_service import AuthContext
    ctx: AuthContext = {
        "org_id": uuid4(),
        "key_id": uuid4(),
        "plan": "free",
        "role": "owner",
        "email": "owner@test.com",
    }
    assert ctx["role"] == "owner"
    assert ctx["email"] == "owner@test.com"


# ── Dependency name for OpenAPI ───────────────────────────────────────────────

def test_require_role_sets_function_name():
    """The returned dependency must have a stable __name__ for OpenAPI."""
    from apps.api_server.middleware.rbac import require_role
    dep = require_role("admin")
    assert dep.__name__ == "require_admin_role"

    dep2 = require_role("owner")
    assert dep2.__name__ == "require_owner_role"
