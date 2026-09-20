"""Wave 2 PR-5c: fail-closed env-separation startup guards + the managed-spend /v1/usage surface.

validate_environment_separation refuses to boot on a dangerous cross-environment config; the
defaults (dev + placeholder Stripe + managed/strict off) pass untouched so self-host/CI is unaffected.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.config import Settings
from apps.api_server.services.env_separation import validate_environment_separation


def _settings(api_env: str, stripe_secret_key: str = "sk_test_placeholder"):
    return SimpleNamespace(api_env=api_env, stripe_secret_key=stripe_secret_key)


# ── Guard 1: a LIVE Stripe key is only allowed in production ───────────────────────


def test_live_stripe_key_off_production_refuses_to_boot():
    for env in ("development", "staging", "test"):
        with pytest.raises(RuntimeError, match="LIVE key"):
            validate_environment_separation(_settings(env, "sk_live_realkey123"))


def test_live_stripe_key_in_production_is_allowed():
    validate_environment_separation(_settings("production", "sk_live_realkey123"))  # no raise


def test_test_stripe_key_off_production_is_fine():
    validate_environment_separation(_settings("staging", "sk_test_abc"))  # no raise
    validate_environment_separation(_settings("development", "sk_test_placeholder"))  # no raise


# ── Guard 2: managed-LLM mode and strict per-tenant keys are mutually exclusive ──────


def test_managed_and_strict_together_refuses_to_boot(monkeypatch):
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    with pytest.raises(RuntimeError, match="contradictory"):
        validate_environment_separation(_settings("production", "sk_live_x"))


def test_managed_or_strict_alone_is_fine(monkeypatch):
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    monkeypatch.setenv("ALGENTA_MANAGED_LLM", "1")
    validate_environment_separation(_settings("production", "sk_live_x"))  # managed only — fine

    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.setenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", "1")
    validate_environment_separation(_settings("production", "sk_live_x"))  # strict only — fine


def test_defaults_pass(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    validate_environment_separation(_settings("development", "sk_test_placeholder"))  # no raise


# ── Guard 3: the session-JWT secret may not be the shipped placeholder in production ──


def _settings_with_jwt(api_env: str, jwt_secret: str):
    return SimpleNamespace(
        api_env=api_env, stripe_secret_key="sk_test_placeholder", jwt_secret=jwt_secret
    )


def test_placeholder_jwt_secret_in_production_refuses_to_boot(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    placeholder = Settings.model_fields["jwt_secret"].default
    docs_style = (
        "<paste-output-of-openssl-rand-hex-32-here>",
        "change-me-in-production",
        "<set-me>",
    )
    for bad in (placeholder, "", "   ", None, *docs_style):
        with pytest.raises(RuntimeError, match="placeholder"):
            validate_environment_separation(_settings_with_jwt("production", bad))


def test_self_host_doc_jwt_placeholders_are_refused_in_production(monkeypatch):
    # Whatever JWT_SECRET value the self-hosting guide shows must never boot a production server
    # verbatim — this pins the docs and the guard to each other so neither can drift alone.
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    doc = Path(__file__).resolve().parents[1] / "apps" / "docs" / "docs" / "self-hosting.md"
    values = re.findall(r"(?m)^JWT_SECRET=(.*)$", doc.read_text(encoding="utf-8"))
    assert values, "self-hosting.md no longer shows a JWT_SECRET line"
    for value in values:
        with pytest.raises(RuntimeError, match="placeholder"):
            validate_environment_separation(_settings_with_jwt("production", value.strip()))


def test_placeholder_jwt_secret_off_production_is_fine(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    placeholder = Settings.model_fields["jwt_secret"].default
    for env in ("development", "staging", "test"):
        validate_environment_separation(_settings_with_jwt(env, placeholder))  # no raise


def test_real_jwt_secret_in_production_is_allowed(monkeypatch):
    monkeypatch.delenv("ALGENTA_MANAGED_LLM", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_PER_TENANT_KEYS", raising=False)
    validate_environment_separation(_settings_with_jwt("production", "a" * 64))  # no raise


def test_settings_without_jwt_attribute_skip_guard_three():
    # Only an ABSENT attribute skips the guard (existing partial test doubles); a present-but-None
    # value is treated as blank and refused — covered above.
    validate_environment_separation(_settings("production", "sk_live_realkey123"))  # no raise


# ── /v1/usage surfaces managed-LLM spend + cap ──────────────────────────────────────


async def test_usage_response_surfaces_managed_spend():
    # Call the /v1/usage handler directly (no middleware/redis): seed an org + a managed LLM call,
    # confirm the response carries the managed spend + the plan's cap.
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.llm_usage_record import LLMKeyType
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
    from apps.api_server.routers.account import usage
    from apps.api_server.services.llm_spend_service import record_llm_usage

    async with AsyncSessionLocal() as s:
        org = Organization(
            name="Usage Surface", slug=f"usage-{uuid.uuid4().hex[:8]}",
            plan=OrgPlan.PRO, status=OrgStatus.ACTIVE,
        )
        s.add(org)
        await s.commit()
        org_id = org.id
        await record_llm_usage(
            org_id=org_id, backend="anthropic", model="claude-sonnet-4-6",
            key_type=LLMKeyType.MANAGED, prompt_tokens=1_000, completion_tokens=1_000, db=s,
        )
        await s.commit()

    auth = {"org_id": org_id, "plan": "pro", "workspace_id": None}
    async with AsyncSessionLocal() as s:
        resp = await usage(auth=auth, db=s)  # type: ignore[arg-type]
    assert resp.managed_llm_cap_usd_month == 200  # PRO plan default cap
    # 1k·$3/Mtok + 1k·$15/Mtok = 18_000 µ$ = $0.018.
    assert resp.managed_llm_spend_usd_month == pytest.approx(0.018)


async def test_usage_response_unlimited_plan_reports_zero_cap():
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
    from apps.api_server.routers.account import usage

    async with AsyncSessionLocal() as s:
        org = Organization(
            name="Usage Ent", slug=f"usage-{uuid.uuid4().hex[:8]}",
            plan=OrgPlan.ENTERPRISE, status=OrgStatus.ACTIVE,
        )
        s.add(org)
        await s.commit()
        org_id = org.id

    auth = {"org_id": org_id, "plan": "enterprise", "workspace_id": None}
    async with AsyncSessionLocal() as s:
        resp = await usage(auth=auth, db=s)  # type: ignore[arg-type]
    assert resp.managed_llm_cap_usd_month == 0  # enterprise = unlimited
    assert resp.managed_llm_spend_usd_month == 0.0
