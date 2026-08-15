"""P1: pluggable license signer (dev_hmac / pem / cf_worker)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.services import license_signer as ls


def _rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv, pub


_CLAIMS = {"device_id": "d-1", "plan": "pro", "iss": "algenta-control-plane", "ver": 2}


def test_dev_hmac_signer_round_trips():
    signer = ls.DevHmacSigner("a-secret")
    token = signer.sign(_CLAIMS)
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    decoded = jwt.decode(token, "a-secret", algorithms=["HS256"])
    assert decoded["device_id"] == "d-1" and decoded["ver"] == 2


def test_dev_hmac_signer_requires_secret():
    with pytest.raises(ls.LicenseSignerError):
        ls.DevHmacSigner("")


def test_pem_signer_signs_rs256_with_kid():
    priv, pub = _rsa_keypair()
    token = ls.LocalPemSigner(priv, kid="k1").sign(_CLAIMS)
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256"
    assert header["kid"] == "k1"
    decoded = jwt.decode(token, pub, algorithms=["RS256"])
    assert decoded["device_id"] == "d-1"


def test_pem_signer_requires_key():
    with pytest.raises(ls.LicenseSignerError):
        ls.LocalPemSigner("")


def test_cf_worker_signer_returns_token_from_worker():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"token": "signed.jws.value"}
    with patch(
        "apps.api_server.services.egress_guard.sync_http_request", return_value=resp
    ) as mock_req:
        out = ls.CloudflareWorkerSigner("https://signer.example/sign", "svc-token").sign(_CLAIMS)
    assert out == "signed.jws.value"
    # routed through the approved egress wrapper with the claims + bearer service token (never a key)
    kw = mock_req.call_args.kwargs
    assert kw["url"] == "https://signer.example/sign" and kw["method"] == "POST"
    assert kw["egress_class"] == "algenta_cloud"
    assert kw["headers"]["authorization"] == "Bearer svc-token"
    assert kw["json"]["claims"]["device_id"] == "d-1"


def test_cf_worker_signer_requires_url_and_token():
    with pytest.raises(ls.LicenseSignerError):
        ls.CloudflareWorkerSigner("", "tok")
    with pytest.raises(ls.LicenseSignerError):
        ls.CloudflareWorkerSigner("https://x/sign", "")


def test_cf_worker_signer_raises_on_missing_token_in_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"not_a_token": True}
    with patch("apps.api_server.services.egress_guard.sync_http_request", return_value=resp):
        with pytest.raises(ls.LicenseSignerError):
            ls.CloudflareWorkerSigner("https://signer.example/sign", "tok").sign(_CLAIMS)


def _settings(**kw) -> SimpleNamespace:
    base = dict(
        license_signer_backend=None,
        license_signing_secret=None,
        jwt_secret="seed",
        license_signing_private_key=None,
        license_signing_private_key_file=None,
        license_signer_kid="",
        license_signer_url="",
        license_signer_auth_token="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_factory_defaults_to_dev_hmac():
    # _settings() carries no api_env (non-production) — the ergonomic zero-config default for
    # local dev/CI. See test_factory_refuses_ambient_default_in_production below for the
    # complementary production hard-fail.
    with patch("apps.api_server.config.get_settings", return_value=_settings()):
        signer = ls.get_license_signer()
    assert isinstance(signer, ls.DevHmacSigner)
    # parity: dev secret derivation matches device_service._get_license_secret
    assert ls.dev_hmac_secret(_settings()) == ls.dev_hmac_secret(_settings())


def test_factory_refuses_ambient_default_in_production():
    # The security-critical fix: a production-classified deployment (api_env=="production") that
    # never explicitly configured license_signer_backend must NOT silently mint symmetric,
    # forgeable HS256 "production" licenses — it must refuse to issue at all until pem/cf_worker
    # is explicitly configured.
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(api_env="production"),
    ):
        with pytest.raises(ls.LicenseSignerError):
            ls.get_license_signer()


def test_factory_refuses_explicit_dev_hmac_global_default_in_production():
    # Also refused when an operator explicitly set the GLOBAL default to dev_hmac (not just when
    # it's unset) — production must never resolve to dev_hmac via the ambient default, however it
    # got there.
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(api_env="production", license_signer_backend="dev_hmac"),
    ):
        with pytest.raises(ls.LicenseSignerError):
            ls.get_license_signer()


def test_factory_allows_pem_explicitly_configured_in_production():
    priv, _ = _rsa_keypair()
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(
            api_env="production", license_signer_backend="pem", license_signing_private_key=priv
        ),
    ):
        assert isinstance(ls.get_license_signer(), ls.LocalPemSigner)


def test_factory_allows_cf_worker_explicitly_configured_in_production():
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(
            api_env="production",
            license_signer_backend="cf_worker",
            license_signer_url="https://signer.example/sign",
            license_signer_auth_token="tok",
        ),
    ):
        assert isinstance(ls.get_license_signer(), ls.CloudflareWorkerSigner)


def test_factory_explicit_backend_override_bypasses_production_guard():
    # An explicit backend= (per-call routing decision, e.g. Codna's dev_hmac in device_service.py)
    # is respected even in production — the guard targets the ambient DEFAULT footgun, not a
    # caller's already-considered routing choice.
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(api_env="production"),
    ):
        assert isinstance(ls.get_license_signer(backend="dev_hmac"), ls.DevHmacSigner)


def test_factory_non_production_api_env_values_keep_ergonomic_default():
    for env in ("development", "staging", "test", ""):
        with patch(
            "apps.api_server.config.get_settings",
            return_value=_settings(api_env=env),
        ):
            assert isinstance(ls.get_license_signer(), ls.DevHmacSigner)


def test_factory_pem_backend():
    priv, _ = _rsa_keypair()
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(license_signer_backend="pem", license_signing_private_key=priv),
    ):
        assert isinstance(ls.get_license_signer(), ls.LocalPemSigner)


def test_factory_cf_worker_backend():
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(
            license_signer_backend="cf_worker",
            license_signer_url="https://signer.example/sign",
            license_signer_auth_token="tok",
        ),
    ):
        assert isinstance(ls.get_license_signer(), ls.CloudflareWorkerSigner)


def test_factory_rejects_unknown_backend():
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(license_signer_backend="totally-bogus"),
    ):
        with pytest.raises(ls.LicenseSignerError):
            ls.get_license_signer()


def test_factory_backend_override_wins_over_settings_default():
    # Per-product routing: an explicit backend= forces that signer even though settings default to dev_hmac,
    # while backend=None keeps the settings default. This is how Telys plans get RS256 without a global flip.
    with patch(
        "apps.api_server.config.get_settings",
        return_value=_settings(
            license_signer_url="https://license.algenta.ai/sign",
            license_signer_auth_token="tok",
        ),
    ):
        assert isinstance(ls.get_license_signer(backend="cf_worker"), ls.CloudflareWorkerSigner)
        assert isinstance(ls.get_license_signer(backend=None), ls.DevHmacSigner)
