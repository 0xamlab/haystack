"""Contract tests for `algenta runtime doctor`'s live execution gate.

The shipped 1.0.8/1.0.9 wheels failed out-of-the-box on plain Ubuntu 22.04 servers while
doctor still reported READY: the static checks (artifact present + signature verified) pass
even when the embedded interpreter cannot execute (a libpython ABI mismatch kills the worker
inside `import socket`, before it binds). Doctor's final gate is therefore a LIVE round trip
through the same path as `algenta runtime execute`; when it fails, doctor must NOT report
READY — it names the failure and the remedy instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ALGENTA_PKG = Path(__file__).resolve().parents[1] / "packages" / "algenta"
if str(_ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(_ALGENTA_PKG))

import algenta  # noqa: E402
from algenta.native import doctor, loader  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_doctor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("ALGENTA_HOME", str(tmp_path))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "deny")
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.null.Keyring")
    loader._LIB = None
    loader._LIB_PATH = None
    loader._LIB_SOURCE = None
    loader._HANDLE = None
    yield
    loader._LIB = None
    loader._LIB_PATH = None
    loader._LIB_SOURCE = None
    loader._HANDLE = None


def _healthy_static_info() -> dict:
    return {
        "runtime_source": "bundled runtime",
        "path": "/tmp/runtime/algenta-runtime-worker",
        "platform_tag": "linux-x86_64",
        "package_version": algenta.__version__,
        "abi_version_expected": loader.ABI_VERSION,
        "abi_version_native": "worker",
        "loaded": True,
        "verified": True,
        "mode": "bundled worker",
        "fallback": "deny",
        "tcp_listeners": [],
        "python": sys.version.split()[0],
        "error": None,
    }


class _FakeMojoRuntime:
    """Stands in for algenta.MojoRuntime and records the doctor's round-trip request."""

    def __init__(self, envelope: dict) -> None:
        self._envelope = envelope
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, *, mode: str = "local", **kwargs) -> _FakeMojoRuntime:
        assert mode == "local"
        return self

    def execute(self, module: str, function: str, args=None, *, timeout=None) -> dict:
        self.calls.append((module, function, args))
        return self._envelope


def _install_fake_runtime(monkeypatch: pytest.MonkeyPatch, envelope: dict) -> _FakeMojoRuntime:
    fake = _FakeMojoRuntime(envelope)
    monkeypatch.setattr(algenta, "MojoRuntime", fake, raising=False)
    return fake


def test_doctor_ready_when_round_trip_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(loader, "info", _healthy_static_info)
    fake = _install_fake_runtime(
        monkeypatch, {"result": 13.0, "engine_used": "mojo", "success": True}
    )

    rc = doctor.run()

    out = capsys.readouterr().out.lower()
    assert rc == 0
    assert "execution check: ok" in out
    assert "status:          ready" in out
    # The gate exercises the exact public execute path with the standard 64-element fixture.
    (module, function, args), = fake.calls
    assert (module, function) == ("vector_kernels.dot", "dot64_f32")
    assert len(args["a"]) == 64 and len(args["b"]) == 64
    assert args["a"][:3] == [1.0, 2.0, 3.0] and args["b"][:3] == [3.0, 2.0, 2.0]


def test_doctor_not_ready_when_round_trip_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # The Ubuntu defect shape: every static check passes, but the worker dies inside the
    # embedded interpreter, so execute returns the fail-closed envelope. Doctor must NOT say
    # READY — it names the failure and points at the distro libpython remedy.
    monkeypatch.setattr(loader, "info", _healthy_static_info)
    _install_fake_runtime(
        monkeypatch,
        {
            "result": None,
            "engine_used": "none",
            "success": False,
            "error": "The bundled Algenta runtime could not execute.",
            "error_code": "compute_runtime_unavailable",
        },
    )

    rc = doctor.run()

    out = capsys.readouterr().out.lower()
    assert rc == 1
    assert "status:          ready" not in out
    assert "status:          not ready (execution check failed)" in out
    assert "execution check: failed" in out
    assert "could not execute" in out
    assert "libpython3.14" in out  # the remedy names the missing system package
    for forbidden in ("mojo", "modular", "docker run", "command not found"):
        assert forbidden not in out, f"doctor leaked {forbidden!r}"


def test_doctor_round_trip_rejects_wrong_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # success=True with a wrong value is still a broken runtime — the gate checks the number.
    monkeypatch.setattr(loader, "info", _healthy_static_info)
    _install_fake_runtime(
        monkeypatch, {"result": 12.0, "engine_used": "mojo", "success": True}
    )

    rc = doctor.run()

    out = capsys.readouterr().out
    assert rc == 1
    assert "execution check: FAILED" in out
    assert "status:          NOT READY (execution check failed)" in out


def test_doctor_skips_round_trip_when_static_checks_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    info = _healthy_static_info()
    info["loaded"] = False
    monkeypatch.setattr(loader, "info", lambda: info)

    def _explode(**kwargs):
        raise AssertionError("round trip must not run when the static phase already failed")

    monkeypatch.setattr(algenta, "MojoRuntime", _explode, raising=False)

    rc = doctor.run()

    out = capsys.readouterr().out
    assert rc == 1
    assert "status:          NOT READY" in out
    assert "execution check" not in out


def test_doctor_round_trip_reports_exceptions_as_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(loader, "info", _healthy_static_info)

    def _explode(**kwargs):
        raise OSError("simulated worker startup death")

    monkeypatch.setattr(algenta, "MojoRuntime", _explode, raising=False)

    rc = doctor.run()

    out = capsys.readouterr().out
    assert rc == 1
    assert "execution check: FAILED" in out
    assert "simulated worker startup death" in out
    assert "status:          NOT READY (execution check failed)" in out
