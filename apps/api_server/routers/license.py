"""/license + /.well-known — control-plane license surfaces.

P3b-B1: GET /.well-known/jwks.json — the license signer's PUBLIC key(s), so a runtime can
verify device licenses (and, later, the signed CRL) by ``kid`` instead of a hardcoded env
key. Unauthenticated + self-authenticating (public key material only).

Future (same router): POST /v1/license/challenge + /v1/license/renew (renewal
proof-of-possession), GET /v1/license/revocations (signed CRL).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from apps.api_server.services.license_jwk import get_active_license_jwks

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["license"])


@router.get(
    "/.well-known/jwks.json",
    include_in_schema=False,
    summary="License signer public keys (JWKS)",
)
async def jwks() -> dict[str, list[dict[str, str]]]:
    """Public JWKS for the active license signer.

    Empty ``keys`` under the dev_hmac (HS256) backend — there is no asymmetric public key;
    consumers fall back to the shared-secret / offline-key verification path.
    """
    return get_active_license_jwks()
