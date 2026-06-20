"""Device keypair (P3b-1) — per-machine Ed25519 identity for activation binding.

Hermetic: forces the encrypted-file store (ALGENTA_DEVICE_KEY_STORE=file) in a tmp runtime
dir, so no OS keychain backend is needed (mirrors headless/CI). Covers generation +
persistence, a stable thumbprint, sign/verify proof-of-possession, machine-bound file
encryption, and rotation.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def kp(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "file")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    mod = importlib.import_module("apps.runtime.device_keypair")
    mod.reset_device_keypair()
    yield mod
    mod.reset_device_keypair()


def test_keypair_generated_and_persisted(kp) -> None:
    k1 = kp.ensure_device_keypair()
    # second call loads the SAME stored key (stable identity)
    k2 = kp.ensure_device_keypair()
    assert kp._private_pem(k1) == kp._private_pem(k2)
    assert kp._file_path().exists()


def test_thumbprint_is_stable_and_prefixed(kp) -> None:
    t1 = kp.public_key_thumbprint()
    t2 = kp.public_key_thumbprint()
    assert t1 == t2
    assert t1.startswith("ed25519:")
    # matches the server-side recompute from the public PEM
    assert kp.thumbprint_for_public_pem(kp.device_public_key_pem()) == t1


def test_sign_verify_round_trip(kp) -> None:
    nonce = b"server-challenge-nonce-123"
    sig = kp.sign(nonce)
    assert kp.verify_signature(kp.device_public_key_pem(), nonce, sig) is True
    # wrong payload fails
    assert kp.verify_signature(kp.device_public_key_pem(), b"tampered", sig) is False


def test_verify_rejects_foreign_key(kp) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    nonce = b"nonce"
    sig = kp.sign(nonce)
    foreign_pem = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    assert kp.verify_signature(foreign_pem, nonce, sig) is False


def test_verify_handles_garbage_pem(kp) -> None:
    assert kp.verify_signature("not a pem", b"x", b"y") is False
    assert kp.thumbprint_for_public_pem("not a pem") is None


def test_file_is_encrypted_not_plaintext(kp) -> None:
    kp.ensure_device_keypair()
    raw = kp._file_path().read_bytes()
    assert b"PRIVATE KEY" not in raw  # PEM header must not appear in the at-rest file
    assert b"BEGIN" not in raw


def test_copied_file_does_not_decrypt_on_other_machine(kp, monkeypatch) -> None:
    kp.ensure_device_keypair()
    blob = kp._file_path().read_bytes()
    # simulate the SAME file appearing on a different machine (different raw machine id)
    monkeypatch.setattr("apps.runtime.device._raw_machine_id", lambda: "a-different-machine-id")
    kp._file_path().write_bytes(blob)
    assert kp._file_load() is None  # machine-bound cipher rejects the foreign blob


def test_reset_regenerates_a_new_identity(kp) -> None:
    t1 = kp.public_key_thumbprint()
    kp.reset_device_keypair()
    assert not kp._file_path().exists()
    t2 = kp.public_key_thumbprint()  # generates a fresh keypair
    assert t1 != t2
