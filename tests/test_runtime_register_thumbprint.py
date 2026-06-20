"""Runtime register body carries the device-key thumbprint (P3b-3).

Completes the binding loop: the runtime presents its Ed25519 public-key thumbprint on
/v1/device/register (which the server binds, P3b-2). Guarded — a keypair/store failure
degrades to an unbound (legacy) registration rather than breaking login.
"""

from __future__ import annotations

import json

from apps.runtime import license as rt_license


def test_register_body_includes_device_pubkey_thumbprint(monkeypatch) -> None:
    monkeypatch.setattr(rt_license, "_device_pubkey_thumbprint", lambda: "ed25519:TESTTHUMB")
    body = rt_license._device_register_body(
        {
            "device_id": "dev-1234567890ab",
            "platform": "linux",
            "platform_version": "6.8",
            "hostname_hash": "h" * 16,
            "sdk_version": "algenta/1.0.0",
        }
    )
    payload = json.loads(body)
    device = payload["device"]
    assert device["device_pubkey_thumbprint"] == "ed25519:TESTTHUMB"
    # existing fields still present (back-compat shape)
    assert device["device_id"] == "dev-1234567890ab"
    assert device["hostname_hash"] == "h" * 16


def test_register_body_thumbprint_empty_when_keypair_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(rt_license, "_device_pubkey_thumbprint", lambda: "")
    body = rt_license._device_register_body({"device_id": "dev-1234567890ab"})
    assert json.loads(body)["device"]["device_pubkey_thumbprint"] == ""


def test_thumbprint_helper_returns_keypair_value(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "file")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    from apps.runtime import device_keypair

    device_keypair.reset_device_keypair()
    try:
        thumb = rt_license._device_pubkey_thumbprint()
        assert thumb.startswith("ed25519:")
        assert thumb == device_keypair.public_key_thumbprint()  # stable
    finally:
        device_keypair.reset_device_keypair()


def test_thumbprint_helper_guards_failure(monkeypatch) -> None:
    # Force the keypair module import path to raise → helper returns "" (unbound fallback).
    import apps.runtime.device_keypair as dk

    def _boom() -> str:
        raise RuntimeError("keystore unavailable")

    monkeypatch.setattr(dk, "public_key_thumbprint", _boom)
    assert rt_license._device_pubkey_thumbprint() == ""
