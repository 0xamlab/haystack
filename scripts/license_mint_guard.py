#!/usr/bin/env python3
"""Provisioning guardrail for PAID self-hosted license mints.

Self-hosted Algenta is priced PER ACTIVE NODE. The anti-fleet-abuse defense (so a customer can't take one
cheap license and run it across an entire server fleet) is: the license must carry FINITE, enforceable caps
and must NOT be an OEM / redistribution license. This module is the single, pure-stdlib check that both
``scripts/issue_offline_license.py`` (at mint time, behind ``--paid-selfhost``) and the golden tests
(``tests/test_license_mint_guard.py``) call, so the rule can't drift between the two.

What a paid self-host license MUST look like (else it's the fleet hole):
  * ``deployment_class`` != ``oem`` and ``oem`` claim not truthy — OEM is caps=0 / redistribution and is
    reserved for trusted-partner / sub-brand redistribution (scripts/issue_oem_license.py), NEVER a paying
    customer.
  * ``redistribution_allowed`` is false — a paid customer may run, not resell/redistribute.
  * ``commercial_use`` is true — it's a paid, commercial deployment.
  * FINITE caps — at least one enforceable ceiling > 0 (``active_node_limit`` for connected deployments, or
    ``concurrent_worker_limit`` for the runtime broker). A license with every cap 0 is uncapped = fleet-
    portable = exactly what we're preventing.
  * AIR-GAPPED deployments must be DEVICE-BOUND (``device_pubkey_thumbprint`` set) AND carry a finite
    ``concurrent_worker_limit`` > 0 — because offline the runtime self-enforces only the worker cap, not
    ``active_node_limit`` (a signed-but-not-runtime-enforced claim offline). Without binding, an air-gap
    token is portable across any machine within its worker cap.
  * ``offline_grace_days`` bounded (<= ``MAX_PAID_OFFLINE_GRACE_DAYS``) — indefinite offline grace is the
    OEM/never-phone-home shape, not a metered paid license.

None of this depends on the app package (it runs in the isolated minting script), so it imports nothing
beyond the stdlib.

Enforcement reminder (deployment-side, not mintable here): a connected paid self-host deployment must run
with ``ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1`` for the active-node-cap to be a true concurrent ceiling; when
off it counts every non-revoked device (legacy semantics) = effectively uncapped. The mint can't set the
customer's env, so the mint output/runbook must state this.
"""
from __future__ import annotations

from collections.abc import Mapping

# The env flag a connected paid self-host deployment MUST set for the active-node-cap to bind (kept here as
# the single source so the mint output + docs + tests reference one string).
ACTIVE_NODE_CAP_ENFORCE_ENV = "ALGENTA_ENFORCE_ACTIVE_NODE_CAP"
REQUIRE_LOCAL_LICENSE_ENV = "ALGENTA_REQUIRE_LOCAL_LICENSE"

# A paid, metered self-host license is not an indefinite OEM grant — bound its offline grace.
MAX_PAID_OFFLINE_GRACE_DAYS = 90


class LicenseMintGuardError(ValueError):
    """A would-be paid self-host license fails the anti-fleet-abuse guardrail."""


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _is_truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def paid_selfhost_violations(claims: Mapping[str, object]) -> list[str]:
    """Return the list of guardrail violations for a paid self-host claim set (empty = safe).

    Pure inspection — never raises, never mutates. ``assert_paid_selfhost_claims`` wraps this to raise.
    """
    violations: list[str] = []

    deployment_class = str(claims.get("deployment_class", "")).strip().lower()
    active_node_limit = _as_int(claims.get("active_node_limit"))
    worker_limit = _as_int(claims.get("concurrent_worker_limit"))
    grace_days = _as_int(claims.get("offline_grace_days"))
    thumbprint = str(claims.get("device_pubkey_thumbprint", "")).strip()

    # 1) Never an OEM / redistribution license for a paying customer — that's the fleet-portable shape.
    if deployment_class == "oem" or _is_truthy(claims.get("oem")):
        violations.append(
            "deployment_class is 'oem' (or oem=true): OEM licenses are uncapped/redistributable and are "
            "for trusted-partner redistribution only — mint paid self-host via issue_offline_license.py "
            "--paid-selfhost, never issue_oem_license.py."
        )
    if _is_truthy(claims.get("redistribution_allowed")):
        violations.append("redistribution_allowed is true: a paid self-host customer may run, not redistribute.")

    # 2) It's a paid, commercial deployment.
    if not _is_truthy(claims.get("commercial_use")):
        violations.append("commercial_use is false: a paid self-host license must grant commercial use.")

    # 3) FINITE caps — at least one enforceable ceiling. All-zero caps = uncapped = fleet-portable.
    if active_node_limit <= 0 and worker_limit <= 0:
        violations.append(
            "no finite caps: set --active-node-limit (connected) and/or --concurrent-worker-limit > 0. "
            "An all-zero-cap license runs on unlimited nodes — the exact fleet-abuse hole."
        )

    # 4) Air-gapped must be device-bound with a finite worker cap (active_node_limit is not runtime-enforced
    #    offline, so it's the only thing stopping one token from running on every air-gapped box).
    if deployment_class == "airgapped":
        if not thumbprint:
            violations.append(
                "air-gapped license is not device-bound: pass --device-pubkey-thumbprint (active_node_limit "
                "is not runtime-enforced offline, so an unbound air-gap token is portable across machines)."
            )
        if worker_limit <= 0:
            violations.append(
                "air-gapped license has no concurrent_worker_limit: offline, the worker cap is the only "
                "unit the runtime self-enforces — set --concurrent-worker-limit > 0."
            )

    # 5) Bounded offline grace — indefinite grace is the OEM/never-phone-home shape.
    if grace_days > MAX_PAID_OFFLINE_GRACE_DAYS:
        violations.append(
            f"offline_grace_days={grace_days} exceeds the paid ceiling {MAX_PAID_OFFLINE_GRACE_DAYS}: "
            "indefinite grace is an OEM grant, not a metered paid license."
        )

    return violations


def is_paid_selfhost_safe(claims: Mapping[str, object]) -> bool:
    """True if these claims are a safe paid self-host license (no guardrail violations)."""
    return not paid_selfhost_violations(claims)


def assert_paid_selfhost_claims(claims: Mapping[str, object]) -> None:
    """Raise ``LicenseMintGuardError`` if ``claims`` would be an abusable paid self-host license."""
    violations = paid_selfhost_violations(claims)
    if violations:
        raise LicenseMintGuardError(
            "paid self-host mint rejected by the anti-fleet-abuse guardrail:\n  - "
            + "\n  - ".join(violations)
        )
