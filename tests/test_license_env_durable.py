"""Durable license loading — the offline license JWT can come from a platform secret (env),
not only the ephemeral ~/.algenta/runtime/license.jwt file.

This is what makes an air-gapped / hosted engine survive Fly/Cloudflare redeploys: the file is
wiped when the machine/image is replaced, but a secret-backed env var persists. The local file
still takes precedence so existing deployments are unaffected.
"""

from __future__ import annotations

import apps.runtime.license as lic


def test_file_takes_precedence_over_env(tmp_path, monkeypatch) -> None:
    (tmp_path / "license.jwt").write_text("file-token\n")
    monkeypatch.setenv("ALGENTA_LICENSE_JWT", "env-token")
    assert lic._load_raw_token(tmp_path) == "file-token"


def test_env_fallback_when_no_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_JWT", "env-token")
    assert lic._load_raw_token(tmp_path) == "env-token"  # empty dir → env used


def test_legacy_env_name_also_works(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_LICENSE_JWT", raising=False)
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE", "env-token-2")
    assert lic._load_raw_token(tmp_path) == "env-token-2"


def test_env_file_fallback(tmp_path, monkeypatch) -> None:
    token_file = tmp_path / "lic.jwt"
    token_file.write_text("filevar-token\n")
    for name in ("ALGENTA_LICENSE_JWT", "ALGENTA_LOCAL_LICENSE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALGENTA_LICENSE_JWT_FILE", str(token_file))
    rt = tmp_path / "rt"
    rt.mkdir()
    assert lic._load_raw_token(rt) == "filevar-token"


def test_none_when_nothing_set(tmp_path, monkeypatch) -> None:
    for name in (
        "ALGENTA_LICENSE_JWT",
        "ALGENTA_LOCAL_LICENSE",
        "ALGENTA_LICENSE_JWT_FILE",
        "ALGENTA_LOCAL_LICENSE_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    rt = tmp_path / "rt"
    rt.mkdir()
    assert lic._load_raw_token(rt) is None
