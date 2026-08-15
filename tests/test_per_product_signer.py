"""Per-product license signing (device_service): Telys → cf_worker (RS256, license.algenta.ai) with a payload the
Worker + telys.verify accept; Codna/Algenta → dev_hmac (HS256), untouched — even when the ambient global
LICENSE_SIGNER_BACKEND is cf_worker. The RS256 product set is config-extensible so Algenta external users (same
model, coming next) can be enabled with no code change.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest

from apps.api_server.services import device_service as ds
from apps.api_server.services.license_signer import LicenseSignerError


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
        rs256_license_products=None,
        license_v2_issuance=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# cf_worker fully configured (as it is in prod after the Fly secrets land).
_CF = dict(
    license_signer_url="https://license.algenta.ai/sign",
    license_signer_auth_token="svc-token",
)


class _CapturingSigner:
    """Records the claims it is asked to sign (stands in for the cf_worker so tests never hit the network)."""

    def __init__(self):
        self.claims = None

    def sign(self, claims):
        self.claims = dict(claims)
        return "captured.rs256.token"


# ── routing decision ────────────────────────────────────────────────────────────
def test_telys_plan_routes_to_cf_worker_when_configured():
    s = _settings(**_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("telys_developer", s) is True


def test_codna_plan_never_routes_to_cf_worker():
    s = _settings(**_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("pro", s) is False


def test_no_routing_without_cf_configured():
    s = _settings()  # dev/test: no signer URL
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("telys_pro", s) is False


def test_algenta_plan_routes_to_cf_worker_when_configured():
    # Algenta joins telys on RS256/cf_worker (external users, same offline model).
    s = _settings(**_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("algenta_free", s) is True
        assert ds._use_cf_worker_signer("algenta_pro", s) is True


def test_products_map_emitted_for_telys_even_when_signer_override_excludes_it():
    # Regression for the review footgun: emission follows the REGISTRY, not the operator signer override.
    # A narrowed rs256_license_products (here dropping telys) must NEVER suppress telys' required
    # products.telys claim — else a paying telys runtime fails closed. Emission != signer routing.
    s = _settings(rs256_license_products="algenta")  # deliberately excludes telys from the SIGNER set
    with patch("apps.api_server.config.get_settings", return_value=s):
        token = ds._issue_license_jwt("dev-1", "ak_abc", "telys_pro", 1, "org-1")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "telys" in claims.get("products", {}), "telys products map suppressed by a signer override!"
    assert claims["products"]["telys"]["features"]


def test_algenta_plan_emits_products_map_even_without_cf_worker():
    # algenta_* plans always carry products.algenta (with non-empty features), independent of whether the
    # cf_worker signer is configured — its bundled runtime verifies the license offline and needs the claim.
    s = _settings()  # no signer configured (dev/test) → dev_hmac HS256
    with patch("apps.api_server.config.get_settings", return_value=s):
        token = ds._issue_license_jwt("dev-1", "ak_abc", "algenta_pro", 1, "org-1")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "algenta" in claims.get("products", {})
    assert claims["products"]["algenta"]["features"]
    assert jwt.get_unverified_header(token)["alg"] == "HS256"  # emission ≠ signing: still dev_hmac here


def test_rs256_product_set_extensible_via_env_string():
    # The exact hook Algenta external will use: RS256_LICENSE_PRODUCTS="telys,algenta" (comma-separated env
    # string). Here we opt "codna" in purely to prove the mechanism routes by config, no code change.
    s = _settings(rs256_license_products="telys,codna", **_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("pro", s) is True


def test_rs256_product_set_accepts_explicit_iterable():
    s = _settings(rs256_license_products={"telys", "codna"}, **_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        assert ds._use_cf_worker_signer("pro", s) is True


# ── the load-bearing safety property (regression for review blocker #1) ──────────
def test_codna_stays_hs256_even_when_global_backend_is_cf_worker():
    # If LICENSE_SIGNER_BACKEND=cf_worker were allowed to widen routing, a codna plan would mint an RS256 license
    # its HS256 runtime rejects. The explicit dev_hmac in the else-branch prevents that.
    s = _settings(license_signer_backend="cf_worker", **_CF)
    with patch("apps.api_server.config.get_settings", return_value=s):
        token = ds._issue_license_jwt("dev-1", "ak_abc", "pro", 1, "org-1")
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


# ── telys payload satisfies the Worker policy + telys.verify (regression for #2) ─
def test_telys_payload_shaped_for_worker_and_verifier():
    s = _settings(**_CF)
    fake = _CapturingSigner()
    now = int(time.time())
    with patch("apps.api_server.config.get_settings", return_value=s), patch(
        "apps.api_server.services.license_signer.get_license_signer", return_value=fake
    ):
        out = ds._issue_license_jwt("dev-1", "ak_abc", "telys_developer", 1, "org-1")
    assert out == "captured.rs256.token"
    c = fake.claims
    # Worker.policyError + telys.verify requirements:
    assert c["iss"] == "https://license.algenta.ai"      # not the legacy _JWT_ISSUER
    assert c["aud"] == "algenta-runtime"
    assert c["ver"] == 2
    assert c["jti"] and c["activation_id"]
    assert isinstance(c["exp"], int) and c["exp"] > now
    assert c["exp"] - now <= 90 * 86400                   # under the worker's MAX_TTL_SECONDS
    assert c["exp"] == c["expires_at"]                    # internally consistent
    assert c["products"]["telys"]["tier"] and c["products"]["telys"]["features"]


def test_codna_payload_keeps_legacy_issuer_and_no_exp():
    # The dev_hmac/Codna path must NOT be reshaped: keeps iss=algenta-control-plane + expires_at, no standard exp.
    s = _settings(**_CF)
    fake = _CapturingSigner()
    with patch("apps.api_server.config.get_settings", return_value=s), patch(
        "apps.api_server.services.license_signer.get_license_signer", return_value=fake
    ):
        ds._issue_license_jwt("dev-1", "ak_abc", "pro", 1, "org-1")
    c = fake.claims
    assert c["iss"] == ds._JWT_ISSUER
    assert "exp" not in c
    assert "expires_at" in c


# ── production safety net: RS256-required products must never silently fall back to HS256 ──────


def test_algenta_plan_refuses_dev_hmac_fallback_in_production_without_cf_worker():
    # algenta_pro is RS256-required by the registry. If cf_worker isn't configured (so
    # _use_cf_worker_signer returns False) AND this deployment is production-classified, issuance
    # must refuse outright rather than silently mint a forgeable/incompatible HS256 license.
    s = _settings(api_env="production")  # no cf_worker configured
    with patch("apps.api_server.config.get_settings", return_value=s):
        with pytest.raises(LicenseSignerError):
            ds._issue_license_jwt("dev-1", "ak_abc", "algenta_pro", 1, "org-1")


def test_telys_plan_refuses_dev_hmac_fallback_in_production_without_cf_worker():
    s = _settings(api_env="production")
    with patch("apps.api_server.config.get_settings", return_value=s):
        with pytest.raises(LicenseSignerError):
            ds._issue_license_jwt("dev-1", "ak_abc", "telys_developer", 1, "org-1")


def test_algenta_plan_issues_via_cf_worker_in_production_when_configured():
    # The safety net never fires when cf_worker IS configured — _use_cf_worker_signer routes there
    # first, same as in dev/test.
    s = _settings(api_env="production", **_CF)
    fake = _CapturingSigner()
    with patch("apps.api_server.config.get_settings", return_value=s), patch(
        "apps.api_server.services.license_signer.get_license_signer", return_value=fake
    ):
        token = ds._issue_license_jwt("dev-1", "ak_abc", "algenta_pro", 1, "org-1")
    assert token == "captured.rs256.token"


def test_codna_plan_unaffected_by_production_guard_without_cf_worker():
    # The load-bearing safety property: Codna's plans never intersect the RS256 product set, so
    # the new production guard NEVER fires for it — Codna keeps issuing HS256 in production
    # exactly as it always has, cf_worker configured or not.
    s = _settings(api_env="production")  # no cf_worker configured
    with patch("apps.api_server.config.get_settings", return_value=s):
        token = ds._issue_license_jwt("dev-1", "ak_abc", "pro", 1, "org-1")
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
