"""Device license identity claims (P3b-A1).

The issued license now carries: activation_id (stable per org+device — the CRL revokes by
it), license_id + jti (per-issuance), and device_pubkey_thumbprint. Additive + back-compat
(ver stays 1); the runtime already parses these. Foundation for renewal PoP + CRL.
"""

from __future__ import annotations

import uuid

import jwt

from apps.api_server.services.device_service import _activation_id, _issue_license_jwt

_ORG = "11111111-1111-1111-1111-111111111111"
_DEVICE = "device-fingerprint-abc123"


def _claims(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


# ── activation_id derivation ───────────────────────────────────────────────────


def test_activation_id_is_deterministic_and_opaque() -> None:
    a1 = _activation_id(_ORG, _DEVICE)
    a2 = _activation_id(_ORG, _DEVICE)
    assert a1 == a2  # stable
    uuid.UUID(a1)  # valid uuid
    # different device or org → different id
    assert _activation_id(_ORG, "other-device") != a1
    assert _activation_id("22222222-2222-2222-2222-222222222222", _DEVICE) != a1
    # opaque: org_id / device_id not recoverable from the id
    assert _ORG not in a1 and _DEVICE not in a1


def test_activation_id_falls_back_for_non_uuid_org() -> None:
    a = _activation_id("not-a-uuid", _DEVICE)
    uuid.UUID(a)  # still a valid uuid (NIL-namespace fallback)


# ── issued claim set ───────────────────────────────────────────────────────────


def test_license_carries_identity_claims() -> None:
    token = _issue_license_jwt(
        device_id=_DEVICE,
        api_key_prefix="ak_test",
        plan="pro",
        device_limit=5,
        org_id=_ORG,
        device_pubkey_thumbprint="ed25519:THUMB",
    )
    c = _claims(token)
    assert c["activation_id"] == _activation_id(_ORG, _DEVICE)
    assert c["jti"] == c["license_id"]
    uuid.UUID(c["license_id"])
    assert c["device_pubkey_thumbprint"] == "ed25519:THUMB"
    # back-compat: existing claims intact
    assert c["ver"] == 1
    assert c["device_id"] == _DEVICE
    assert c["org_id"] == _ORG
    assert c["plan"] == "pro"
    assert c["sub"] == "device-license"


def test_thumbprint_defaults_empty_for_legacy_issuance() -> None:
    token = _issue_license_jwt(
        device_id=_DEVICE, api_key_prefix="ak", plan="pro", device_limit=0, org_id=_ORG
    )
    assert _claims(token)["device_pubkey_thumbprint"] == ""


def test_activation_id_stable_but_license_id_unique_across_reissue() -> None:
    t1 = _issue_license_jwt(
        device_id=_DEVICE, api_key_prefix="ak", plan="pro", device_limit=0, org_id=_ORG
    )
    t2 = _issue_license_jwt(
        device_id=_DEVICE, api_key_prefix="ak", plan="pro", device_limit=0, org_id=_ORG
    )
    c1, c2 = _claims(t1), _claims(t2)
    assert c1["activation_id"] == c2["activation_id"]  # stable per device
    assert c1["license_id"] != c2["license_id"]  # per-issuance


# ── runtime parser round-trip ──────────────────────────────────────────────────


def test_runtime_parses_identity_claims() -> None:
    from apps.runtime.license import _device_license_from_payload

    token = _issue_license_jwt(
        device_id=_DEVICE,
        api_key_prefix="ak",
        plan="pro",
        device_limit=0,
        org_id=_ORG,
        device_pubkey_thumbprint="ed25519:THUMB",
    )
    lic = _device_license_from_payload(
        _claims(token), source="test", api_key="", default_plan="free"
    )
    assert lic.activation_id == _activation_id(_ORG, _DEVICE)
    assert lic.license_id == _claims(token)["license_id"]
    assert lic.device_pubkey_thumbprint == "ed25519:THUMB"
