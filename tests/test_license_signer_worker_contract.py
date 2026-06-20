"""License-signer Worker contract (P4b).

The signer Worker (infra/cloudflare/license-signer/worker.js) holds the RS256 key and returns
{"token": "<RS256 JWS>"} for a posted claim set. This test proves the END-TO-END contract WITHOUT
the JS runtime:
  (1) a Worker-shaped RS256+kid token verifies in the runtime (apps.runtime.license._parse_token),
  (2) the public key publishes as a JWKS the runtime can select by kid (license_jwk), and
  (3) the server-side CloudflareWorkerSigner POSTs {"claims": ...} + Bearer and parses {"token"},
      failing closed on HTTP errors / a missing token.

If the Worker's emitted token shape drifts from what the runtime accepts, (1)/(2) break here.
"""

from __future__ import annotations

import importlib
import sys
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KID = "algenta-license-2026"


def _rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


def _v2_claims() -> dict:
    now = int(time.time())
    # NOTE: no "aud" claim yet — the runtime does not pin audience today (aud-pinning is P5).
    # The Worker enforces aud only IF present, so it is ready for that flip.
    return {
        "iss": "https://license.algenta.ai",
        "sub": "device-license",
        "jti": "lic_contract_1",
        "license_id": "lic_contract_1",
        "activation_id": "act_contract_1",
        "ver": 2,
        "plan": "team",
        "deployment_class": "server",
        "device_id": "device-contract",
        "api_key_prefix": "ak_contract",
        "issued_at": now,
        "exp": now + 7 * 86400,
        "expires_at": now + 7 * 86400,
        "key_expires_at": now + 7 * 86400,
        "grace_days": 3,
        "permitted_modules": ["*"],
        "device_pubkey_thumbprint": "ed25519:THUMB",
        "products": {"codna": {"tier": "team", "features": ["repo_graph", "triage", "fix"]}},
        "named_seat_limit": 5,
        "active_node_limit": 2,
        "concurrent_worker_limit": 4,
        "entitlement_version": 7,
        "commercial_use": True,
    }


def _worker_token(priv: str, claims: dict) -> str:
    """What worker.js emits: RS256 + a kid header over the posted claims."""
    return jwt.encode(claims, priv, algorithm="RS256", headers={"kid": _KID})


# ── (1) the Worker token verifies in the runtime ───────────────────────────────


def test_worker_token_verifies_in_runtime(monkeypatch) -> None:
    priv, pub = _rsa_keypair()
    token = _worker_token(priv, _v2_claims())
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")  # strict: RS256 only
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", pub)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    rt = importlib.reload(sys.modules["apps.runtime.license"]) if "apps.runtime.license" in sys.modules \
        else importlib.import_module("apps.runtime.license")
    try:
        parsed = rt._parse_token(token, "")
        assert parsed is not None and parsed.valid is True
        assert parsed.license_version == 2
        assert parsed.activation_id == "act_contract_1"
        assert parsed.has_product("codna")
        assert parsed.product_features("codna") == frozenset({"repo_graph", "triage", "fix"})
        assert parsed.worker_limit() == 4
        assert parsed.device_pubkey_thumbprint == "ed25519:THUMB"
    finally:
        importlib.reload(rt)  # restore default module state for other tests


# ── (2) the public key publishes as a JWKS selectable by kid ───────────────────


def test_worker_public_key_publishes_as_jwks() -> None:
    from apps.api_server.services.license_jwk import build_rsa_jwk_from_public_pem

    _priv, pub = _rsa_keypair()
    jwk = build_rsa_jwk_from_public_pem(pub, _KID)
    assert jwk is not None
    assert jwk["kid"] == _KID and jwk["kty"] == "RSA" and jwk["alg"] == "RS256"
    # the token header's kid matches the published JWK kid → a consumer can select the key
    token = _worker_token(_priv, _v2_claims())
    assert jwt.get_unverified_header(token)["kid"] == jwk["kid"]


# ── (3) the server-side signer calls + parses the Worker correctly ─────────────


def test_cloudflare_worker_signer_posts_claims_and_returns_token(monkeypatch) -> None:
    from apps.api_server.services import egress_guard, license_signer

    captured = {}

    def _fake_http(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status_code=200, json=lambda: {"token": "signed.jwt.here"})

    monkeypatch.setattr(egress_guard, "sync_http_request", _fake_http)
    signer = license_signer.CloudflareWorkerSigner("https://license.algenta.ai/sign", "svc-token")
    claims = {"ver": 2, "jti": "x"}
    token = signer.sign(claims)

    assert token == "signed.jwt.here"
    assert captured["json"] == {"claims": claims}  # contract: body is {"claims": ...}
    assert captured["headers"]["authorization"] == "Bearer svc-token"
    assert captured["method"] == "POST"


def test_cloudflare_worker_signer_fails_closed(monkeypatch) -> None:
    from apps.api_server.services import egress_guard, license_signer

    # HTTP >= 400 → error
    monkeypatch.setattr(
        egress_guard,
        "sync_http_request",
        lambda **k: SimpleNamespace(status_code=422, json=lambda: {"error": {"code": "policy"}}),
    )
    signer = license_signer.CloudflareWorkerSigner("https://license.algenta.ai/sign", "t")
    with pytest.raises(license_signer.LicenseSignerError):
        signer.sign({"ver": 2})

    # 200 but no token → error
    monkeypatch.setattr(
        egress_guard,
        "sync_http_request",
        lambda **k: SimpleNamespace(status_code=200, json=lambda: {}),
    )
    with pytest.raises(license_signer.LicenseSignerError):
        signer.sign({"ver": 2})
