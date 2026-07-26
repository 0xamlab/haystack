"""Algenta Relay — the customer-run HTTP lease authority for air-gapped / floating pools.

Runs INSIDE the customer network (no vendor connectivity). On startup it verifies a vendor-minted
pool root under the vendor trust bundle to learn its Compute-Unit ceiling, then leases units to
engine nodes over HTTP, signing each lease with its own relay key (the delegation chain in
``relay_delegation``). The in-memory :class:`LeaseLedger` enforces the pool ceiling, idempotency,
borrow-with-expiry, and never-evict.

Built as a factory (``create_relay_app``) with all key material injected, so it is fully testable
with a TestClient and no env/DB. Endpoints:
  POST /v1/relay/lease      — acquire (or idempotently refresh) a node's unit lease → signed lease
  POST /v1/relay/heartbeat  — renew an existing lease's TTL
  POST /v1/relay/release    — graceful give-back (frees units immediately)
  GET  /v1/relay/status     — pool utilization
"""
from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from apps.runtime import relay_delegation as rd
from apps.runtime.relay_lease import LeaseError, LeaseLedger

_DEFAULT_LEASE_TTL = 300
_DEFAULT_BORROW = 300


class LeaseRequest(BaseModel):
    node_public_key_thumbprint: str = Field(..., min_length=1, max_length=256)
    deployment_id: str = Field(..., min_length=1, max_length=128)
    product: str = Field(..., min_length=1, max_length=32)
    units: int = Field(..., ge=1, le=1_000_000)


class HeartbeatRequest(BaseModel):
    node_public_key_thumbprint: str = Field(..., min_length=1, max_length=256)


class ReleaseRequest(BaseModel):
    node_public_key_thumbprint: str = Field(..., min_length=1, max_length=256)


def create_relay_app(
    *,
    pool_root_token: str,
    relay_private_key_pem: str,
    relay_public_key_pem: str,
    vendor_trust_bundle: dict[str, str],
    relay_id: str = "relay-1",
    lease_ttl_seconds: int = _DEFAULT_LEASE_TTL,
    borrow_seconds: int = _DEFAULT_BORROW,
    ledger_factory=None,
) -> FastAPI:
    """Build a Relay app for a specific vendor-minted pool root + this relay's keypair.

    Raises at construction if the pool root does not verify under the vendor trust bundle or does
    not bind THIS relay's key (fail closed — a misprovisioned relay never serves leases).

    ``ledger_factory(max_units, node_ceiling)`` builds the lease ledger; the default is the
    in-memory :class:`LeaseLedger` (single relay). For HA, pass a factory returning a shared
    ledger (e.g. ``apps.runtime.relay_lease_store.SqliteLeaseLedger`` on shared storage) so
    replicas can't double-allocate the pool."""
    pool = rd.verify_pool_root(pool_root_token, trust_bundle=vendor_trust_bundle)
    if pool.relay_thumbprint != rd.key_thumbprint(relay_public_key_pem):
        raise ValueError("pool root does not bind this relay's public key")

    node_ceiling = int(pool.payload.get("max_node_count_safety_ceiling", 0) or 0)
    if ledger_factory is None:
        ledger = LeaseLedger(max_units=pool.max_concurrent_units, node_ceiling=node_ceiling)
    else:
        ledger = ledger_factory(pool.max_concurrent_units, node_ceiling)
    # The relay may not grant a longer TTL than the pool root permits.
    max_ttl = int(pool.payload.get("maximum_delegated_lease_ttl", lease_ttl_seconds) or lease_ttl_seconds)
    ttl = min(lease_ttl_seconds, max_ttl)
    pool_license_id = str(pool.payload.get("jti") or "pool")
    relay_epoch = int(pool.payload.get("relay_epoch", 1) or 1)

    app = FastAPI(title="Algenta Relay", version="1")

    def _issue_lease(node_thumb: str, deployment_id: str, product: str, units: int) -> dict:
        now = time.time()
        # Validate product BEFORE touching the ledger — otherwise a bad-product request would
        # acquire (clobbering the node's existing valid lease) and then release it, destroying a
        # good lease. Check first so a rejected request never mutates ledger state.
        if pool.permitted_products and product not in pool.permitted_products:
            raise HTTPException(status_code=403, detail={"error": "product_not_in_pool", "product": product})
        try:
            lease = ledger.acquire(node_thumb, units, now, ttl=ttl, borrow=borrow_seconds)
        except LeaseError as exc:
            raise HTTPException(
                status_code=409,
                detail={"error": "pool_exhausted", "message": str(exc),
                        "pool_units": ledger.max_units, "available_units": ledger.available_units(now)},
            ) from exc
        token = rd.sign_node_lease(
            relay_private_key_pem, pool_license_id=pool_license_id, relay_id=relay_id,
            node_public_key_thumbprint=node_thumb, deployment_id=deployment_id, product=product,
            granted_units=int(lease.granted_units), ttl_seconds=ttl,
            borrowed_until_seconds=borrow_seconds, relay_epoch=relay_epoch, now=int(now),
        )
        return {
            "lease_token": token,
            "granted_units": int(lease.granted_units),
            "expires_at": int(lease.expires_at),
            "pool_units": ledger.max_units,
            "available_units": ledger.available_units(now),
        }

    @app.post("/v1/relay/lease")
    def acquire_lease(body: LeaseRequest) -> dict:
        return _issue_lease(body.node_public_key_thumbprint, body.deployment_id, body.product, body.units)

    @app.post("/v1/relay/heartbeat")
    def heartbeat(body: HeartbeatRequest) -> dict:
        now = time.time()
        try:
            lease = ledger.renew(body.node_public_key_thumbprint, now, ttl=ttl, borrow=borrow_seconds)
        except LeaseError as exc:
            # No active lease — the node must re-acquire (its slot was reclaimed).
            raise HTTPException(status_code=409, detail={"error": "no_active_lease", "message": str(exc)}) from exc
        token = rd.sign_node_lease(
            relay_private_key_pem, pool_license_id=pool_license_id, relay_id=relay_id,
            node_public_key_thumbprint=body.node_public_key_thumbprint, deployment_id="",
            product="", granted_units=int(lease.granted_units), ttl_seconds=ttl,
            borrowed_until_seconds=borrow_seconds, relay_epoch=relay_epoch, now=int(now),
        )
        return {"lease_token": token, "granted_units": int(lease.granted_units),
                "expires_at": int(lease.expires_at)}

    @app.post("/v1/relay/release")
    def release(body: ReleaseRequest) -> dict:
        ledger.release(body.node_public_key_thumbprint, time.time())
        return {"released": True}

    @app.get("/v1/relay/status")
    def status() -> dict:
        now = time.time()
        return {
            "pool_units": ledger.max_units,
            "used_units": ledger.used_units(now),
            "available_units": ledger.available_units(now),
            "active_nodes": len(ledger.active_leases(now)),
            "permitted_products": list(pool.permitted_products),
        }

    return app
