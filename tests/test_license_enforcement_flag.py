"""P5.2 — fail-closed enforcement MACHINERY, default OFF (reversible, no behavior change).

The whole point of P5.2: ship the wiring that CAN enforce a local license on self-hosted, but keep
it DARK by default so every current deployment/dev/CI keeps running unchanged. These tests pin
that the default is OFF (the load-bearing guarantee), that enforcement engages only when explicitly
opted in, and that the runtime now ACCEPTS aud-bearing tokens (forward-compat for P5.7).
"""

from __future__ import annotations

import importlib
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.privacy_policy import build_privacy_policy, policy_from_environment

# ── the flag defaults OFF everywhere (the no-behavior-change guarantee) ─────────


def test_enforce_flag_defaults_off() -> None:
    assert build_privacy_policy().enforce_license_validation is False
    assert policy_from_environment(env={}).enforce_license_validation is False
    # self-hosted (the profile P5 will eventually flip) is STILL off by default
    assert (
        build_privacy_policy(deployment_mode="self_hosted").enforce_license_validation is False
    )


def test_enforce_flag_opt_in() -> None:
    assert build_privacy_policy(enforce_license_validation=True).enforce_license_validation is True
    assert (
        policy_from_environment(
            env={"ALGENTA_ENFORCE_LICENSE_VALIDATION": "1"}
        ).enforce_license_validation
        is True
    )


def test_config_default_off() -> None:
    from apps.api_server.config import Settings

    assert Settings().privacy_policy.enforce_license_validation is False


# ── the self-host bypass routes through the flag ───────────────────────────────


def test_offline_execution_bypass_dark_by_default(monkeypatch) -> None:
    import apps.runtime.credits as credits

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    # default OFF → free self-host stays free (no license required), exactly as today
    assert credits._offline_execution_entitled() is True


def test_offline_execution_enforced_when_opted_in(monkeypatch) -> None:
    import apps.runtime.credits as credits
    import apps.runtime.license as lic

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", "1")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    # opted in → no early grant; it falls through to the stored-license check
    monkeypatch.setattr(lic, "stored_offline_execution_entitlement", lambda *a, **k: False)
    assert credits._offline_execution_entitled() is False  # no license → denied
    monkeypatch.setattr(lic, "stored_offline_execution_entitlement", lambda *a, **k: True)
    assert credits._offline_execution_entitled() is True  # valid license → allowed


# ── aud-accept: tokens WITH aud now verify (forward-compat; aud-require is P5.7) ─


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


def test_aud_bearing_token_verifies(monkeypatch) -> None:
    priv, pub = _rsa_keypair()
    now = int(time.time())
    claims = {
        "iss": "https://license.algenta.ai",
        "aud": "device-license",  # ← previously caused InvalidAudienceError
        "sub": "device-license",
        "ver": 2,
        "device_id": "d",
        "activation_id": "a",
        "expires_at": now + 600,
        "key_expires_at": now + 600,
        "grace_days": 3,
        "issued_at": now,
    }
    token = jwt.encode(claims, priv, algorithm="RS256", headers={"kid": "k"})
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", pub)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import apps.runtime.license as _lic

    rt = importlib.reload(_lic)
    try:
        parsed = rt._parse_token(token, "")
        assert parsed is not None and parsed.valid is True and parsed.license_version == 2
    finally:
        importlib.reload(rt)
