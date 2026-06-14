"""Wave 2 PR-1: account-status + email-verification auth gates.

Unit-level coverage of the two enforcement points added to middleware/auth.py:
  - _enforce_account_status: every protected request from a suspended/deleted org or a suspended
    user is rejected with 403 (runs in get_current_org, covering both the DB and Redis-cache paths);
  - require_verified_email: agentic/expensive endpoints require a verified email (service keys exempt);
plus a wiring assertion that the agentic routers actually carry the require_verified_email dependency.
"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

from apps.api_server.middleware.auth import _enforce_account_status, require_verified_email


def _request():
    return types.SimpleNamespace(state=types.SimpleNamespace(request_id="test-req"))


def _ctx(**overrides):
    base = {
        "org_status": "active",
        "user_status": "active",
        "email_verified": True,
        "is_service": False,
    }
    base.update(overrides)
    return base


# ── _enforce_account_status (suspension) ──────────────────────────────────────


def test_suspended_org_is_blocked():
    with pytest.raises(HTTPException) as exc:
        _enforce_account_status(_ctx(org_status="suspended"), _request())
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "organization_suspended"


def test_deleted_org_is_blocked():
    with pytest.raises(HTTPException) as exc:
        _enforce_account_status(_ctx(org_status="deleted"), _request())
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "organization_suspended"


def test_suspended_user_is_blocked():
    with pytest.raises(HTTPException) as exc:
        _enforce_account_status(_ctx(user_status="suspended"), _request())
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "account_suspended"


def test_active_account_passes():
    # No raise for an active org + active user.
    _enforce_account_status(_ctx(), _request())


# ── require_verified_email (agentic gate) ─────────────────────────────────────


def test_unverified_email_is_blocked():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_verified_email(_ctx(email_verified=False)))
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "email_verification_required"


def test_verified_email_passes():
    ctx = _ctx(email_verified=True)
    assert asyncio.run(require_verified_email(ctx)) is ctx


def test_service_key_is_exempt_from_email_verification():
    # Machine credentials have no human email — never gated.
    ctx = _ctx(email_verified=False, is_service=True)
    assert asyncio.run(require_verified_email(ctx)) is ctx


# ── wiring: the agentic routers actually attach the gate ──────────────────────


def test_agentic_routers_require_verified_email():
    # The full expensive/agentic surface — provider-backed (llm) + the Monte-Carlo simulate family
    # (simulate/decisions/products/recommend/whatif/stream) + mojo exec (runtime_libraries) + agent
    # runs + repository ops + async jobs. Gating a subset would be trivially bypassable via a sibling
    # endpoint that runs the same compute, so this asserts the whole set.
    from apps.api_server.routers import (
        agent_runs,
        decisions,
        jobs,
        llm,
        products,
        recommend,
        repositories,
        runtime_libraries,
        simulate,
        stream,
        whatif,
    )

    gated = (
        simulate,
        agent_runs,
        jobs,
        repositories,
        llm,
        decisions,
        products,
        recommend,
        whatif,
        stream,
        runtime_libraries,
    )
    for module in gated:
        deps = [getattr(d, "dependency", None) for d in (module.router.dependencies or [])]
        assert require_verified_email in deps, (
            f"{module.__name__}.router is missing the require_verified_email dependency"
        )
