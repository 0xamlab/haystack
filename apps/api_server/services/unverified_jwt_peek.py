"""Read a JWT's payload claims WITHOUT verifying it — for routing and key selection only.

Every bearer verifier in this package has to look at a claim or two *before* it can verify the
token: the ``iss`` host decides which verifier is even relevant (Entra vs generic OIDC), and
Entra's ``tid`` decides which tenant's JWKS the signature must be checked against (and whether
that tenant is allowed here at all — no key fetch for strangers). Those pre-reads used to be
``jwt.decode(token, options={"verify_signature": False})``, which is the same call shape as a
real verification with the safety switched off; a reader (or a scanner) cannot tell at the call
site whether the result is later trusted. This module is the explicit alternative: it only ever
splits the compact serialisation, base64url-decodes the payload segment and parses the JSON. It
has no notion of keys, algorithms, audiences or expiry, so nothing that comes out of it can be
mistaken for a verified claim.

Contract for callers: values returned here carry ZERO trust. They may select a verifier, a
tenant or a signing key, or produce an early precise error — and then the token MUST still go
through the pinned ``jwt.decode(token, key, algorithms=[...], audience=..., issuer=...)`` on
every accepting path. Nothing read here is ever returned to a caller as identity.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

__all__ = ["UnverifiedJwtError", "peek_unverified_claims"]


class UnverifiedJwtError(ValueError):
    """The compact serialisation is not a JWT whose payload segment we can read at all."""


def _b64url_decode(segment: str) -> bytes:
    # RFC 7515 §2: base64url without padding. Re-add the padding the encoder stripped; reject
    # anything outside the base64url alphabet (``validate=True`` — no silent skipping).
    stripped = segment.strip()
    if not stripped:
        raise UnverifiedJwtError("empty JWT segment")
    padded = stripped + "=" * (-len(stripped) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise UnverifiedJwtError("JWT segment is not base64url") from exc


def peek_unverified_claims(token: str) -> dict[str, Any]:
    """Return the payload claims of ``token`` as a dict — UNVERIFIED, for routing/key selection only.

    Accepts exactly the three-segment compact JWS serialisation (``header.payload.signature``).
    Raises :class:`UnverifiedJwtError` (a ``ValueError``) when the token has the wrong number of
    segments, the payload is not base64url, is not UTF-8 JSON, or is not a JSON object. The
    signature segment is deliberately never looked at: this function cannot check it, and it
    must not appear to.
    """
    parts = (token or "").strip().split(".")
    if len(parts) != 3:
        raise UnverifiedJwtError("not a compact JWS (expected header.payload.signature)")
    raw = _b64url_decode(parts[1])
    try:
        claims = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnverifiedJwtError("JWT payload is not a UTF-8 JSON document") from exc
    if not isinstance(claims, dict):
        raise UnverifiedJwtError("JWT payload is not a JSON object")
    return claims
