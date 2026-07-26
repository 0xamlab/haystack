"""Offline server-license issuance guards (scripts/issue_offline_license.py --paid-selfhost).

Exercises the CLI end to end via subprocess: a deployment-scope paid mint must have a finite
expiry (no perpetual "pay once and leave") and a finite Compute-Unit ceiling; a well-formed one
succeeds and round-trips through the runtime as a deployment license.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "issue_offline_license.py"


def _write_keypair(tmp_path: Path) -> tuple[Path, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = tmp_path / "priv.pem"
    priv.write_text(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ).decode()
    )
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args], capture_output=True, text=True, cwd=str(_REPO)
    )


def test_paid_deployment_mint_requires_finite_expiry(tmp_path: Path) -> None:
    priv, _ = _write_keypair(tmp_path)
    out = tmp_path / "lic.jwt"
    r = _run([
        "--device-id", "d", "--plan", "algenta_server", "--output", str(out),
        "--private-key-file", str(priv), "--org-id", "o",
        "--license-scope", "deployment", "--max-concurrent-units", "16",
        "--commercial-use", "--expires-at", "0", "--paid-selfhost",
    ])
    assert r.returncode != 0
    assert "expires-at" in (r.stderr + r.stdout)
    assert not out.exists()


def test_paid_deployment_mint_requires_unit_ceiling(tmp_path: Path) -> None:
    priv, _ = _write_keypair(tmp_path)
    out = tmp_path / "lic.jwt"
    r = _run([
        "--device-id", "d", "--plan", "algenta_server", "--output", str(out),
        "--private-key-file", str(priv), "--org-id", "o",
        "--license-scope", "deployment", "--commercial-use",
        "--expires-at", "9999999999", "--paid-selfhost",
    ])
    assert r.returncode != 0
    assert "Compute-Unit ceiling" in (r.stderr + r.stdout)


def test_wellformed_paid_deployment_mint_succeeds_and_roundtrips(tmp_path: Path) -> None:
    priv, pub = _write_keypair(tmp_path)
    out = tmp_path / "lic.jwt"
    r = _run([
        "--device-id", "deployment-node", "--plan", "algenta_server", "--output", str(out),
        "--private-key-file", str(priv), "--org-id", "org-acme",
        "--license-scope", "deployment", "--deployment-id", "prod-us",
        "--max-concurrent-units", "64", "--vcpu-per-unit", "4",
        "--commercial-use", "--offline-grace-days", "30",
        "--expires-at", "9999999999", "--paid-selfhost",
    ])
    assert r.returncode == 0, r.stderr
    assert out.exists()

    # round-trip through the runtime parser as a deployment-scope license
    import os

    from apps.runtime import license as L

    prev = os.environ.get("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY")
    os.environ["ALGENTA_LOCAL_LICENSE_PUBLIC_KEY"] = pub
    try:
        lic = L._parse_token(out.read_text().strip())
    finally:
        if prev is None:
            os.environ.pop("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", None)
        else:
            os.environ["ALGENTA_LOCAL_LICENSE_PUBLIC_KEY"] = prev
    assert lic is not None and lic.valid
    assert lic.is_deployment_scope()
    assert lic.max_concurrent_units == 64
