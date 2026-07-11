"""Runtime renewal client (P3b-C2) — renew_license() + load_license auto-renew wiring.

renew_license does challenge → sign(nonce) → renew over the egress wrapper and returns a
fresh token, or None on ANY failure (so the caller falls back to full re-register). load_license
prefers it on hard-expiry (dark: falls back to the expired message on failure).
"""

from __future__ import annotations

import base64
import json
import urllib.error

import pytest

from apps.runtime import license as rt
from apps.runtime.license import DeviceLicense


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a) -> bool:
        return False


@pytest.fixture()
def _keystore(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "file")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(rt, "_validated_control_plane_url", lambda **k: "https://cp.test")
    yield


def test_renew_license_happy_path(_keystore, monkeypatch) -> None:
    nonce_b64 = base64.b64encode(b"n" * 32).decode()

    def _fake_urlopen(req, surface=None, timeout=None):
        url = req.full_url
        if url.endswith("/v1/license/challenge"):
            return _Resp({"nonce": nonce_b64, "device_pubkey_thumbprint": "ed25519:x"})
        if url.endswith("/v1/license/renew"):
            # the renew request must carry the device pubkey + a base64 signature
            body = json.loads(req.data)
            assert body["public_key_pem"].startswith("-----BEGIN PUBLIC KEY")
            assert base64.b64decode(body["signature"])  # decodable
            return _Resp({"license_token": "fresh.jwt.token", "server_time": 1_900_000_000})
        raise AssertionError(url)

    monkeypatch.setattr(rt, "runtime_urlopen", _fake_urlopen)
    assert rt.renew_license("de_live_key") == "fresh.jwt.token"


def test_renew_license_none_without_device_id(_keystore, monkeypatch) -> None:
    monkeypatch.setattr(rt, "runtime_urlopen", lambda *a, **k: pytest.fail("should not call"))
    assert rt.renew_license("de_live_key", device_info={"device_id": ""}) is None


def test_renew_license_none_on_old_server_404(_keystore, monkeypatch) -> None:
    def _raise_404(req, surface=None, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(rt, "runtime_urlopen", _raise_404)
    assert rt.renew_license("de_live_key") is None  # falls back to register


def test_renew_license_none_when_challenge_has_no_nonce(_keystore, monkeypatch) -> None:
    monkeypatch.setattr(rt, "runtime_urlopen", lambda *a, **k: _Resp({"device_pubkey_thumbprint": "x"}))
    assert rt.renew_license("de_live_key") is None


# ── load_license auto-renew wiring ─────────────────────────────────────────────


def _lic(*, expires_at: int) -> DeviceLicense:
    return DeviceLicense(
        valid=True,
        plan="pro",
        device_id="dev-abc",
        device_limit=0,
        permitted_modules=["*"],
        expires_at=expires_at,
        key_expires_at=0,
        grace_days=0,
        api_key_prefix="ak",
        issued_at=1,
    )


def test_load_license_auto_renews_on_hard_expiry(monkeypatch) -> None:
    expired = _lic(expires_at=1)  # epoch 1 + 0 grace → hard expired
    fresh = _lic(expires_at=0)  # 0 = no expiry → valid
    monkeypatch.setattr(rt, "_load_raw_token", lambda *a, **k: "STORED")
    monkeypatch.setattr(rt, "_parse_token", lambda token, api_key="": expired if token == "STORED" else fresh)
    monkeypatch.setattr(rt, "_local_license_required", lambda: False)
    monkeypatch.setattr(rt, "renew_license", lambda api_key, device_info=None: "RENEWED")
    monkeypatch.setattr(rt, "_save_license", lambda token, runtime_dir=None: None)

    result = rt.load_license("de_live_key")
    assert result is fresh  # hard-expired → PoP-renewed without re-login


def test_load_license_expired_downgrades_to_community_when_renew_fails(monkeypatch) -> None:
    # NEW model: a lapsed paid license that can't renew DOWNGRADES to Community (free-forever) —
    # the engine keeps running at Community limits rather than hard-blocking.
    expired = _lic(expires_at=1)
    monkeypatch.setattr(rt, "_load_raw_token", lambda *a, **k: "STORED")
    monkeypatch.setattr(rt, "_parse_token", lambda token, api_key="": expired)
    monkeypatch.setattr(rt, "_local_license_required", lambda: False)
    monkeypatch.setattr(rt, "renew_license", lambda api_key, device_info=None: None)  # renew fails

    result = rt.load_license("de_live_key")
    assert result.valid is True  # engine keeps running — NOT hard-blocked
    assert result.plan == "algenta_free"  # downgraded to Community
    assert result.source == "community-fallback"
    assert result.concurrent_worker_limit == 1  # Community per-device worker cap
    assert result.commercial_use is False


def test_load_license_expired_hard_blocks_when_local_license_required(monkeypatch) -> None:
    # Enterprise air-gapped (a local signed license is REQUIRED) has no connected renewal path,
    # so a hard-expired license still hard-blocks — it does not silently downgrade.
    expired = _lic(expires_at=1)
    monkeypatch.setattr(rt, "_load_raw_token", lambda *a, **k: "STORED")
    monkeypatch.setattr(rt, "_parse_token", lambda token, api_key="": expired)
    monkeypatch.setattr(rt, "_local_license_required", lambda: True)

    result = rt.load_license("de_live_key")
    assert result.valid is False
    assert "expired" in result.message.lower()
