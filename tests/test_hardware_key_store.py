"""Hardware-backed device identity (TPM / Secure Enclave) — makes L1 node binding tamper-PROOF.

Coverage without hardware: the secp256r1 crypto path (thumbprint + ECDSA verify) with real software P-256
keys, hardware-backend selection + graceful fallback (a real-crypto fake store), and that node_broker's L1
binding works with a hardware secp256r1 identity. Plus a REAL Secure Enclave round-trip, gated to a macOS
host that actually has an Enclave + swiftc (runs on Apple Silicon, skipped on CI/Linux).
"""
from __future__ import annotations

import sys

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from apps.runtime import device_keypair as dk
from apps.runtime import hardware_key_store as hks


def _pem(pub) -> str:  # noqa: ANN001
    return pub.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


class _FakeHwStore:
    """A HardwareKeyStore backed by a real software P-256 key — same crypto a TPM/Enclave produces."""

    algorithm = "secp256r1"

    def __init__(self, *, avail: bool = True) -> None:
        self._avail = avail
        self._key = ec.generate_private_key(ec.SECP256R1())

    def available(self) -> bool:
        return self._avail

    def public_pem(self) -> str:
        return _pem(self._key.public_key())

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data, ec.ECDSA(hashes.SHA256()))

    def reset(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    hks.reset_hardware_key_stores_for_test()
    yield
    hks.reset_hardware_key_stores_for_test()


# ── algorithm-agnostic crypto path (real crypto, no hardware) ───────────────────────
def test_p256_thumbprint_prefix_and_verify() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    pem = _pem(key.public_key())
    tp = dk.thumbprint_for_public_pem(pem)
    assert tp is not None and tp.startswith("secp256r1:")
    sig = key.sign(b"nonce", ec.ECDSA(hashes.SHA256()))
    assert dk.verify_signature(pem, b"nonce", sig) is True
    assert dk.verify_signature(pem, b"tampered", sig) is False


def test_ed25519_path_still_works() -> None:
    key = Ed25519PrivateKey.generate()
    pem = _pem(key.public_key())
    tp = dk.thumbprint_for_public_pem(pem)
    assert tp is not None and tp.startswith("ed25519:")
    assert dk.verify_signature(pem, b"x", key.sign(b"x")) is True


def test_thumbprints_are_stable_and_distinct_by_algorithm() -> None:
    ecp = _pem(ec.generate_private_key(ec.SECP256R1()).public_key())
    edp = _pem(Ed25519PrivateKey.generate().public_key())
    assert dk.thumbprint_for_public_pem(ecp) == dk.thumbprint_for_public_pem(ecp)  # deterministic
    assert dk.thumbprint_for_public_pem(ecp) != dk.thumbprint_for_public_pem(edp)


def test_unsupported_curve_rejected() -> None:
    # only secp256r1 hardware keys are accepted (Secure Enclave / TPM shape); P-384 is not an identity
    p384 = _pem(ec.generate_private_key(ec.SECP384R1()).public_key())
    assert dk.thumbprint_for_public_pem(p384) is None
    assert dk.verify_signature(p384, b"x", b"badsig") is False


# ── backend selection + graceful fallback ───────────────────────────────────────────
def test_hardware_backend_selected_and_signs(monkeypatch) -> None:
    fake = _FakeHwStore(avail=True)
    monkeypatch.setattr(hks, "get_hardware_key_store", lambda mode: fake)
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "secure_enclave")

    tp = dk.public_key_thumbprint()
    assert tp.startswith("secp256r1:")
    assert dk.thumbprint_for_public_pem(dk.device_public_key_pem()) == tp  # pem ↔ thumbprint agree
    assert dk.active_key_store() == "secure_enclave"
    # sign in "hardware", verify from the exported public pem
    sig = dk.sign(b"renewal-nonce")
    assert dk.verify_signature(dk.device_public_key_pem(), b"renewal-nonce", sig) is True
    assert dk.verify_signature(dk.device_public_key_pem(), b"forged", sig) is False


def test_hardware_unavailable_degrades_to_software(monkeypatch) -> None:
    fake = _FakeHwStore(avail=False)  # requested but not available on this host
    monkeypatch.setattr(hks, "get_hardware_key_store", lambda mode: fake)
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "secure_enclave")

    tp = dk.public_key_thumbprint()
    assert tp.startswith("ed25519:")  # degraded to the software key (differs → fails a hw-bound license closed)
    assert dk.active_key_store() in ("file", "keyring")
    sig = dk.sign(b"x")  # software sign still works
    assert dk.verify_signature(dk.device_public_key_pem(), b"x", sig) is True


def test_auto_never_silently_picks_hardware(monkeypatch) -> None:
    # a device's thumbprint must be stable — auto stays software even if hardware exists
    monkeypatch.setattr(hks, "get_hardware_key_store", lambda mode: _FakeHwStore(avail=True))
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "auto")
    assert dk.public_key_thumbprint().startswith("ed25519:")


# ── L1 node binding with a hardware identity (ties L3 → L1) ──────────────────────────
class _Lic:
    def __init__(self, *, node_limit: int, thumbprint: str) -> None:
        self._nl = node_limit
        self.device_pubkey_thumbprint = thumbprint

    def node_limit(self) -> int:
        return self._nl


def test_node_binding_enforced_with_hardware_thumbprint(monkeypatch) -> None:
    from apps.runtime import node_broker

    fake = _FakeHwStore(avail=True)
    monkeypatch.setattr(hks, "get_hardware_key_store", lambda mode: fake)
    monkeypatch.setenv("ALGENTA_DEVICE_KEY_STORE", "secure_enclave")

    tp = dk.public_key_thumbprint()
    assert tp.startswith("secp256r1:")
    # a license bound to THIS hardware node boots; one bound to a different node fails closed
    node_broker.assert_node_binding(_Lic(node_limit=1, thumbprint=tp), enforcing=True)
    with pytest.raises(node_broker.NodeAdmissionError, match="not the licensed node"):
        node_broker.assert_node_binding(
            _Lic(node_limit=1, thumbprint="secp256r1:SOME-OTHER-NODE"), enforcing=True
        )


# ── TPM backend feature-detection ───────────────────────────────────────────────────
def test_tpm_unavailable_without_optin() -> None:
    store = hks.TpmKeyStore()
    assert store.available() is False  # opt-in (ALGENTA_TPM_ENABLE) + lib + TCTI required


# ── REAL Secure Enclave (macOS, Apple Silicon / T2 with swiftc) ─────────────────────
@pytest.mark.skipif(sys.platform != "darwin", reason="Secure Enclave is macOS-only")
def test_real_secure_enclave_roundtrip() -> None:
    store = hks.SecureEnclaveKeyStore()
    if not store.available():
        pytest.skip("no Secure Enclave / swiftc on this host")

    pem = store.public_pem()
    assert "BEGIN PUBLIC KEY" in pem
    assert dk.thumbprint_for_public_pem(pem).startswith("secp256r1:")

    sig = store.sign(b"hello-enclave")  # signed INSIDE the Secure Enclave (key never exported)
    assert dk.verify_signature(pem, b"hello-enclave", sig) is True
    assert dk.verify_signature(pem, b"tampered", sig) is False

    # the Enclave-bound blob persists: a fresh instance reloads the SAME key
    assert hks.SecureEnclaveKeyStore().public_pem() == pem
