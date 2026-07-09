"""Hardware-backed device identity (TPM / Secure Enclave) — makes L1 node binding tamper-PROOF.

Coverage without hardware: the secp256r1 crypto path (thumbprint + ECDSA verify) with real software P-256
keys, hardware-backend selection + graceful fallback (a real-crypto fake store), and that node_broker's L1
binding works with a hardware secp256r1 identity. Plus a REAL Secure Enclave round-trip, gated to a macOS
host that actually has an Enclave + swiftc (runs on Apple Silicon, skipped on CI/Linux).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from apps.runtime import device_keypair as dk
from apps.runtime import hardware_key_store as hks
from apps.runtime import native_manifest

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


# ── prebuilt + signed helper resolution (no runtime swiftc) ─────────────────────────
def _rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub


def _write_signed_helper(d: Path, binary_bytes: bytes, priv, *, platform: str = "macos-arm64") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    binp = d / "algenta-se-helper"
    binp.write_bytes(binary_bytes)
    manifest = {
        "format_version": 1,
        "platform": platform,
        "artifacts": [
            {"name": "algenta-se-helper", "sha256": hashlib.sha256(binary_bytes).hexdigest(),
             "size_bytes": len(binary_bytes)},
        ],
    }
    mbytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (d / "manifest.json").write_bytes(mbytes)
    (d / "manifest.sig").write_bytes(priv.sign(mbytes, padding.PKCS1v15(), hashes.SHA256()))
    return binp


def test_native_manifest_verifies_and_fails_closed(tmp_path, monkeypatch) -> None:
    priv, pub = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", pub)
    d = tmp_path / "se"
    binp = _write_signed_helper(d, b"\x7fELF-ish-helper-bytes", priv)
    args = (str(binp), str(d / "manifest.json"), str(d / "manifest.sig"))

    native_manifest.verify_bundled_artifact(*args, expected_name="algenta-se-helper")  # valid → no raise

    binp.write_bytes(b"\x7fELF-ish-helper-bytes-TAMPERED")  # integrity break
    with pytest.raises(native_manifest.NativeVerificationError, match="integrity"):
        native_manifest.verify_bundled_artifact(*args, expected_name="algenta-se-helper")

    _write_signed_helper(d, b"\x7fELF-ish-helper-bytes", priv)  # restore
    other_priv, other_pub = _rsa_keypair()  # wrong trust anchor
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", other_pub)
    with pytest.raises(native_manifest.NativeVerificationError, match="signature"):
        native_manifest.verify_bundled_artifact(*args, expected_name="algenta-se-helper")


def test_se_resolves_verified_prebuilt_not_jit(tmp_path, monkeypatch) -> None:
    priv, pub = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", pub)
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_SE_ALLOW_JIT", raising=False)
    d = tmp_path / "se"
    _write_signed_helper(d, b"prebuilt-helper", priv)
    store = hks.SecureEnclaveKeyStore()
    monkeypatch.setattr(store, "_repo_se_dir", lambda: d)
    monkeypatch.setattr(store, "_sidecar_se_dir", lambda: None)

    resolved = store._resolve()
    assert resolved is not None and resolved[1] == "repo"  # the VERIFIED prebuilt binary, not jit-dev


def test_se_tampered_bundle_fails_closed_no_jit_fallback(tmp_path, monkeypatch) -> None:
    priv, pub = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", pub)
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_SE_ALLOW_JIT", raising=False)
    d = tmp_path / "se"
    binp = _write_signed_helper(d, b"prebuilt-helper", priv)
    binp.write_bytes(b"prebuilt-helper-TAMPERED")  # tamper after signing
    store = hks.SecureEnclaveKeyStore()
    monkeypatch.setattr(store, "_repo_se_dir", lambda: d)
    monkeypatch.setattr(store, "_sidecar_se_dir", lambda: None)

    assert store._resolve() is None  # refused (fail-closed) AND no runtime-swiftc fallback


def test_se_dev_jit_gated_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_SE_ALLOW_JIT", raising=False)
    monkeypatch.delenv("ALGENTA_SE_HELPER", raising=False)
    store = hks.SecureEnclaveKeyStore()
    monkeypatch.setattr(store, "_repo_se_dir", lambda: None)
    monkeypatch.setattr(store, "_sidecar_se_dir", lambda: None)
    assert store._resolve() is None  # release: no bundle + no runtime compiler ⇒ SE simply unavailable
    assert hks._dev_jit_allowed() is False


def test_se_env_override(tmp_path, monkeypatch) -> None:
    p = tmp_path / "myhelper"
    p.write_text("x")
    monkeypatch.setenv("ALGENTA_SE_HELPER", str(p))
    store = hks.SecureEnclaveKeyStore()
    assert store._resolve() == (str(p), "env")


# ── a stray Developer ID identity without a cert must NOT break the build (falls back to ad-hoc) ──
@pytest.mark.skipif(sys.platform != "darwin", reason="codesign is macOS-only")
def test_build_se_helper_falls_back_to_adhoc_on_bad_identity(tmp_path) -> None:
    if hks._swiftc() is None:
        pytest.skip("swiftc not available to build the helper")
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keyfile = tmp_path / "k.pem"
    keyfile.write_bytes(priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    env = {**__import__("os").environ, "ALGENTA_SE_CODESIGN_IDENTITY": "Developer ID Application: nope (ZZZZ)"}
    out = tmp_path / "se"
    res = subprocess.run(
        [sys.executable, "scripts/build_se_helper.py", "--out", str(out), "--key", str(keyfile),
         "--platform", "macos-test"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, env=env,
    )
    assert res.returncode == 0, res.stderr  # a missing Developer ID cert must fall back to ad-hoc, not abort
    assert (out / "algenta-se-helper").exists()
    assert (out / "manifest.sig").exists()


# ── REAL Secure Enclave through the VERIFIED PREBUILT helper (macOS, no runtime swiftc) ──
@pytest.mark.skipif(sys.platform != "darwin", reason="Secure Enclave is macOS-only")
def test_real_secure_enclave_via_prebuilt_signed_helper(tmp_path, monkeypatch) -> None:
    if hks._swiftc() is None:
        pytest.skip("swiftc not available to build the helper")
    # build + RS256-sign the helper with a test release key via the actual release script
    priv, pub = _rsa_keypair()
    keyfile = tmp_path / "release_priv.pem"
    keyfile.write_bytes(priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    se_dir = tmp_path / "se"
    build = subprocess.run(
        [sys.executable, "scripts/build_se_helper.py", "--out", str(se_dir),
         "--key", str(keyfile), "--platform", "macos-test"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stderr

    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", pub)
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))  # Enclave blob location
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_SE_ALLOW_JIT", raising=False)  # prove JIT is NOT what's used
    store = hks.SecureEnclaveKeyStore()
    monkeypatch.setattr(store, "_repo_se_dir", lambda: se_dir)
    monkeypatch.setattr(store, "_sidecar_se_dir", lambda: None)

    if not store.available():
        pytest.skip("no Secure Enclave on this host")
    assert store.source() == "repo"  # ran the VERIFIED PREBUILT helper, not a runtime compile

    pem = store.public_pem()
    assert dk.thumbprint_for_public_pem(pem).startswith("secp256r1:")
    sig = store.sign(b"hello-enclave")  # signed INSIDE the Enclave via the prebuilt helper
    assert dk.verify_signature(pem, b"hello-enclave", sig) is True
    assert dk.verify_signature(pem, b"tampered", sig) is False
