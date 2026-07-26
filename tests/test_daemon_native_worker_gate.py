"""Native-daemon-only verification gate (apps/runtime/daemon.py).

When ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER=1, the daemon refuses to boot unless the resolved
native worker is the verified/signed binary — so license enforcement can't be run in a patched
Python-only process. Default OFF preserves self-host/dev.
"""
from __future__ import annotations

import pytest

from apps.runtime import daemon


def test_gate_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", raising=False)
    assert daemon._require_verified_native_worker() is False


def test_gate_on_when_flag_set(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", "1")
    assert daemon._require_verified_native_worker() is True


def test_fails_closed_when_unverified(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", "1")
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", False)
    with pytest.raises(RuntimeError, match="unverified"):
        daemon._validate_daemon_startup_prerequisites()


def test_passes_gate_when_verified_and_not_enforcing(monkeypatch) -> None:
    # flag on + verified worker + license enforcement dark → gate passes, function returns cleanly
    monkeypatch.setenv("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", "1")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", True)
    daemon._validate_daemon_startup_prerequisites()  # no raise


def test_gate_absent_when_flag_off_even_if_unverified(monkeypatch) -> None:
    # default self-host/dev: unverified worker is fine when the flag is off
    monkeypatch.delenv("ALGENTA_REQUIRE_VERIFIED_NATIVE_WORKER", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)
    monkeypatch.setattr(daemon, "_MOJO_BINARY_VERIFIED", False)
    daemon._validate_daemon_startup_prerequisites()  # no raise (enforcement dark)
