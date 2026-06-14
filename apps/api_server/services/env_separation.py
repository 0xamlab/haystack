"""Fail-closed staging/prod environment-separation guards (Wave 2 PR-5c).

Run at startup (lifespan), mirroring ``validate_billing_configuration``. Refuse to boot on a config
that crosses an environment boundary in a *dangerous* direction — the kind of mistake that, on a
hosted multi-tenant deploy, would charge real cards from a staging box or silently disable
managed-LLM billing. Each check fails closed (RuntimeError) with a remediation message.
"""

from __future__ import annotations

import structlog

from apps.api_server.config import Settings, get_settings
from apps.api_server.services.tenant_keys import managed_llm_mode_enabled, require_per_tenant_keys

logger = structlog.get_logger(__name__)


def validate_environment_separation(current_settings: Settings | None = None) -> None:
    """Fail closed on dangerous cross-environment configuration. Safe defaults (dev + placeholder
    Stripe + managed/strict off) pass untouched, so this never breaks self-host or CI."""
    s = current_settings or get_settings()
    env = (s.api_env or "").strip().lower()

    # 1) A LIVE Stripe key outside production means a staging/dev box could charge real customers.
    secret = getattr(s, "stripe_secret_key", "") or ""
    if env != "production" and secret.startswith("sk_live_"):
        raise RuntimeError(
            f"Refusing to start: api_env={s.api_env!r} but STRIPE_SECRET_KEY is a LIVE key "
            "(sk_live_…). A non-production deployment must use a Stripe TEST key so it can never "
            "charge real customers — use sk_test_… here, or set api_env=production."
        )

    # 2) Managed-LLM mode and strict BYOK-only are mutually exclusive: strict forbids the shared
    # pooled key that managed pass-through hands out, so managed-LLM would silently never fire.
    # Refuse rather than boot a deployment whose managed billing is dead-on-arrival.
    if managed_llm_mode_enabled() and require_per_tenant_keys():
        raise RuntimeError(
            "Refusing to start: ALGENTA_MANAGED_LLM=1 and ALGENTA_REQUIRE_PER_TENANT_KEYS=1 are "
            "contradictory — strict per-tenant mode forbids the pooled key managed pass-through "
            "depends on, so managed-LLM would never fire. Enable exactly one."
        )

    logger.info(
        "environment_separation_validated",
        env=s.api_env,
        managed_llm=managed_llm_mode_enabled(),
        require_per_tenant_keys=require_per_tenant_keys(),
    )
