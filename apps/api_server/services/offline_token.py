"""Offline auth: resolve an AuthContext from a locally-verified signed license token.

ZERO Postgres / Redis / network on the hot path. The control plane (Fly) issues a signed,
time-bound license JWT out-of-band; the engine — on any Fly machine OR a user device gone dark —
verifies it LOCALLY (signature + expiry via the runtime license verifier) and builds the
AuthContext straight from the signed claims (org_id, plan, device_limit). No per-request DB call.

Falls through (returns None) for non-JWT credentials (legacy/hosted API keys), so the DB-backed
api-key path still works for clients that present one.
"""

from __future__ import annotations

import uuid

import structlog

from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)


def _looks_like_jwt(token: str) -> bool:
    # A compact JWS is header.payload.signature; the b64url header of {"alg":... starts "eyJ".
    return token.count(".") == 2 and token.startswith("eyJ")


def _stable_uuid(seed: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_OID, seed or "codna-offline-license")


def verify_offline_token(raw: str) -> AuthContext | None:
    """Verify a signed license token offline and map its claims to an AuthContext.

    Returns None (so the caller falls back to the DB-backed api-key path) when the credential is
    not a JWT, the signature does not verify, the org is absent, or the token is expired.
    Never touches Postgres, Redis, or the network.
    """
    if not raw or not _looks_like_jwt(raw):
        return None
    try:
        # Lazy import: the runtime verifier owns the public-key / control-plane-secret material and
        # the trusted (anti-rollback) clock. RS256 (device holds public key) or HS256 (dev/self-host).
        from apps.runtime.license import _parse_token

        lic = _parse_token(raw)
    except Exception as exc:  # noqa: BLE001 — a malformed token must not 500; fall through to api-key
        logger.warning("offline_token_parse_failed", error=str(exc))
        return None

    if lic is None or not lic.org_id:
        return None
    # Go-dark: a device past its token's expiry keeps working through the grace window
    # (grace_days). Only HARD expiry — past expires_at + grace_days — actually denies. This is the
    # whole point of an offline license: the user can be disconnected for the grace window and the
    # fix path never blocks. (is_expired() is true the instant past expiry, which would wrongly deny
    # during grace — the bug this guards against.)
    if lic.is_hard_expired():
        logger.info(
            "offline_token_hard_expired",
            org_id=lic.org_id,
            expires_at=lic.expires_at,
            grace_days=lic.grace_days,
        )
        return None
    if lic.is_in_grace():
        logger.info(
            "offline_token_in_grace",
            org_id=lic.org_id,
            expires_at=lic.expires_at,
            grace_days=lic.grace_days,
        )

    try:
        org_uuid = uuid.UUID(lic.org_id)
    except (ValueError, AttributeError, TypeError):
        logger.warning("offline_token_bad_org_id", org_id=lic.org_id)
        return None

    return AuthContext(
        org_id=org_uuid,
        key_id=_stable_uuid(lic.activation_id or lic.license_id or lic.org_id),
        key_prefix=lic.api_key_prefix or "license",
        user_id=None,
        plan=lic.plan,
        device_limit=lic.device_limit,
        device_limit_configured=lic.device_limit > 0,
        role="owner",
        email="offline_license",
        is_platform=False,
        is_service=False,
        workspace_id=None,
        org_status="active",
        user_status="active",
        email_verified=True,
    )
