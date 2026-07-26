"""Algenta Relay delegation chain — root → pool-root → node-lease signing/verification.

The cryptographic backbone of the customer-run Relay (air-gapped / floating pools):

    Algenta root key (vendor, offline)
      └── signs a POOL ROOT (typ=algenta-relay-root+jwt) that grants N Compute Units and BINDS
          the customer's relay public-key thumbprint
            └── the Relay's own key signs short-TTL NODE LEASES (typ=algenta-node-lease+jwt)

A node trusts a lease iff: (1) the pool root verifies under the vendor trust bundle (RS256, kid),
and (2) the lease is signed by the relay key whose thumbprint the pool root binds. So stealing
the pool-root FILE without the relay PRIVATE key is useless — you can't sign leases. The relay
never holds the vendor root key; the vendor never holds the relay key.

Pure crypto + validation (RS256 via PyJWT), deterministic ``now`` in verification. No network.
"""
from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass

import jwt

POOL_ROOT_TYP = "algenta-relay-root+jwt"
NODE_LEASE_TYP = "algenta-node-lease+jwt"
_POOL_ISSUER = "https://license.algenta.ai"

_MAX_TOKEN_BYTES = 16 * 1024


class RelayVerificationError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


def key_thumbprint(public_key_pem: str) -> str:
    """Stable thumbprint of a PEM public key: ``rsa-sha256:<b64url(sha256(pem))>`` (no padding).
    Used to BIND the pool root to a specific relay key."""
    digest = hashlib.sha256(public_key_pem.strip().encode("utf-8")).digest()
    return "rsa-sha256:" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class VerifiedPoolRoot:
    payload: dict[str, object]
    relay_thumbprint: str
    max_concurrent_units: int
    permitted_products: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedNodeLease:
    payload: dict[str, object]
    granted_units: int
    node_thumbprint: str
    deployment_id: str


# ── pool root (signed by the vendor root key) ────────────────────────────────


def sign_pool_root(
    root_private_key_pem: str,
    *,
    customer_id: str,
    relay_public_key_pem: str,
    permitted_products: list[str],
    max_concurrent_units: int,
    kid: str,
    ttl_days: int = 365,
    max_node_ceiling: int = 0,
    max_lease_ttl_seconds: int = 3600,
    relay_epoch: int = 1,
    now: int | None = None,
) -> str:
    """Vendor operation: mint a pool root binding the customer's relay key to N Compute Units."""
    if max_concurrent_units <= 0:
        raise ValueError("max_concurrent_units must be > 0")
    if not relay_public_key_pem.strip():
        raise ValueError("relay_public_key_pem is required (the pool root binds the relay key)")
    issued = int(now if now is not None else time.time())
    exp = issued + max(1, int(ttl_days)) * 86400
    payload = {
        "iss": _POOL_ISSUER,
        "typ_claim": POOL_ROOT_TYP,
        "customer_id": customer_id,
        "relay_public_key_thumbprint": key_thumbprint(relay_public_key_pem),
        "permitted_products": list(permitted_products),
        "max_concurrent_units": int(max_concurrent_units),
        "max_node_count_safety_ceiling": int(max_node_ceiling),
        "maximum_delegated_lease_ttl": int(max_lease_ttl_seconds),
        "relay_epoch": int(relay_epoch),
        "iat": issued,
        "nbf": issued,
        "exp": exp,
        "jti": f"poolroot:{customer_id}:{relay_epoch}",
    }
    return jwt.encode(payload, root_private_key_pem, algorithm="RS256",
                      headers={"typ": POOL_ROOT_TYP, "kid": kid})


