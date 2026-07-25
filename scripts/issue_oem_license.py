#!/usr/bin/env python3
"""Issue an INDEFINITE (100-year) OEM / trusted-partner Algenta platform license — for ANY sub-brand.

This is the deliberate exception to the self-service path. Public `<brand> login` licenses are minted by
the shared control-plane signer (the `license-signer` Cloudflare Worker, license.algenta.ai) which HARD-CAPS
every token at 90 days. A trusted partner / sub-brand (codna embedding telys, telys embedding the engine,
cohenta / decimas / escrypto / mission, …) needs a long-lived, offline, non-phone-home license instead — so
we sign it DIRECTLY with the shared platform private key (the SAME key the Worker holds → every brand's
offline verifier accepts it), off the 90-day path.

    python scripts/issue_oem_license.py --product codna --customer codna --org-id codna \
        --tier team --exp-years 100 --key dist-keys/platform_license_priv.pem \
        --out dist/oem/codna-license.jwt

Brand-parameterized: `--product` sets the `products.<product>` claim (generalizing the telys-only
memory-engine/scripts/issue_oem_license.py). iss / aud / kid are the SHARED platform values, identical for
every brand — product scoping is via the `products.<product>` claim, NOT a per-brand audience. That single
shared trust anchor is what lets ONE verifier (telys/verify.py + apps/runtime/license.py) accept every
brand's license — see [[project_licensing_control_plane]] / telys/_keys/README.md.

Security:
  * Reads the platform private key from --key (default dist-keys/platform_license_priv.pem — GITIGNORED,
    never commit). Same bootstrap keypair as the Worker + the runtimes' embedded public key (key continuity).
  * The OUTPUT license.jwt is a bearer credential — do NOT commit it; deliver over a secure channel.
  * SELF-VERIFIES the minted token with the strict platform verifier below (the same contract telys.verify
    enforces) before writing, so a malformed / would-be-rejected token never ships.
  * Emits a machine-readable AUDIT manifest alongside the token for the license register.

"Indefinite" = a far-future numeric `exp` (the verifier REQUIRES a finite exp) + a large offline_grace: the
license never practically expires and never calls home. Infra-wide by default (no device thumbprint).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

import jwt

# ── the SHARED platform trust anchor (identical for EVERY brand) ─────────────────────────────────────────
# Keep in lockstep with:
#   - apps/api_server/services/device_service.py  (_PLATFORM_LICENSE_ISSUER / _PLATFORM_LICENSE_AUDIENCE)
#   - apps/api_server/services/product_registry.py (PLATFORM_LICENSE_ISSUER/AUDIENCE/KID)
#   - infra/cloudflare/license-signer/worker.js
#   - telys-sdk telys/verify.py (DEFAULT_LICENSE_ISSUER / DEFAULT_LICENSE_AUDIENCES)
PLATFORM_ISSUER = "https://license.algenta.ai"
PLATFORM_AUDIENCE = "algenta-runtime"
PLATFORM_KID = "algenta-license-2026"
# The verifier accepts either the platform-runtime audience or a legacy telys-runtime audience.
ACCEPTED_AUDIENCES = ("algenta-runtime", "telys-runtime")
SUPPORTED_LICENSE_VER = 2
_DEFAULT_KEY = os.environ.get("ALGENTA_PLATFORM_LICENSE_PRIVATE_KEY_FILE", "dist-keys/platform_license_priv.pem")

# Per-product default feature sets (mirror product_registry.*_FEATURES_FULL). An unknown/new sub-brand
# defaults to ["local_runtime"] so the token is still valid (non-empty features); override with --features.
PRODUCT_DEFAULT_FEATURES: dict[str, tuple[str, ...]] = {
    "codna": ("repo_graph", "triage", "simulate", "fix", "apply"),
    "telys": ("local_runtime", "partitioned_vector", "ivf_partition"),
    "sqai": ("local_runtime", "structured_query"),
    "algenta": ("local_runtime", "repo_graph", "triage", "simulate", "fix", "apply"),
    "cohenta": ("local_runtime",),
    "decimas": ("local_runtime",),
    "escrypto": ("local_runtime",),
    "mission": ("local_runtime",),
}


class VerificationError(Exception):
    """The strict platform verifier rejected the token. Fail closed — never ship it."""


def build_oem_claims(
    *,
    product: str,
    tier: str,
    features: list[str],
    customer: str,
    org_id: str | None,
    exp_years: int,
    grace_days: int,
    license_id: str,
    device_thumbprint: str | None = None,
    issuer: str = PLATFORM_ISSUER,
    audience: str = PLATFORM_AUDIENCE,
    now: int | None = None,
) -> dict[str, object]:
    """Build the ver:2 OEM entitlement claims for one product. caps=0 (uncapped OEM pool), commercial +
    redistribution granted, deployment_class=oem, exp = now + exp_years, big offline grace."""
    now = int(now if now is not None else time.time())
    exp = now + int(exp_years * 365.25 * 86400)
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "sub": "device-license",
        "ver": SUPPORTED_LICENSE_VER,
        "jti": f"{license_id}-jti",
        "activation_id": f"{license_id}-act",
        "license_id": license_id,
        "iat": now,
        "issued_at": now,
        "exp": exp,
        "expires_at": exp,
        "offline_grace_days": int(grace_days),
        "grace_days": int(grace_days),
        "deployment_class": "oem",
        "products": {product: {"tier": tier, "features": list(features)}},
        # OEM/commercial extras (the strict verifier ignores these; the runtime + platform gate on them).
        # 0 = uncapped for an OEM pool (the local broker treats 0 as uncapped).
        "commercial_use": True,
        "redistribution_allowed": True,
        "plan": f"{product}_oem",
        "named_seat_limit": 0,
        "active_node_limit": 0,
        "concurrent_worker_limit": 0,
        "device_allowance_per_seat": 0,
        "oem": True,
        "customer": customer,
    }
    if org_id:
        claims["org_id"] = org_id
    if device_thumbprint:
        claims["device_pubkey_thumbprint"] = device_thumbprint
    return claims


def mint_oem_license(private_pem: str, claims: dict[str, object], *, kid: str = PLATFORM_KID) -> str:
    """RS256-sign the claims with the platform private key, stamping the platform `kid` header."""
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


def verify_platform_license(
    token: str,
    public_pem: str,
    *,
    product: str,
    now: int | None = None,
    issuer: str = PLATFORM_ISSUER,
    audiences: tuple[str, ...] = ACCEPTED_AUDIENCES,
) -> dict[str, object]:
    """STRICT offline verification mirroring telys/verify.py:verify_license — the contract every brand's
    runtime enforces. Pins RS256; requires the platform iss; an accepted aud; ver==2; a finite exp checked
    against now (+ offline_grace_days); and products.<product> present with a non-empty tier AND features.
    Raises VerificationError on any failure (fail closed)."""
    now = int(now if now is not None else time.time())
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:  # noqa: BLE001
        raise VerificationError(f"unreadable JWS header: {exc}") from exc
    if header.get("alg") != "RS256":
        raise VerificationError(f"alg must be RS256, got {header.get('alg')!r} (no none/HS*/negotiation)")
    try:
        # We verify the SIGNATURE here, but handle iss/aud/exp ourselves for grace + precise errors.
        claims = jwt.decode(
            token,
            public_pem,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_exp": False, "verify_iss": False},
        )
    except Exception as exc:  # noqa: BLE001 (bad signature / malformed)
        raise VerificationError(f"signature/format invalid: {exc}") from exc
    if claims.get("iss") != issuer:
        raise VerificationError(f"issuer {claims.get('iss')!r} != expected {issuer!r}")
    aud = claims.get("aud")
    aud_set = {aud} if isinstance(aud, str) else (set(aud) if isinstance(aud, list) else set())
    if not (aud_set & set(audiences)):
        raise VerificationError(f"audience {aud!r} not in accepted {list(audiences)}")
    ver = claims.get("ver")
    if isinstance(ver, bool) or ver != SUPPORTED_LICENSE_VER:
        raise VerificationError(f"ver {ver!r} unsupported (need v{SUPPORTED_LICENSE_VER})")
    exp = claims.get("exp", claims.get("expires_at"))
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        raise VerificationError("no finite numeric expiry ('exp') — expiry is required")
    grace = claims.get("offline_grace_days", claims.get("grace_days", 0))
    if isinstance(grace, bool) or not isinstance(grace, (int, float)) or grace < 0:
        raise VerificationError(f"invalid offline_grace_days: {grace!r}")
    if now > int(exp) + int(grace) * 86400:
        raise VerificationError(f"expired (exp={int(exp)}, grace_days={int(grace)}, now={now})")
    products = claims.get("products")
    if not isinstance(products, dict) or product not in products:
        raise VerificationError(f"does not grant product {product!r}")
    entry = products[product]
    if not isinstance(entry, dict) or not entry.get("tier"):
        raise VerificationError(f"product {product!r} missing a tier")
    feats = entry.get("features")
    if not isinstance(feats, list) or not feats:
        raise VerificationError(f"product {product!r} missing a non-empty features list")
    return claims


def audit_manifest(claims: dict[str, object], *, product: str, kid: str) -> dict[str, object]:
    """Machine-readable audit record for the license register (NOT a secret — safe to keep)."""
    exp = int(claims.get("exp", 0))
    iat = int(claims.get("iat", claims.get("issued_at", 0)))
    return {
        "product": product,
        "deployment_class": claims.get("deployment_class"),
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "kid": kid,
        "ver": claims.get("ver"),
        "license_id": claims.get("license_id"),
        "customer": claims.get("customer"),
        "org_id": claims.get("org_id"),
        "tier": (claims.get("products") or {}).get(product, {}).get("tier"),
        "features": (claims.get("products") or {}).get(product, {}).get("features"),
        "exp": exp,
        "exp_years": round((exp - iat) / (365.25 * 86400), 1) if exp and iat else None,
        "offline_grace_days": claims.get("offline_grace_days"),
        "commercial_use": claims.get("commercial_use"),
        "redistribution_allowed": claims.get("redistribution_allowed"),
        "caps": {
            "named_seat_limit": claims.get("named_seat_limit"),
            "active_node_limit": claims.get("active_node_limit"),
            "concurrent_worker_limit": claims.get("concurrent_worker_limit"),
        },
        "device_bound": bool(claims.get("device_pubkey_thumbprint")),
    }


def _public_pem_from_private(private_pem: str) -> str:
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Issue an indefinite (100y) OEM Algenta platform license for a sub-brand")
    p.add_argument("--product", required=True, choices=sorted(PRODUCT_DEFAULT_FEATURES), help="brand this license grants")
    p.add_argument("--customer", required=True, help="partner/customer name (e.g. codna)")
    p.add_argument("--org-id", dest="org_id", default=None, help="platform org id to stamp (default: --customer)")
    p.add_argument("--tier", default="enterprise", help="entitlement tier label")
    p.add_argument("--features", nargs="+", default=None, help="override the product's default feature set")
    p.add_argument("--exp-years", dest="exp_years", type=int, default=100, help="license lifetime in years")
    p.add_argument("--grace-days", dest="grace_days", type=int, default=3650, help="offline grace after exp")
    p.add_argument("--license-id", dest="license_id", default=None, help="stable id (default: oem-<product>-<customer>-<ts>)")
    p.add_argument("--device-thumbprint", dest="device_thumbprint", default=None,
                   help="optional ed25519:… to device-bind; omit for an infra-wide OEM license")
    p.add_argument("--key", default=_DEFAULT_KEY, help=f"platform private key PEM (default: {_DEFAULT_KEY})")
    p.add_argument("--aud", default=PLATFORM_AUDIENCE)
    p.add_argument("--iss", default=PLATFORM_ISSUER)
    p.add_argument("--kid", default=PLATFORM_KID)
    p.add_argument("--out", default=None, help="output token path (default: dist/oem/<product>-<customer>-license.jwt)")
    p.add_argument("--audit-out", dest="audit_out", default=None, help="audit manifest path (default: <out>.audit.json)")
    return p


def main(argv: list[str] | None = None) -> int:
    a = _build_parser().parse_args(argv)
    key_path = Path(a.key).expanduser()
    if not key_path.is_file():
        sys.stderr.write(f"platform private key not found: {key_path}\n")
        return 1
    private_pem = key_path.read_text(encoding="utf-8")

    ts = int(time.time())
    license_id = a.license_id or f"oem-{a.product}-{a.customer}-{ts}"
    org_id = a.org_id or a.customer
    features = list(a.features) if a.features else list(PRODUCT_DEFAULT_FEATURES[a.product])
    out = Path(a.out).expanduser() if a.out else Path("dist/oem") / f"{a.product}-{a.customer}-license.jwt"
    audit_out = Path(a.audit_out).expanduser() if a.audit_out else out.with_suffix(".audit.json")

    claims = build_oem_claims(
        product=a.product, tier=a.tier, features=features, customer=a.customer, org_id=org_id,
        exp_years=a.exp_years, grace_days=a.grace_days, license_id=license_id,
        device_thumbprint=a.device_thumbprint, issuer=a.iss, audience=a.aud, now=ts,
    )
    token = mint_oem_license(private_pem, claims, kid=a.kid)

    # Self-verify with the strict platform verifier BEFORE writing — never ship a rejectable token.
    try:
        verify_platform_license(
            token, _public_pem_from_private(private_pem), product=a.product, now=ts, issuer=a.iss
        )
    except VerificationError as exc:
        sys.stderr.write(f"self-verify FAILED, refusing to write: {exc}\n")
        return 1

    manifest = audit_manifest(claims, product=a.product, kid=a.kid)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(token + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    audit_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sys.stdout.write(
        "✓ OEM license issued + self-verified (strict platform verifier)\n"
        f"  product:  {a.product}   customer: {a.customer}   org_id: {org_id}\n"
        f"  tier:     {a.tier}   features: {features}\n"
        f"  iss/aud:  {a.iss} / {a.aud}   kid: {a.kid}   deployment_class: oem\n"
        f"  expires:  ~{manifest['exp_years']}y   offline_grace_days: {a.grace_days}   device_bound: {manifest['device_bound']}\n"
        f"  token:    {out}\n"
        f"  audit:    {audit_out}\n"
        "  ⚠ bearer credential — deliver over a secure channel; do NOT commit it.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
