"""Golden tests for the paid self-host anti-fleet-abuse guardrail (scripts/license_mint_guard).

Self-hosted Algenta is priced PER ACTIVE NODE. The guardrail is the single check that stops a paid mint from
becoming a fleet-portable license (the "one $199 license across all of AWS's servers" hole). These tests pin
its exact rules and prove the OEM path can never masquerade as paid self-host.
"""
from __future__ import annotations

import pytest

from scripts.license_mint_guard import (
    MAX_PAID_OFFLINE_GRACE_DAYS,
    LicenseMintGuardError,
    assert_paid_selfhost_claims,
    is_paid_selfhost_safe,
    paid_selfhost_violations,
)


def _paid_selfhost(**overrides: object) -> dict[str, object]:
    """A well-formed paid, connected, per-node self-host claim set (server, 3 nodes, finite worker cap)."""
    claims: dict[str, object] = {
        "deployment_class": "server",
        "commercial_use": True,
        "redistribution_allowed": False,
        "active_node_limit": 3,
        "concurrent_worker_limit": 4,
        "named_seat_limit": 5,
        "offline_grace_days": 14,
        "device_pubkey_thumbprint": "",
    }
    claims.update(overrides)
    return claims


# ── the safe shape passes ─────────────────────────────────────────────────────────
def test_wellformed_paid_selfhost_passes() -> None:
    claims = _paid_selfhost()
    assert paid_selfhost_violations(claims) == []
    assert is_paid_selfhost_safe(claims) is True
    assert_paid_selfhost_claims(claims)  # does not raise


def test_worker_only_cap_is_finite_enough() -> None:
    # A connected mint that caps workers but not nodes still has a finite ceiling → allowed.
    assert is_paid_selfhost_safe(_paid_selfhost(active_node_limit=0, concurrent_worker_limit=2))


# ── the fleet-abuse shapes are rejected ────────────────────────────────────────────
def test_oem_deployment_class_rejected() -> None:
    with pytest.raises(LicenseMintGuardError, match="oem"):
        assert_paid_selfhost_claims(_paid_selfhost(deployment_class="oem"))


def test_oem_flag_rejected() -> None:
    assert not is_paid_selfhost_safe(_paid_selfhost(oem=True))


def test_redistribution_rejected() -> None:
    with pytest.raises(LicenseMintGuardError, match="redistribut"):
        assert_paid_selfhost_claims(_paid_selfhost(redistribution_allowed=True))


def test_uncapped_all_zero_rejected() -> None:
    # The core hole: every cap 0 = runs on unlimited nodes.
    with pytest.raises(LicenseMintGuardError, match="no finite caps"):
        assert_paid_selfhost_claims(_paid_selfhost(active_node_limit=0, concurrent_worker_limit=0))


def test_non_commercial_rejected() -> None:
    with pytest.raises(LicenseMintGuardError, match="commercial_use"):
        assert_paid_selfhost_claims(_paid_selfhost(commercial_use=False))


def test_offline_grace_over_ceiling_rejected() -> None:
    with pytest.raises(LicenseMintGuardError, match="offline_grace_days"):
        assert_paid_selfhost_claims(_paid_selfhost(offline_grace_days=MAX_PAID_OFFLINE_GRACE_DAYS + 1))
    # exactly at the ceiling is fine
    assert is_paid_selfhost_safe(_paid_selfhost(offline_grace_days=MAX_PAID_OFFLINE_GRACE_DAYS))


# ── air-gapped must be device-bound with a finite worker cap ────────────────────────
def test_airgapped_requires_device_binding() -> None:
    violations = paid_selfhost_violations(
        _paid_selfhost(deployment_class="airgapped", device_pubkey_thumbprint="")
    )
    assert any("device-bound" in v for v in violations)


def test_airgapped_requires_worker_cap() -> None:
    # active_node_limit is NOT runtime-enforced offline, so an air-gap mint that relies only on it is unsafe.
    violations = paid_selfhost_violations(
        _paid_selfhost(
            deployment_class="airgapped",
            device_pubkey_thumbprint="abc123",
            active_node_limit=3,
            concurrent_worker_limit=0,
        )
    )
    assert any("worker" in v.lower() for v in violations)


def test_airgapped_device_bound_with_worker_cap_passes() -> None:
    # Air-gapped is enterprise-only (self-serve tiers must stay connected so renewal is sub-gated).
    assert is_paid_selfhost_safe(
        _paid_selfhost(
            deployment_class="airgapped",
            plan="enterprise",
            device_pubkey_thumbprint="thumb-xyz",
            concurrent_worker_limit=2,
        )
    )


def test_airgapped_requires_enterprise_plan() -> None:
    # A non-enterprise (self-serve) air-gap mint is the pay-once-leave hole: no renewal check offline.
    violations = paid_selfhost_violations(
        _paid_selfhost(
            deployment_class="airgapped",
            plan="algenta_selfhost",
            device_pubkey_thumbprint="thumb-xyz",
            concurrent_worker_limit=2,
        )
    )
    assert any("enterprise" in v for v in violations)


# ── the OEM minter's output can NEVER pass as paid self-host ─────────────────────────
def test_oem_claims_are_rejected_as_paid_selfhost() -> None:
    """build_oem_claims() is the trusted-partner/sub-brand shape (caps=0, deployment_class=oem,
    redistribution, ~100y). Feeding it to the paid-self-host guard MUST fail — you cannot mint an OEM license
    and pass it off as a paid per-node customer license."""
    import scripts.issue_oem_license as oem

    claims = oem.build_oem_claims(
        product="codna",
        tier="team",
        features=["*"],
        customer="acme",
        org_id="acme",
        exp_years=100,
        grace_days=3650,
        license_id="lic-1",
        now=1_700_000_000,
    )
    violations = paid_selfhost_violations(claims)
    assert violations, "OEM claims must be rejected by the paid self-host guard"
    # It trips the OEM + redistribution + uncapped rules specifically.
    joined = " ".join(violations).lower()
    assert "oem" in joined
    assert "finite caps" in joined or "redistribut" in joined


# ── the algenta_selfhost tier, minted for real, is a safe paid license ──────────────
def test_algenta_selfhost_entitlement_claims_pass_the_guard() -> None:
    """The algenta_selfhost tier → license claims must satisfy the guard (it's the paid per-node tier)."""
    from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims

    rec = resolve_entitlement("algenta_selfhost")
    claims = to_license_claims(rec)
    assert claims["deployment_class"] == "server"
    assert claims["commercial_use"] is True
    assert claims["redistribution_allowed"] is False
    assert int(claims["active_node_limit"]) >= 1
    assert is_paid_selfhost_safe(claims), paid_selfhost_violations(claims)
