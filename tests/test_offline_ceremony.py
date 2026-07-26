"""Air-gap offline ceremony end-to-end: request → response → runtime consumes.

A node generates a request (bound to its device-key thumbprint); the operator mints a response
(a deployment license bound to that thumbprint, capped at the approved units); the runtime parses
the response as a deployment-scope license that verifies + carries the ceiling.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runtime import license as L
from apps.runtime.offline_ceremony import (
    OfflineRequestError,
    build_offline_request,
    parse_offline_request,
)

_REPO = Path(__file__).resolve().parent.parent


# ── request build/parse (pure) ────────────────────────────────────────────────


def test_build_and_parse_roundtrip() -> None:
    req = build_offline_request(
        product="algenta", deployment_id="prod-us", device_pubkey_thumbprint="ed25519:K",
        requested_units=16, nonce="abc", generated_at=1000, effective_vcpu=64.0,
    )
    parsed = parse_offline_request(json.dumps(req))
    assert parsed["product"] == "algenta" and parsed["requested_units"] == 16
    assert parsed["device_pubkey_thumbprint"] == "ed25519:K"


def test_build_requires_binding() -> None:
    with pytest.raises(OfflineRequestError, match="device_pubkey_thumbprint"):
        build_offline_request(product="algenta", deployment_id="d", device_pubkey_thumbprint="",
                              requested_units=4, nonce="n", generated_at=1)


def test_parse_rejects_missing_fields() -> None:
    with pytest.raises(OfflineRequestError, match="missing required fields"):
        parse_offline_request({"algenta_offline_request": 1, "product": "algenta"})


# ── full CLI ceremony round-trip ──────────────────────────────────────────────


def test_offline_ceremony_end_to_end(tmp_path: Path, monkeypatch) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = tmp_path / "cp.pem"
    priv.write_text(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode())
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # step 1 (node): generate a request bound to a device thumbprint
    req_path = tmp_path / "request.json"
    r1 = subprocess.run(
        [sys.executable, str(_REPO / "scripts" / "generate_offline_request.py"),
         "--product", "algenta", "--deployment-id", "prod-us", "--requested-units", "16",
         "--output", str(req_path), "--device-pubkey-thumbprint", "ed25519:NODEKEY"],
        capture_output=True, text=True, cwd=str(_REPO),
    )
    assert r1.returncode == 0, r1.stderr
    assert req_path.exists()
    req = json.loads(req_path.read_text())
    assert req["device_pubkey_thumbprint"] == "ed25519:NODEKEY"
    assert "nonce" in req and req["requested_units"] == 16

    # step 2 (operator/portal): mint the response, capping at 8 of the requested 16
    resp_path = tmp_path / "response.jwt"
    r2 = subprocess.run(
        [sys.executable, str(_REPO / "scripts" / "issue_offline_response.py"),
         "--request", str(req_path), "--private-key-file", str(priv), "--org-id", "org-acme",
         "--approved-units", "8", "--output", str(resp_path)],
        capture_output=True, text=True, cwd=str(_REPO),
    )
    assert r2.returncode == 0, r2.stderr
    assert resp_path.exists()

    # step 3 (node): the runtime consumes the response as a deployment license
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", pub)
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "algenta")
    lic = L._parse_token(resp_path.read_text().strip())
    assert lic is not None and lic.valid
    assert lic.is_deployment_scope()
    assert lic.deployment_id == "prod-us"
    assert lic.max_concurrent_units == 8  # operator-approved cap, not the requested 16
    assert lic.device_pubkey_thumbprint == "ed25519:NODEKEY"  # bound to the request's device key
