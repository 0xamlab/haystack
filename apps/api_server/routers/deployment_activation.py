"""Deployment activation endpoint — the connected path to a server (Compute-Unit) license.

``POST /v1/deployment/activate``: an org on a ``*_server`` plan presents a deployment identity +
the deployment's public-key thumbprint and receives a signed, bound, strict-profile deployment
license carrying its purchased Compute-Unit ceiling. The offline counterpart is
``scripts/issue_offline_license.py --license-scope deployment``.

No usage measurement — the license is a locally-enforced capacity cap (owner policy: runs on
their infra, no phone-home).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.deployment_license import (
    DeploymentLicenseRegistration,
    DeploymentLicenseStatus,
)
from apps.api_server.models.organization import Organization
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["deployment"])


class DeploymentActivateRequest(BaseModel):
    deployment_id: str = Field(..., min_length=1, max_length=128)
    deployment_pubkey_thumbprint: str = Field(..., min_length=1, max_length=128)
    # Compute Units to allocate to THIS deployment out of the org's purchased pool. Omit (0) to
    # take the remaining pool. The sum across an org's active deployments can never exceed the
    # purchased pool — so N purchased units stay N total, split across deployments (never N×K).
    units: int = Field(default=0, ge=0, le=1_000_000)
    ttl_days: int = Field(default=365, ge=1, le=3660)


class DeploymentNodeHeartbeatRequest(BaseModel):
    deployment_id: str = Field(..., min_length=1, max_length=128)
    node_thumbprint: str = Field(..., min_length=1, max_length=128)
    units: int = Field(..., ge=1, le=1_000_000)


class DeploymentNodeHeartbeatResponse(BaseModel):
    admitted: bool
    granted_units: int
    pool_units: int
    used_units: int
    reason: str = ""


class DeploymentActivateResponse(BaseModel):
    license_token: str
    deployment_id: str
    product: str
    max_concurrent_units: int  # units allocated to THIS deployment
    pool_units: int  # the org's total purchased pool
    pool_allocated_units: int  # units allocated across all of the org's active deployments
    license_jti: str


def _product_for_plan(plan: str) -> str:
    return (plan or "").split("_", 1)[0]


@router.post(
    "/v1/deployment/activate",
    response_model=DeploymentActivateResponse,
    summary="Activate an organization server deployment and mint its Compute-Unit license",
)
async def activate_deployment(
    body: DeploymentActivateRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentActivateResponse:
    from apps.api_server.services.deployment_service import (
        DeploymentActivationError,
        build_deployment_license,
    )
    from apps.api_server.services.entitlement_service import entitlement_for_org
    from apps.api_server.services.entitlement_snapshot import (
        SOURCE_STRIPE,
        snapshot_from_record,
    )

    org = (
        await db.execute(select(Organization).where(Organization.id == ctx["org_id"]))
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    record = entitlement_for_org(org)
    if not record.is_deployment_scope():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "no_deployment_entitlement",
                "message": (
                    "This organization's plan does not grant server (deployment) licensing. "
                    "Upgrade to a *_server plan or contact sales for an enterprise pool."
                ),
            },
        )

    plan = str(ctx.get("plan") or getattr(org.plan, "value", org.plan) or "")
    product = _product_for_plan(plan)
    pool_units = int(record.max_concurrent_units or 0)

    # Serialize concurrent activations for THIS org so two activations of DIFFERENT deployment_ids
    # can't each read a stale allocated-total and jointly over-provision the purchased pool.
    from apps.api_server.services.deployment_service import acquire_pool_advisory_lock

    await acquire_pool_advisory_lock(db, "algenta_org_deployment_alloc", str(org.id))

    # Aggregate cap: the org's purchased pool is shared across ALL its deployments. Sum the units
    # already allocated to OTHER active deployments; this activation may take at most the remainder.
    # (Fixes the over-provisioning hole where N purchased units could mint N per deployment_id.)
    others_rows = (
        await db.execute(
            select(DeploymentLicenseRegistration).where(
                DeploymentLicenseRegistration.org_id == org.id,
                DeploymentLicenseRegistration.deployment_id != body.deployment_id,
                DeploymentLicenseRegistration.status == DeploymentLicenseStatus.ACTIVE,
            )
        )
    ).scalars().all()
    allocated_elsewhere = sum(int(r.max_concurrent_units or 0) for r in others_rows)
    remaining = max(0, pool_units - allocated_elsewhere)
    requested = int(body.units) if body.units else remaining
    if requested < 1:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pool_exhausted",
                "message": (
                    f"Compute-Unit pool exhausted: {allocated_elsewhere}/{pool_units} units are "
                    f"allocated to other deployments; none remain for this one."
                ),
            },
        )
    if allocated_elsewhere + requested > pool_units:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pool_exceeded",
                "message": (
                    f"Requested {requested} units + {allocated_elsewhere} already allocated exceeds "
                    f"the purchased pool of {pool_units}."
                ),
            },
        )

    # Mint a license carrying THIS deployment's slice (requested), not the whole org pool.
    from dataclasses import replace as _replace

    per_deployment_record = _replace(record, max_concurrent_units=requested)
    snapshot = snapshot_from_record(
        source_type=SOURCE_STRIPE,
        org_id=str(org.id),
        product=product,
        edition="server",
        record=per_deployment_record,
    )

    try:
        token = build_deployment_license(
            snapshot,
            deployment_id=body.deployment_id,
            deployment_pubkey_thumbprint=body.deployment_pubkey_thumbprint,
            ttl_days=body.ttl_days,
        )
    except DeploymentActivationError as exc:
        raise HTTPException(status_code=422, detail={"error": "activation_invalid", "message": str(exc)}) from exc
    except ValueError as exc:
        # e.g. signing key not configured on this control plane
        logger.error("deployment_signing_unavailable", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail={"error": "signing_unavailable", "message": "deployment license signing is not configured"},
        ) from exc

    # Decode our own token (unverified) only to capture the jti for the audit/revocation record.
    import jwt as _jwt

    license_jti = str(_jwt.decode(token, options={"verify_signature": False}).get("jti", ""))
    now = datetime.now(UTC)

    existing = (
        await db.execute(
            select(DeploymentLicenseRegistration).where(
                DeploymentLicenseRegistration.org_id == org.id,
                DeploymentLicenseRegistration.deployment_id == body.deployment_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            DeploymentLicenseRegistration(
                org_id=org.id,
                api_key_id=ctx.get("api_key_id"),
                deployment_id=body.deployment_id,
                product=product,
                max_concurrent_units=requested,
                deployment_pubkey_thumbprint=body.deployment_pubkey_thumbprint,
                license_jti=license_jti,
                status=DeploymentLicenseStatus.ACTIVE,
                last_activated_at=now,
            )
        )
    else:
        existing.product = product
        existing.max_concurrent_units = requested
        existing.deployment_pubkey_thumbprint = body.deployment_pubkey_thumbprint
        existing.license_jti = license_jti
        existing.status = DeploymentLicenseStatus.ACTIVE
        existing.last_activated_at = now
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent first-time activation of the same (org_id, deployment_id) lost the unique-
        # constraint race — reconcile onto the row the winner inserted instead of 500ing.
        await db.rollback()
        row = (
            await db.execute(
                select(DeploymentLicenseRegistration).where(
                    DeploymentLicenseRegistration.org_id == org.id,
                    DeploymentLicenseRegistration.deployment_id == body.deployment_id,
                )
            )
        ).scalar_one()
        row.product = product
        row.max_concurrent_units = requested
        row.deployment_pubkey_thumbprint = body.deployment_pubkey_thumbprint
        row.license_jti = license_jti
        row.status = DeploymentLicenseStatus.ACTIVE
        row.last_activated_at = now
        await db.commit()

    logger.info(
        "deployment_activated",
        org_id=str(org.id),
        deployment_id=body.deployment_id,
        product=product,
        units=requested,
        pool_units=pool_units,
        pool_allocated=allocated_elsewhere + requested,
    )
    return DeploymentActivateResponse(
        license_token=token,
        deployment_id=body.deployment_id,
        product=product,
        max_concurrent_units=requested,
        pool_units=pool_units,
        pool_allocated_units=allocated_elsewhere + requested,
        license_jti=license_jti,
    )


@router.post(
    "/v1/deployment/node/heartbeat",
    response_model=DeploymentNodeHeartbeatResponse,
    summary="L3 connected-pool: admit/renew an engine node's Compute-Unit lease against the pool",
)
async def deployment_node_heartbeat(
    body: DeploymentNodeHeartbeatRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentNodeHeartbeatResponse:
    from apps.api_server.services.deployment_service import (
        DeploymentActivationError,
        admit_deployment_node,
    )

    try:
        result = await admit_deployment_node(
            org_id=ctx["org_id"],
            deployment_id=body.deployment_id,
            node_thumbprint=body.node_thumbprint,
            units=body.units,
            db=db,
        )
    except DeploymentActivationError as exc:
        raise HTTPException(status_code=404, detail={"error": "deployment_not_active", "message": str(exc)}) from exc

    if not result.admitted:
        # Over the pool — fail closed (the node must reduce units or the org must buy more).
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pool_exhausted",
                "message": result.reason,
                "pool_units": result.pool_units,
                "used_units": result.used_units,
            },
        )
    return DeploymentNodeHeartbeatResponse(
        admitted=True,
        granted_units=result.granted_units,
        pool_units=result.pool_units,
        used_units=result.used_units,
    )
