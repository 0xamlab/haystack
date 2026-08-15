"""RS256-only production mode (apps/runtime/license.py) + the hardening preflight guard.

The runtime half of the artifact split: with ALGENTA_LICENSE_RS256_ONLY=1, NO HS256 token — the
forgeable source-secret dev stub OR the control-plane HS256 secret — is accepted for ANY product;
only asymmetric RS256 verifies. This is now additive hardening on top of a default that is ALREADY
RS256-only for every product except the one still shipping HS256 by deliberate, already-reviewed
design (Codna — see apps/runtime/license.py's `_HS256_LEGACY_PERMITTED_PRODUCTS`, mirroring
apps/api_server/services/product_registry.py's `rs256_license=False`). ALGENTA_LICENSE_RS256_ONLY
closes that one remaining legacy product too, and is what an operator flips to harden Codna itself.
"""
from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runtime import license as L


def _rs256_offline_token(monkeypatch) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", pub)
    return jwt.encode(
        {"ver": 2, "plan": "enterprise", "device_id": "d", "sub": "device-license",
         "expires_at": 0, "grace_days": 14},
        priv, algorithm="RS256",
    )


def _dev_hs256_token() -> str:
    return jwt.encode(
        {"ver": 2, "plan": "enterprise", "device_id": "d", "sub": "device-license"},
        L._DEV_SECRET, algorithm="HS256",
    )


def test_rs256_only_rejects_dev_stub_hs256(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_RS256_ONLY", "1")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    assert L._parse_token(_dev_hs256_token()) is None


def test_rs256_only_rejects_control_plane_hs256(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_RS256_ONLY", "1")
    monkeypatch.setenv("JWT_SECRET", "seed-xyz")
    # a token signed with a derived control-plane HS256 secret — accepted WITHOUT the flag, rejected WITH it
    import hashlib

    secret = hashlib.sha256(("seed-xyz" + ":license-signing").encode()).hexdigest()
    tok = jwt.encode({"ver": 2, "plan": "pro", "device_id": "d", "sub": "device-license"},
                     secret, algorithm="HS256")
    assert L._parse_token(tok) is None


def test_rs256_only_accepts_rs256(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_RS256_ONLY", "1")
    tok = _rs256_offline_token(monkeypatch)
    lic = L._parse_token(tok)
    assert lic is not None and lic.valid and lic.plan == "enterprise"


def test_hs256_rejected_by_default_for_non_legacy_product(monkeypatch) -> None:
    # This is the actual fix: even with the flag OFF and require_local_license unset, HS256 is now
    # hard-rejected by DEFAULT for the default runtime product (algenta) — the old opt-in
    # "strict mode" footgun (accept-unless-hardened) is gone. Regression test for the HS256 fix.
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_RUNTIME_PRODUCT", raising=False)
    lic = L._parse_token(_dev_hs256_token())
    assert lic is None


def test_hs256_still_works_for_codna_legacy_product(monkeypatch) -> None:
    # Codna's shipped runtime still verifies HS256 by explicit, already-reviewed product-registry
    # design (rs256_license=False) — this ONE product keeps the legacy HS256 path with the flag
    # off, so its live install base is unaffected. Every other product does not (see above).
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    lic = L._parse_token(_dev_hs256_token())
    assert lic is not None and lic.valid


def test_hs256_rejected_for_codna_when_rs256_only_flag_set(monkeypatch) -> None:
    # An operator can still harden Codna itself with the explicit flag — it's additive, not the
    # only path to RS256-only for non-legacy products.
    monkeypatch.setenv("ALGENTA_LICENSE_RS256_ONLY", "1")
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    assert L._parse_token(_dev_hs256_token()) is None


def test_require_local_license_implies_rs256_only(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    assert L._rs256_only_enforced() is True
    assert L._parse_token(_dev_hs256_token()) is None


# ── preflight guard ──────────────────────────────────────────────────────────


def test_hardening_preflight_flags_unhardened(monkeypatch) -> None:
    from scripts.check_license_hardening import hardening_violations

    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_LICENSE_TRUST_BUNDLE", raising=False)
    v = hardening_violations()
    assert any("RS256-only mode is OFF" in x for x in v)
    assert any("no verification key" in x for x in v)


def test_hardening_preflight_passes_when_hardened(monkeypatch) -> None:
    from scripts.check_license_hardening import hardening_violations

    monkeypatch.setenv("ALGENTA_LICENSE_RS256_ONLY", "1")
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----")
    assert hardening_violations() == []
