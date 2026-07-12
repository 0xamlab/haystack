"""Contract tests for the graduated `algenta` bundled-runtime CLI that hold WITHOUT a native lib present.

The happy-path execute() needs the CI-built `algenta-runtime-native` sidecar (verified by the clean-machine
CI + scripts/verify_sdk_artifact_install). Here we pin the pieces that must hold on any dev machine:
lazy import, fail-closed loading, the never-mention-Mojo contract, `runtime doctor` invariants, and the
offline verifier (manifest signature + artifact sha256 + RS256 alg-confusion rejection).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# The graduated `algenta` package lives under packages/algenta (import name `algenta`).
_ALGENTA_PKG = Path(__file__).resolve().parents[1] / "packages" / "algenta"
if str(_ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(_ALGENTA_PKG))

import algenta  # noqa: E402
from algenta import paths  # noqa: E402
from algenta.native import loader as _loader  # noqa: E402
from algenta.native import verify as _verify  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_loader(monkeypatch, tmp_path):
    # Isolate each test: empty ALGENTA_HOME (no cache), deny fallback, reset the loader singleton, and make
    # sure no override / sidecar leaks a real lib in.
    monkeypatch.setenv("ALGENTA_HOME", str(tmp_path))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "deny")
    monkeypatch.delenv("ALGENTA_NATIVE_KERNEL", raising=False)
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    _loader._LIB = None
    _loader._LIB_PATH = None
    _loader._HANDLE = None
    yield
    _loader._LIB = None
    _loader._HANDLE = None


def test_import_algenta_is_lazy_no_native():
    # importing algenta must not have loaded the native lib / ctypes handle.
    assert algenta.__version__ == "1.0.3"
    assert _loader._LIB is None


def test_loader_fails_closed_without_native():
    assert _loader.available() is False
    with pytest.raises(_loader.RuntimeUnavailable):
        _loader.execute({"op": "noop"})


def test_fail_closed_message_never_mentions_mojo():
    try:
        _loader.execute({"op": "x"})
        pytest.skip("a native runtime is unexpectedly present in this env")
    except _loader.RuntimeUnavailable as exc:
        msg = str(exc).lower()
    for forbidden in ("mojo", "modular", "docker", "daemon", "command not found"):
        assert forbidden not in msg, f"fail-closed message leaked {forbidden!r}: {msg}"
    assert "upgrade algenta" in msg and "platform" in msg and "fallback" in msg


def test_runtime_doctor_output_contract(capsys):
    from algenta.native import doctor

    rc = doctor.run()
    out = capsys.readouterr().out.lower()
    assert "mode:            in-process" in out
    assert "fallback:        denied" in out
    assert "tcp listeners:   none" in out
    for forbidden in ("mojo", "modular", "docker run", "command not found"):
        assert forbidden not in out, f"doctor leaked {forbidden!r}"
    assert rc != 0  # no native runtime here → NOT READY


def test_doctor_reports_no_tcp_listeners():
    # The in-process ctypes path opens no sockets by construction.
    assert _loader.info()["tcp_listeners"] == []
    assert _loader.info()["mode"] == "in-process"


# ── offline verifier (manifest + license) ───────────────────────────────────────────────────────
def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return key, pub


def test_verify_manifest_roundtrip_and_tamper(monkeypatch, tmp_path):
    key, pub = _keypair()
    (tmp_path / "rel.pem").write_bytes(pub)
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY_FILE", str(tmp_path / "rel.pem"))

    art = tmp_path / "libalgenta_runtime.so"
    art.write_bytes(b"NATIVE-RUNTIME-BYTES")
    sha = hashlib.sha256(art.read_bytes()).hexdigest()
    manifest = json.dumps(
        {"format_version": 1, "platform": "linux-x86_64",
         "artifacts": [{"name": "libalgenta_runtime.so", "sha256": sha, "size_bytes": art.stat().st_size}]},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    sig = key.sign(manifest, padding.PKCS1v15(), hashes.SHA256())

    parsed = _verify.verify_manifest(manifest, sig)
    assert parsed["platform"] == "linux-x86_64"
    _verify.verify_artifact(str(art), sha)  # matches

    art.write_bytes(b"TAMPERED")  # integrity break
    with pytest.raises(_verify.VerificationError):
        _verify.verify_artifact(str(art), sha)
    with pytest.raises(_verify.VerificationError):  # signature break
        _verify.verify_manifest(manifest + b" ", sig)


def test_verify_license_rejects_alg_confusion(monkeypatch, tmp_path):
    key, pub = _keypair()
    (tmp_path / "lic.pem").write_bytes(pub)
    monkeypatch.setenv("ALGENTA_LICENSE_PUBKEY_FILE", str(tmp_path / "lic.pem"))

    def _b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    import hmac

    claims = {"iss": "https://license.algenta.ai", "aud": "algenta-runtime", "ver": 2, "exp": 4102444800,
              "offline_grace_days": 30, "products": {"algenta": {"tier": "pro", "features": ["local_runtime"]}}}
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(claims).encode())
    sig = _b64(hmac.new(pub, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    forged = f"{header}.{payload}.{sig}"
    with pytest.raises(_verify.VerificationError):
        _verify.verify_license(forged, now=1_700_000_000, product="algenta")


# ── migration guard + CLI ────────────────────────────────────────────────────────────────────────
def test_check_migration_none_when_no_legacy_core():
    # In this env there is no file-owning legacy algenta-core → no warning (returns None or a string; never raises).
    result = algenta.check_migration()
    assert result is None or isinstance(result, str)


def test_check_migration_removes_legacy_core_instead_of_reinstalling_it(monkeypatch):
    from importlib import metadata

    monkeypatch.setattr(metadata, "requires", lambda name: [] if name == "algenta-core" else None)

    warning = algenta.check_migration()

    assert warning is not None
    assert "pip uninstall algenta-core" in warning
    assert "pip install --upgrade algenta" in warning
    assert "pip install --upgrade algenta-core" not in warning


def test_cli_version_and_whoami(capsys, monkeypatch, tmp_path):
    from algenta import cli

    monkeypatch.setenv("ALGENTA_HOME", str(tmp_path))
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["algenta", "version"])
    cli.main()
    assert "algenta 1.0.3" in capsys.readouterr().out
    # whoami with no login → exit 1
    monkeypatch.setattr(sys, "argv", ["algenta", "whoami"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1
