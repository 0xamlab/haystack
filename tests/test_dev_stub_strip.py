"""Production-wheel dev-secret strip (scripts/strip_dev_stub.py) + the stripped-runtime behavior.

The dev HS256 secret lives ONLY in apps/runtime/_dev_license_stub.py; the production build strips
that file so the artifact can't even contain the forgeable secret, and the runtime degrades to
RS256-only (no dev-stub token accepted) by construction.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import jwt

from apps.runtime import license as L
from scripts.strip_dev_stub import _DEV_SECRET_NEEDLE, strip_and_verify

_REPO = Path(__file__).resolve().parent.parent


def test_dev_stub_present_in_dev_checkout() -> None:
    # In a dev/test checkout the stub is present, so the dev secret is available (existing behavior).
    assert L._DEV_SECRET == _DEV_SECRET_NEEDLE


def test_strip_removes_stub_and_leaves_no_secret(tmp_path: Path) -> None:
    # Stage a minimal package tree with the stub + a file that (wrongly) also holds the needle.
    root = tmp_path / "pkg"
    (root / "apps" / "runtime").mkdir(parents=True)
    shutil.copy(_REPO / "apps" / "runtime" / "_dev_license_stub.py",
                root / "apps" / "runtime" / "_dev_license_stub.py")
    (root / "apps" / "runtime" / "license.py").write_text(
        "try:\n    from apps.runtime._dev_license_stub import DEV_SECRET as _DEV_SECRET\n"
        "except ImportError:\n    _DEV_SECRET = None\n"
    )
    offenders = strip_and_verify(root)
    assert offenders == []  # only the stub held it, and it's now deleted
    assert not (root / "apps" / "runtime" / "_dev_license_stub.py").exists()


def test_strip_flags_a_stray_secret_copy(tmp_path: Path) -> None:
    root = tmp_path / "pkg"
    (root / "apps" / "runtime").mkdir(parents=True)
    (root / "apps" / "runtime" / "_dev_license_stub.py").write_text(
        f'DEV_SECRET = "{_DEV_SECRET_NEEDLE}"\n'
    )
    # a stray copy of the needle elsewhere must be caught (build not hardened)
    (root / "apps" / "runtime" / "leaky.py").write_text(f'X = "{_DEV_SECRET_NEEDLE}"\n')
    offenders = strip_and_verify(root)
    assert offenders == ["apps/runtime/leaky.py"]


def test_strip_catches_secret_in_compiled_bytecode(tmp_path: Path) -> None:
    # The strip must scan compiled artifacts too — a .pyc embedding the secret is a false-green
    # if only *.py is grepped.
    root = tmp_path / "pkg"
    cache = root / "apps" / "runtime" / "__pycache__"
    cache.mkdir(parents=True)
    # a stray .pyc-like file NOT named _dev_license_stub.* (so it isn't auto-deleted) holding the needle
    (cache / "leaky.cpython-312.pyc").write_bytes(b"\x00\x01" + _DEV_SECRET_NEEDLE.encode() + b"\x00")
    offenders = strip_and_verify(root)
    assert offenders == ["apps/runtime/__pycache__/leaky.cpython-312.pyc"]


def test_strip_removes_compiled_stub_bytecode(tmp_path: Path) -> None:
    root = tmp_path / "pkg"
    cache = root / "apps" / "runtime" / "__pycache__"
    cache.mkdir(parents=True)
    (root / "apps" / "runtime" / "_dev_license_stub.py").write_text(
        f'DEV_SECRET = "{_DEV_SECRET_NEEDLE}"\n'
    )
    (cache / "_dev_license_stub.cpython-312.pyc").write_bytes(
        b"\x00" + _DEV_SECRET_NEEDLE.encode() + b"\x00"
    )
    # the stub's own compiled artifact is deleted, so no offender remains
    assert strip_and_verify(root) == []
    assert not (cache / "_dev_license_stub.cpython-312.pyc").exists()


def test_runtime_rejects_dev_hs256_when_stub_stripped(monkeypatch) -> None:
    # Simulate a production wheel (stub stripped → _DEV_SECRET is None): a dev-stub HS256 token is
    # rejected even with RS256-only mode OFF, because the secret literally isn't in the build.
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.setattr(L, "_DEV_SECRET", None)
    forged = jwt.encode(
        {"ver": 2, "plan": "enterprise", "device_id": "d", "sub": "device-license"},
        _DEV_SECRET_NEEDLE, algorithm="HS256",
    )
    assert L._parse_token(forged) is None


def test_dev_jwt_issuance_unavailable_when_stub_stripped(monkeypatch) -> None:
    monkeypatch.setattr(L, "_DEV_SECRET", None)
    import pytest

    with pytest.raises(RuntimeError, match="production build"):
        L._issue_dev_jwt("device-x")


def test_control_plane_hs256_still_works_when_stub_stripped(monkeypatch) -> None:
    # Stripping the DEV stub must not disturb the control-plane HS256 path (dev/internal), which is
    # a separate secret; only the dev-stub secret is removed.
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.setattr(L, "_DEV_SECRET", None)
    monkeypatch.setenv("JWT_SECRET", "seed-abc")
    import hashlib

    secret = hashlib.sha256(("seed-abc" + ":license-signing").encode()).hexdigest()
    tok = jwt.encode({"ver": 2, "plan": "pro", "device_id": "d", "sub": "device-license"},
                     secret, algorithm="HS256")
    lic = L._parse_token(tok)
    assert lic is not None and lic.valid  # control-plane HS256 unaffected by the dev-stub strip
