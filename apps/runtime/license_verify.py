"""Strict JOSE license verifier (approved plan §3, RFC 8725).

The critique's #1 finding: the legacy ``license._parse_token`` accepts HS256 dev-stub tokens
signed with a source-visible secret unless a strict flag is set — anyone can forge a license
with a few lines of PyJWT. This module is the hardened replacement profile for the NEW
server/enterprise (``license_scope=deployment``) and next-gen tokens: RS256-only, exact-match
issuer/audience/type/product/edition, ``kid`` resolved against an embedded trust bundle, and
no token-supplied key URLs.

Rollout is NON-BREAKING: this profile is identified by the JOSE header ``typ=algenta-license+jwt``.
Tokens carrying that type are verified strictly; every currently-issued license (no such ``typ``)
keeps flowing through the legacy path unchanged, so live installs never break. The eventual
artifact split (production wheels with NO HS256 branch) makes strict the only path — tracked
separately.

Pure verification, no network. Keys come from an embedded/offline trust bundle (env or file),
NEVER from ``jku``/``x5u`` in the token.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

import jwt

# The JOSE header ``typ`` that marks a strict-profile license. Its presence routes verification
# here; its absence keeps the legacy path (back-compat).
LICENSE_TYP = "algenta-license+jwt"

# Accepted issuers (the control-plane mint + the platform cf_worker). Env-extensible for ops.
_DEFAULT_ISSUERS = ("https://license.algenta.ai", "algenta-control-plane")
# Accepted audience — the on-device runtime.
DEFAULT_AUDIENCE = "algenta-runtime"

# Hard bounds — a license is a small signed blob; anything larger is malformed/hostile.
_MAX_TOKEN_BYTES = 16 * 1024
_MAX_STR_CLAIM_LEN = 1024

# Required claims for a strict-profile license (per §3). Presence is enforced; exp is required
# but expiry ITSELF is enforced by the runtime state machine (grace → Community), so we require
# the claim without letting the JOSE layer reject on it.
_REQUIRED_CLAIMS = (
    "iss",
    "aud",
    "sub",
    "jti",
    "iat",
    "nbf",
    "exp",
    "schema_version",
    "product",
    "edition",
    "license_scope",
    "deployment_class",
)


class LicenseVerificationError(Exception):
    """A token failed strict verification. ``reason`` is a stable machine code for tests/logs
    (never contains secrets or token contents)."""

    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


@dataclass(frozen=True)
class VerifiedLicense:
    payload: dict[str, object]
    kid: str


def _accepted_issuers() -> tuple[str, ...]:
    extra = (os.environ.get("ALGENTA_LICENSE_ACCEPTED_ISSUERS") or "").strip()
    if not extra:
        return _DEFAULT_ISSUERS
    parsed = tuple(p.strip() for p in extra.split(",") if p.strip())
    return parsed or _DEFAULT_ISSUERS


def load_trust_bundle() -> dict[str, str]:
    """Resolve the embedded/offline trust bundle: ``{kid: public_key_pem}``.

    Sources, merged (later wins on kid collision):
      1. Single-key legacy envs (``ALGENTA_LOCAL_LICENSE_PUBLIC_KEY`` / ``_FILE`` / the
         ``ALGENTA_LICENSE_*`` variants) → assigned the default kid.
      2. ``ALGENTA_LICENSE_TRUST_BUNDLE`` (JSON ``{kid: pem}``) or ``_FILE`` → the multi-key
         set enabling rotation (ship current + next before flipping the signer).

    NEVER reads a key from a URL in the token (no ``jku``/``x5u``)."""
    bundle: dict[str, str] = {}

    # 1. legacy single-key envs → default kid
    from apps.runtime.license import _offline_license_public_keys

    for pem, _source in _offline_license_public_keys():
        bundle.setdefault("algenta-license-default", pem)

    # 2. explicit multi-key manifest
    raw = (os.environ.get("ALGENTA_LICENSE_TRUST_BUNDLE") or "").strip()
    if not raw:
        path = (os.environ.get("ALGENTA_LICENSE_TRUST_BUNDLE_FILE") or "").strip()
        if path:
            try:
                raw = Path(path).expanduser().read_text().strip()
            except OSError:
                raw = ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for kid, pem in parsed.items():
                    if isinstance(kid, str) and isinstance(pem, str) and kid and pem.strip():
                        bundle[kid] = pem.strip()
        except (json.JSONDecodeError, ValueError):
            pass
    return bundle


def is_strict_profile_token(token: str) -> bool:
    """True iff the token's JOSE header declares the strict ``typ`` (so verification routes here)."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return False
    return header.get("typ") == LICENSE_TYP