def verify_pool_root(
    token: str, *, trust_bundle: dict[str, str], now: int | None = None
) -> VerifiedPoolRoot:
    """Verify a pool root under the VENDOR trust bundle (RS256, kid allowlist, typ, exp/nbf)."""
    if not token or len(token.encode("utf-8", "ignore")) > _MAX_TOKEN_BYTES:
        raise RelayVerificationError("token_size")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise RelayVerificationError("bad_header") from exc
    if header.get("alg") != "RS256":
        raise RelayVerificationError("alg_not_allowed")
    if header.get("typ") != POOL_ROOT_TYP:
        raise RelayVerificationError("wrong_typ")
    kid = header.get("kid")
    key_pem = trust_bundle.get(kid) if isinstance(kid, str) else None
    if not key_pem:
        raise RelayVerificationError("kid_unknown")
    try:
        payload = jwt.decode(
            token, key_pem, algorithms=["RS256"], issuer=_POOL_ISSUER,
            options={"require": ["iss", "exp", "nbf", "iat", "relay_public_key_thumbprint",
                                 "max_concurrent_units", "customer_id"],
                     "verify_exp": True, "verify_nbf": True, "verify_iss": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise RelayVerificationError("expired") from exc
    except jwt.InvalidTokenError as exc:
        raise RelayVerificationError("invalid_token", str(exc)) from exc
    return VerifiedPoolRoot(
        payload=payload,
        relay_thumbprint=str(payload.get("relay_public_key_thumbprint") or ""),
        max_concurrent_units=int(payload.get("max_concurrent_units") or 0),
        permitted_products=tuple(payload.get("permitted_products") or []),
    )


# ── node lease (signed by the RELAY key, chained to the pool root) ────────────


def sign_node_lease(
    relay_private_key_pem: str,
    *,
    pool_license_id: str,
    relay_id: str,
    node_public_key_thumbprint: str,
    deployment_id: str,
    product: str,
    granted_units: int,
    ttl_seconds: int,
    borrowed_until_seconds: int | None = None,
    relay_epoch: int = 1,
    now: int | None = None,
) -> str:
    """Relay operation: sign a short-TTL node lease for ``granted_units``."""
    if granted_units <= 0:
        raise ValueError("granted_units must be > 0")
    issued = int(now if now is not None else time.time())
    exp = issued + max(1, int(ttl_seconds))
    borrowed = issued + int(borrowed_until_seconds if borrowed_until_seconds is not None else ttl_seconds)
    payload = {
        "pool_license_id": pool_license_id,
        "relay_id": relay_id,
        "node_public_key_thumbprint": node_public_key_thumbprint,
        "deployment_id": deployment_id,
        "product": product,
        "granted_units": int(granted_units),
        "lease_id": f"lease:{relay_id}:{node_public_key_thumbprint}:{issued}",
        "lease_epoch": int(relay_epoch),
        "iat": issued,
        "nbf": issued,
        "exp": exp,
        "borrowed_until": borrowed,
    }
    return jwt.encode(payload, relay_private_key_pem, algorithm="RS256",
                      headers={"typ": NODE_LEASE_TYP})


def verify_node_lease(
    token: str,
    *,
    pool_root: VerifiedPoolRoot,
    relay_public_key_pem: str,
    expected_product: str | None = None,
    now: int | None = None,
) -> VerifiedNodeLease:
    """Verify a node lease: it must be signed by the relay key the POOL ROOT binds (thumbprint
    match) and be within its TTL. This is the chain check — a lease is only as trusted as the
    pool root that authorized its signer."""
    if key_thumbprint(relay_public_key_pem) != pool_root.relay_thumbprint:
        raise RelayVerificationError("relay_key_mismatch",
                                     "relay key does not match the pool root's bound thumbprint")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise RelayVerificationError("bad_header") from exc
    if header.get("alg") != "RS256":
        raise RelayVerificationError("alg_not_allowed")
    if header.get("typ") != NODE_LEASE_TYP:
        raise RelayVerificationError("wrong_typ")
    try:
        payload = jwt.decode(
            token, relay_public_key_pem, algorithms=["RS256"],
            options={"require": ["exp", "nbf", "iat", "granted_units",
                                 "node_public_key_thumbprint", "deployment_id"],
                     "verify_exp": True, "verify_nbf": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise RelayVerificationError("expired") from exc
    except jwt.InvalidTokenError as exc:
        raise RelayVerificationError("invalid_token", str(exc)) from exc
    if expected_product is not None and str(payload.get("product") or "") != expected_product:
        raise RelayVerificationError("wrong_product")
    if expected_product is not None and pool_root.permitted_products and \
            expected_product not in pool_root.permitted_products:
        raise RelayVerificationError("product_not_in_pool")
    return VerifiedNodeLease(
        payload=payload,
        granted_units=int(payload.get("granted_units") or 0),
        node_thumbprint=str(payload.get("node_public_key_thumbprint") or ""),
        deployment_id=str(payload.get("deployment_id") or ""),
    )
