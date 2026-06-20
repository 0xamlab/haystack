"""Runtime CRL enforcement (P3b-D2).

The ONLY path that can falsely break a paying customer, so it errs entirely toward NOT
revoking: a license is revoked ONLY when a positively-VERIFIED CRL explicitly lists its
activation_id. v1/legacy licenses are exempt (dormant until the P5 flip); every uncertainty
(offline, bad signature, expired CRL) keeps the license.
"""

from __future__ import annotations

import json

import jwt
import pytest

from apps.runtime import license as rt
from apps.runtime.license import _DEV_SECRET, DeviceLicense


@pytest.fixture(autouse=True)
def _clear_crl_cache():
    rt._crl_cache.clear()
    yield
    rt._crl_cache.clear()


def _license(*, version: int, activation_id: str) -> DeviceLicense:
    return DeviceLicense(
        valid=True,
        plan="pro",
        device_id="dev-abc",
        device_limit=0,
        permitted_modules=["*"],
        expires_at=0,
        key_expires_at=0,
        grace_days=0,
        api_key_prefix="ak",
        issued_at=1,
        license_version=version,
        activation_id=activation_id,
    )


# ── the DARK gate: v1 / unbound never revoked, never even fetches ──────────────


def test_v1_license_never_revoked_and_skips_fetch(monkeypatch) -> None:
    monkeypatch.setattr(rt, "_fetch_revocation_list", lambda: pytest.fail("v1 must not fetch CRL"))
    assert rt._is_license_revoked(_license(version=1, activation_id="act-1")) is False


def test_v2_without_activation_id_never_revoked(monkeypatch) -> None:
    monkeypatch.setattr(rt, "_fetch_revocation_list", lambda: pytest.fail("must not fetch"))
    assert rt._is_license_revoked(_license(version=2, activation_id="")) is False


# ── v2 revocation decision ─────────────────────────────────────────────────────


def test_v2_revoked_when_activation_id_listed(monkeypatch) -> None:
    monkeypatch.setattr(
        rt, "_fetch_revocation_list", lambda: {"revoked": [{"activation_id": "act-X"}]}
    )
    assert rt._is_license_revoked(_license(version=2, activation_id="act-X")) is True


def test_v2_not_revoked_when_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        rt, "_fetch_revocation_list", lambda: {"revoked": [{"activation_id": "someone-else"}]}
    )
    assert rt._is_license_revoked(_license(version=2, activation_id="act-X")) is False


# ── FAIL-OPEN: every uncertainty keeps the license ────────────────────────────


def test_fail_open_when_crl_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(rt, "_fetch_revocation_list", lambda: None)
    assert rt._is_license_revoked(_license(version=2, activation_id="act-X")) is False


def test_fail_open_when_revoked_malformed(monkeypatch) -> None:
    monkeypatch.setattr(rt, "_fetch_revocation_list", lambda: {"revoked": "not-a-list"})
    assert rt._is_license_revoked(_license(version=2, activation_id="act-X")) is False


# ── _fetch_revocation_list: verify signature + valid_until, fail-open ──────────


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a) -> bool:
        return False


# The CRL must be signed by the CONTROL-PLANE secret (never the public dev stub). _wire sets a
# known control-plane secret the runtime will trust.
_CP_SECRET = "test-control-plane-license-secret"


def _mk_crl_jwt(secret: str, *, valid_until: int, revoked: list[dict]) -> str:
    return jwt.encode(
        {"revoked": revoked, "version": 1, "valid_until": valid_until, "iss": "algenta-control-plane"},
        secret,
        algorithm="HS256",
    )


def _wire(monkeypatch, crl_jwt: str | None, *, raise_exc: Exception | None = None) -> None:
    monkeypatch.setenv("LICENSE_SIGNING_SECRET", _CP_SECRET)
    monkeypatch.setattr(rt, "_validated_control_plane_url", lambda **k: "https://cp.test")

    def _urlopen(req, surface=None, timeout=None):
        if raise_exc is not None:
            raise raise_exc
        return _Resp({"crl": crl_jwt} if crl_jwt is not None else {})

    monkeypatch.setattr(rt, "runtime_urlopen", _urlopen)


def test_fetch_verifies_signed_crl(monkeypatch) -> None:
    crl = _mk_crl_jwt(_CP_SECRET, valid_until=1_900_000_000, revoked=[{"activation_id": "act-X"}])
    _wire(monkeypatch, crl)
    payload = rt._fetch_revocation_list()
    assert payload is not None
    assert payload["revoked"][0]["activation_id"] == "act-X"


def test_fetch_rejects_wrong_signature(monkeypatch) -> None:
    # Signed with a DIFFERENT secret the runtime does not trust → unverifiable → None (fail-open).
    crl = _mk_crl_jwt("attacker-secret", valid_until=1_900_000_000, revoked=[{"activation_id": "x"}])
    _wire(monkeypatch, crl)
    assert rt._fetch_revocation_list() is None


def test_fetch_rejects_dev_secret_forgery(monkeypatch) -> None:
    # The hardcoded, source-visible dev stub secret must NOT authorize a CRL (forgery guard).
    crl = _mk_crl_jwt(_DEV_SECRET, valid_until=1_900_000_000, revoked=[{"activation_id": "x"}])
    _wire(monkeypatch, crl)
    assert rt._fetch_revocation_list() is None


def test_fetch_rejects_expired_crl(monkeypatch) -> None:
    crl = _mk_crl_jwt(_CP_SECRET, valid_until=1, revoked=[{"activation_id": "x"}])  # past
    _wire(monkeypatch, crl)
    assert rt._fetch_revocation_list() is None


def test_fetch_fail_open_on_network_error(monkeypatch) -> None:
    _wire(monkeypatch, None, raise_exc=RuntimeError("egress denied"))
    assert rt._fetch_revocation_list() is None


def test_fetch_none_when_no_crl_field(monkeypatch) -> None:
    _wire(monkeypatch, None)  # response has no "crl"
    assert rt._fetch_revocation_list() is None


# ── load_license wiring: v2 revoked → invalid; v1 stays valid even if "listed" ─


def test_load_license_revokes_v2(monkeypatch) -> None:
    revoked_lic = _license(version=2, activation_id="act-REVOKED")
    monkeypatch.setattr(rt, "_load_raw_token", lambda *a, **k: "STORED")
    monkeypatch.setattr(rt, "_parse_token", lambda token, api_key="": revoked_lic)
    monkeypatch.setattr(rt, "_local_license_required", lambda: False)
    monkeypatch.setattr(
        rt, "_fetch_revocation_list", lambda: {"revoked": [{"activation_id": "act-REVOKED"}]}
    )
    result = rt.load_license("de_live_key")
    assert result.valid is False
    assert "revoked" in result.message.lower()


def test_load_license_v1_stays_valid_even_if_listed(monkeypatch) -> None:
    # A v1 license whose activation_id happens to be in the CRL is NOT revoked (dormant).
    v1 = _license(version=1, activation_id="act-REVOKED")
    monkeypatch.setattr(rt, "_load_raw_token", lambda *a, **k: "STORED")
    monkeypatch.setattr(rt, "_parse_token", lambda token, api_key="": v1)
    monkeypatch.setattr(rt, "_local_license_required", lambda: False)
    monkeypatch.setattr(
        rt, "_fetch_revocation_list", lambda: {"revoked": [{"activation_id": "act-REVOKED"}]}
    )
    result = rt.load_license("de_live_key")
    assert result.valid is True  # v1 dormant — never revoked pre-P5