def _raw_jose_header(token: str) -> dict | None:
    """Best-effort decode of the UNPROTECTED JOSE header without PyJWT's crit pre-rejection.

    Newer PyJWT versions raise ``InvalidTokenError`` from ``get_unverified_header`` itself when
    the header carries a ``crit`` extension, before this profile can name the rejection. This
    decoder reads the header segment directly so the crit gate can run first. Returns None for
    anything unparseable — ``get_unverified_header`` then produces the normal "bad_header" path.
    No trust decision is ever based on this decode alone: the signature is still verified by
    PyJWT against the trust-bundle key before any claim is honored."""
    try:
        segment = token.split(".", 1)[0]
        padded = segment + "=" * (-len(segment) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        header = json.loads(decoded)
    except Exception:  # noqa: BLE001 — any decode failure → let PyJWT name the header error
        return None
    return header if isinstance(header, dict) else None


def _validate_claim_sizes(payload: dict[str, object]) -> None:
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > _MAX_STR_CLAIM_LEN:
            raise LicenseVerificationError("claim_too_large", f"claim {key} exceeds size bound")


def verify_license_token(
    token: str,
    *,
    expected_product: str,
    expected_edition: str | None = None,
    expected_audience: str = DEFAULT_AUDIENCE,
    trust_bundle: dict[str, str] | None = None,
    revoked_jtis: frozenset[str] | set[str] | None = None,
) -> VerifiedLicense:
    """Strictly verify a license token, or raise :class:`LicenseVerificationError`.

    Enforces (RFC 8725): RS256 only (kills ``alg=none`` and RS/HS confusion), ``typ`` match,
    ``kid`` present + resolved ONLY against the trust bundle, exact ``iss``/``aud`` match, no
    unknown critical headers, required claims present, and exact ``product`` (and ``edition``)
    match so one product's license can never activate another. Signature + iss + aud are
    cryptographically verified; expiry is left to the runtime state machine (grace → Community).
    """
    if not token or len(token.encode("utf-8", "ignore")) > _MAX_TOKEN_BYTES:
        raise LicenseVerificationError("token_size", "token missing or too large")

    # crit gate FIRST, on the raw header: newer PyJWT (>= 2.10) raises InvalidTokenError from
    # get_unverified_header ITSELF on any crit extension ("Unsupported critical extension"),
    # which would mask this profile's named crit rejection as the generic "bad_header". The
    # verdict is identical either way (the token is rejected); checking the raw header first
    # keeps the reason code stable across PyJWT versions.
    raw_header = _raw_jose_header(token)
    if raw_header is not None and raw_header.get("crit"):
        raise LicenseVerificationError("crit_unsupported", "unknown critical header params")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise LicenseVerificationError("bad_header", "unparseable JOSE header") from exc

    # alg allowlist — RS256 ONLY. Rejects alg=none and any HS* (algorithm-confusion).
    if header.get("alg") != "RS256":
        raise LicenseVerificationError("alg_not_allowed", f"alg={header.get('alg')!r} rejected")
    # typ must be the strict profile.
    if header.get("typ") != LICENSE_TYP:
        raise LicenseVerificationError("wrong_typ", "not a strict-profile license")
    # No unknown critical headers; never honor token-supplied key locations.
    if header.get("crit"):
        raise LicenseVerificationError("crit_unsupported", "unknown critical header params")
    if header.get("jku") or header.get("x5u"):
        raise LicenseVerificationError("key_url_forbidden", "token-supplied key URL rejected")

    kid = header.get("kid")
    if not kid or not isinstance(kid, str):
        raise LicenseVerificationError("kid_missing", "kid header required")
    bundle = trust_bundle if trust_bundle is not None else load_trust_bundle()
    key_pem = bundle.get(kid)
    if not key_pem:
        raise LicenseVerificationError("kid_unknown", "kid not in trust bundle")

    try:
        payload = jwt.decode(
            token,
            key_pem,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=list(_accepted_issuers()),
            options={
                "require": list(_REQUIRED_CLAIMS),
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                # Runtime owns expiry (grace → Community); require the claim, don't reject on it.
                "verify_exp": False,
                "verify_nbf": True,
                "verify_iat": True,
            },
        )
    except jwt.MissingRequiredClaimError as exc:
        raise LicenseVerificationError("missing_claim", str(exc)) from exc
    except jwt.InvalidAudienceError as exc:
        raise LicenseVerificationError("bad_audience", "audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise LicenseVerificationError("bad_issuer", "issuer not accepted") from exc
    except jwt.InvalidSignatureError as exc:
        raise LicenseVerificationError("bad_signature", "signature verification failed") from exc
    except jwt.InvalidTokenError as exc:
        raise LicenseVerificationError("invalid_token", str(exc)) from exc

    if not isinstance(payload, dict):
        raise LicenseVerificationError("bad_payload", "payload is not an object")
    _validate_claim_sizes(payload)

    if payload.get("sub") != "device-license":
        raise LicenseVerificationError("wrong_sub", "unexpected subject")

    # Exact product/edition match — no cross-product replay (a Telys license can't run Codna).
    if str(payload.get("product") or "") != expected_product:
        raise LicenseVerificationError("wrong_product", "product mismatch")
    if expected_edition is not None and str(payload.get("edition") or "") != expected_edition:
        raise LicenseVerificationError("wrong_edition", "edition mismatch")

    # Revocation: a positively-listed jti is rejected. Fail-OPEN by default (empty/None set =
    # never revoked) — mirrors the existing CRL philosophy so an unreachable revocation source
    # never falsely breaks a paying customer. A caller passes the verified denylist explicitly.
    revoked = revoked_jtis if revoked_jtis is not None else load_revoked_jtis()
    jti = str(payload.get("jti") or "")
    if jti and jti in revoked:
        raise LicenseVerificationError("revoked", "license jti is revoked")

    return VerifiedLicense(payload=payload, kid=kid)


def load_revoked_jtis() -> frozenset[str]:
    """The set of revoked license jtis the strict verifier denies. Default EMPTY (fail-open):
    revocation is a positive-list action, and an unavailable source must never break a valid
    license. The runtime wires this to the verified CRL (see ``apps.runtime.license`` CRL fetch);
    an operator can also pin a static denylist via ``ALGENTA_REVOKED_JTIS`` (comma-separated)."""
    raw = (os.environ.get("ALGENTA_REVOKED_JTIS") or "").strip()
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def try_verify_license_token(
    token: str,
    *,
    expected_product: str,
    expected_edition: str | None = None,
    expected_audience: str = DEFAULT_AUDIENCE,
    trust_bundle: dict[str, str] | None = None,
    revoked_jtis: frozenset[str] | set[str] | None = None,
) -> tuple[VerifiedLicense | None, str]:
    """Non-raising wrapper: returns ``(VerifiedLicense, "")`` on success or ``(None, reason)``."""
    try:
        return (
            verify_license_token(
                token,
                expected_product=expected_product,
                expected_edition=expected_edition,
                expected_audience=expected_audience,
                trust_bundle=trust_bundle,
                revoked_jtis=revoked_jtis,
            ),
            "",
        )
    except LicenseVerificationError as exc:
        return None, exc.reason
