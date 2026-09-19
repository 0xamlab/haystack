"""Deployment activation endpoint — the connected path to a server (Compute-Unit) license.

``POST /v1/deployment/activate``: an org on a ``*_server`` plan presents a deployment identity +
the deployment's public-key thumbprint and receives a signed, bound, strict-profile deployment
license carrying its purchased Compute-Unit ceiling. The offline counterpart is
``scripts/issue_offline_license.py --license-scope deployment``.

No usage measurement — the license is a locally-enforced capacity cap (owner policy: runs on
their infra, no phone-home).
"""
from __future__ import annotations

import base64
import os
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
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


def _deployment_pop_required() -> bool:
    """When set, a node must PROVE possession of its deployment key (sign a server nonce) to
    heartbeat — so an org API key alone can't spoof/register node identities it doesn't control.
    Default OFF (back-compat: API-key-only heartbeat); hardened production sets it. A request that
    supplies PoP fields is always verified regardless, so honest clients get checked either way."""
    return os.environ.get("ALGENTA_REQUIRE_DEPLOYMENT_POP", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _pop_nonce_key(org_id: object, deployment_id: str, node_thumbprint: str) -> str:
    return f"deployment_pop_nonce:{org_id}:{deployment_id}:{node_thumbprint}"


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
    # Proof-of-possession (optional unless ALGENTA_REQUIRE_DEPLOYMENT_POP): the node signs the
    # server nonce from /v1/deployment/node/challenge with its deployment key.
    nonce: str = Field(default="", max_length=256)  # base64, echoed from the challenge
    public_key_pem: str = Field(default="", max_length=4096)
    signature: str = Field(default="", max_length=1024)  # base64


class DeploymentNodeChallengeRequest(BaseModel):
    deployment_id: str = Field(..., min_length=1, max_length=128)
    node_thumbprint: str = Field(..., min_length=1, max_length=128)


class DeploymentNodeChallengeResponse(BaseModel):
    nonce: str  # base64; sign this with the deployment key and echo it back on heartbeat


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

    # The license id is chosen HERE and handed to the minter, so the audit/revocation record
    # and the signed token share one jti by construction -- there is nothing to read back out
    # of the token afterwards (the old flow decoded our own freshly minted JWT unverified
    # just to learn its jti).
    license_jti = str(uuid.uuid4())
    try:
        token = build_deployment_license(
            snapshot,
            deployment_id=body.deployment_id,
            deployment_pubkey_thumbprint=body.deployment_pubkey_thumbprint,
            ttl_days=body.ttl_days,
            jti=license_jti,
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
    "/v1/deployment/node/challenge",
    response_model=DeploymentNodeChallengeResponse,
    summary="Issue a single-use nonce for deployment-node proof-of-possession",
)
async def deployment_node_challenge(
    body: DeploymentNodeChallengeRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    request: Request,
) -> DeploymentNodeChallengeResponse:
    from apps.api_server.routers.license import _store_nonce

    nonce = secrets.token_bytes(32)
    redis = getattr(request.app.state, "redis", None)
    await _store_nonce(
        redis, _pop_nonce_key(ctx["org_id"], body.deployment_id, body.node_thumbprint), nonce
    )
    return DeploymentNodeChallengeResponse(nonce=base64.b64encode(nonce).decode())


async def _verify_deployment_pop(
    body: DeploymentNodeHeartbeatRequest, ctx: AuthContext, request: Request
) -> None:
    """Verify the node proved possession of its deployment key. Raises 401 on any failure. Runs
    when PoP is required OR when the client supplied PoP fields (honest clients get verified either
    way). Checks: single-use nonce, signature over the nonce, and thumbprint(pubkey)==node_thumbprint."""
    from apps.api_server.routers.license import _consume_nonce
    from apps.runtime.device_keypair import thumbprint_for_public_pem, verify_signature

    supplied = bool(body.nonce or body.public_key_pem or body.signature)
    if not _deployment_pop_required() and not supplied:
        return  # PoP not required and not offered → API-key-only (back-compat)
    if not (body.nonce and body.public_key_pem and body.signature):
        raise HTTPException(status_code=401, detail={"error": "pop_required",
            "message": "deployment node PoP requires nonce + public_key_pem + signature"})

    # the presented key must be the claimed node thumbprint
    if (thumbprint_for_public_pem(body.public_key_pem) or "") != body.node_thumbprint:
        raise HTTPException(status_code=401, detail={"error": "pop_thumbprint_mismatch",
            "message": "public_key_pem does not match node_thumbprint"})

    redis = getattr(request.app.state, "redis", None)
    stored = await _consume_nonce(
        redis, _pop_nonce_key(ctx["org_id"], body.deployment_id, body.node_thumbprint)
    )
    if stored is None:
        raise HTTPException(status_code=401, detail={"error": "pop_nonce_invalid",
            "message": "no valid challenge nonce — request /v1/deployment/node/challenge first"})
    try:
        sig = base64.b64decode(body.signature)
        presented_nonce = base64.b64decode(body.nonce)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail={"error": "pop_malformed"}) from exc
    if presented_nonce != stored or not verify_signature(body.public_key_pem, stored, sig):
        raise HTTPException(status_code=401, detail={"error": "pop_signature_invalid",
            "message": "deployment-key proof-of-possession failed"})


@router.post(
    "/v1/deployment/node/heartbeat",
    response_model=DeploymentNodeHeartbeatResponse,
    summary="L3 connected-pool: admit/renew an engine node's Compute-Unit lease against the pool",
)
async def deployment_node_heartbeat(
    body: DeploymentNodeHeartbeatRequest,
    ctx: Annotated[AuthContext, Depends(get_current_org)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> DeploymentNodeHeartbeatResponse:
    from apps.api_server.services.deployment_service import (
        DeploymentActivationError,
        admit_deployment_node,
    )

    await _verify_deployment_pop(body, ctx, request)

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
