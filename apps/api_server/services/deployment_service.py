"""Deployment activation — turn a resolved EntitlementSnapshot into a signed deployment license.

Organization-DEPLOYMENT scope (server, Compute Units) is activated explicitly (never inferred
from the host): a customer presents an org API key + a deployment identity + the deployment's
public-key thumbprint, and the control plane mints a strict-profile RS256 deployment license
bound to that deployment key, carrying the purchased Compute-Unit ceiling.

This module is the pure service seam (snapshot → signed token); the HTTP router and the
deployment-registration persistence wrap it. No usage measurement — the license carries the
PURCHASED capacity as a locally-enforced cap (owner policy).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.services.entitlement_snapshot import EntitlementSnapshot

# L3 census window — a node whose heartbeat is older than this frees its units (dead-node reclaim).
_DEFAULT_NODE_WINDOW_SECONDS = 600


class DeploymentActivationError(ValueError):
    """The deployment activation request is invalid (wrong scope, missing binding, etc.)."""


@dataclass(frozen=True)
class NodeAdmission:
    admitted: bool
    granted_units: int
    pool_units: int
    used_units: int  # total across active nodes AFTER this admission (or the blocking total)
    reason: str = ""


async def acquire_pool_advisory_lock(db: AsyncSession, namespace: str, key: str) -> None:
    """Transaction-scoped Postgres advisory lock serializing concurrent admissions against the
    SAME Compute-Unit ceiling (released at commit/rollback). The SUM-then-insert admission is not
    atomic under READ COMMITTED — without this, two concurrent requests for DIFFERENT keys each
    read a stale total and jointly overshoot the pool. Mirrors ``acquire_org_device_lock`` for the
    device path. No-op-safe on backends without advisory locks (SQLite tests) — best-effort."""
    from sqlalchemy import text

    try:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:ns), hashtext(:key))"),
            {"ns": namespace, "key": key},
        )
    except Exception:  # noqa: BLE001 — non-PG backend / no advisory locks: proceed unserialized
        pass


def _node_window_seconds() -> int:
    try:
        return max(120, int(os.environ.get("ALGENTA_DEPLOYMENT_NODE_WINDOW_SECONDS",
                                           str(_DEFAULT_NODE_WINDOW_SECONDS))))
    except (TypeError, ValueError):
        return _DEFAULT_NODE_WINDOW_SECONDS


async def admit_deployment_node(
    *,
    org_id: object,
    deployment_id: str,
    node_thumbprint: str,
    units: int,
    db: AsyncSession,
) -> NodeAdmission:
    """L3 connected-pool authority: admit (or refresh) an engine node against its deployment's
    Compute-Unit pool, counting units across ACTIVE peer nodes (heartbeat within the window).

    Fail-CLOSED on over-cap (never evicts a peer); idempotent per (deployment, node) — a node
    re-heartbeating updates its own lease and never double-counts. Returns a :class:`NodeAdmission`.
    Raises :class:`DeploymentActivationError` if the deployment isn't an active registration."""
    from apps.api_server.models.deployment_license import (
        DeploymentLicenseRegistration,
        DeploymentLicenseStatus,
        DeploymentNodeLease,
    )

    if units <= 0:
        raise DeploymentActivationError("units must be > 0")

    reg = (
        await db.execute(
            select(DeploymentLicenseRegistration).where(
                DeploymentLicenseRegistration.org_id == org_id,
                DeploymentLicenseRegistration.deployment_id == deployment_id,
                DeploymentLicenseRegistration.status == DeploymentLicenseStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if reg is None:
        raise DeploymentActivationError(
            f"deployment {deployment_id!r} is not an active registration for this org — activate it first"
        )

    # Serialize concurrent node admissions for THIS deployment so the SUM-then-insert can't be
    # raced by two nodes each reading a stale total and jointly overshooting the pool.
    await acquire_pool_advisory_lock(db, "algenta_deployment_node", str(reg.id))

    pool = int(reg.max_concurrent_units or 0)
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=_node_window_seconds())

    # Units held by OTHER active nodes (heartbeat within window), excluding this node.
    others = (
        await db.execute(
            select(func.coalesce(func.sum(DeploymentNodeLease.granted_units), 0)).where(
                DeploymentNodeLease.deployment_registration_id == reg.id,
                DeploymentNodeLease.node_thumbprint != node_thumbprint,
                DeploymentNodeLease.last_heartbeat_at.is_not(None),
                DeploymentNodeLease.last_heartbeat_at >= cutoff,
            )
        )
    ).scalar_one()
    used_others = int(others or 0)

    if used_others + units > pool:
        return NodeAdmission(
            admitted=False, granted_units=0, pool_units=pool, used_units=used_others,
            reason=(f"deployment pool exhausted: {used_others}/{pool} units held by active peers, "
                    f"{units} requested"),
        )

    # Admit: upsert this node's lease (idempotent on the unique (registration, node) constraint).
    existing = (
        await db.execute(
            select(DeploymentNodeLease).where(
                DeploymentNodeLease.deployment_registration_id == reg.id,
                DeploymentNodeLease.node_thumbprint == node_thumbprint,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            DeploymentNodeLease(
                deployment_registration_id=reg.id,
                node_thumbprint=node_thumbprint,
                granted_units=units,
                last_heartbeat_at=now,
            )
        )
    else:
        existing.granted_units = units
        existing.last_heartbeat_at = now
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent first heartbeat of the SAME node lost the unique-constraint race — reconcile
        # onto the winner's row rather than 500ing. (The advisory lock makes this rare; this is
        # the belt-and-suspenders tail for backends without advisory locks.)
        await db.rollback()
        row = (
            await db.execute(
                select(DeploymentNodeLease).where(
                    DeploymentNodeLease.deployment_registration_id == reg.id,
                    DeploymentNodeLease.node_thumbprint == node_thumbprint,
                )
            )
        ).scalar_one()
        row.granted_units = units
        row.last_heartbeat_at = now
        await db.commit()

    return NodeAdmission(
        admitted=True, granted_units=units, pool_units=pool, used_units=used_others + units
    )


def build_deployment_license(
    snapshot: EntitlementSnapshot,
    *,
    deployment_id: str,
    deployment_pubkey_thumbprint: str,
    ttl_days: int = 365,
    private_key_pem: str | None = None,
    kid: str = "",
    jti: str = "",
) -> str:
    """Mint the signed strict-profile deployment license for a resolved snapshot.

    Requires deployment scope and a deployment key thumbprint (the license is bound to it — a
    copied license file alone can't activate). Returns the RS256 JWT. ``jti`` lets the caller
    choose the license id up front (so its own record and the signed token agree without
    decoding the token back); empty means the minter generates one.
    """
    if snapshot.license_scope != "deployment":
        raise DeploymentActivationError(
            f"snapshot is {snapshot.license_scope!r} scope; deployment activation requires 'deployment'"
        )
    if not deployment_id:
        raise DeploymentActivationError("deployment_id is required")
    if not deployment_pubkey_thumbprint:
        raise DeploymentActivationError(
            "deployment_pubkey_thumbprint is required — the license must be bound to the deployment key"
        )
    units = int(snapshot.license_claims.get("max_concurrent_units", 0) or 0)
    if units <= 0:
        raise DeploymentActivationError(
            "resolved snapshot has no Compute-Unit ceiling — refusing to mint an uncapped deployment license"
        )

    from apps.runtime.license import mint_deployment_token

    return mint_deployment_token(
        org_id=snapshot.org_id,
        product=snapshot.product,
        edition=snapshot.edition,
        deployment_id=deployment_id,
        license_claims=snapshot.license_claims,
        device_pubkey_thumbprint=deployment_pubkey_thumbprint,
        ttl_days=ttl_days,
        jti=jti,
        kid=kid,
        private_key_pem=private_key_pem,
    )
