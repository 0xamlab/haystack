# ruff: noqa: T201
"""`algenta runtime doctor` — the required diagnostic.

Prints runtime diagnostics, license state, fallback policy, and listener status,
returns a non-zero exit code if the bundled in-process runtime isn't healthy. It never mentions
internal implementation names. This is also the target of the clean-machine CI contract, which
greps this output for the invariant lines.

The static checks (artifact present, signature verified, ABI handshake) are only the first
phase. The final gate is a LIVE round trip: one real kernel executed through the bundled
worker. Static readiness cannot see a libpython ABI mismatch, which kills the worker inside
the embedded interpreter at the first extension import — the runtime then reports ready and
fails every execution. When the round trip fails, doctor names the failure and the remedy
instead of reporting READY.
"""
from __future__ import annotations

import sys
import time

from algenta import auth
from algenta.native import loader

# The live gate runs the same kernel + fixed-offset SIMD fixture the release pipeline's
# clean-machine contract executes: dot64_f32's contract is EXACTLY 64 elements (short lists
# return the 0.0 sentinel), so the vectors must be full-length. 1*3 + 2*2 + 3*2 = 13.0,
# exact in Float32.
_DOT64_A = [1.0, 2.0, 3.0] + [0.0] * 61
_DOT64_B = [3.0, 2.0, 2.0] + [0.0] * 61
_DOT64_EXPECTED = 13.0
_ROUND_TRIP_TIMEOUT_SECONDS = 30.0


def _license_state() -> str:
    try:
        token = auth.read_license()
    except auth.CredentialStoreError as exc:
        return f"credential store unavailable ({exc})"
    if not token:
        return "not present (run `algenta login`)"
    try:
        from algenta.runtime import verify

        claims = verify.verify_license(token, now=int(time.time()))
        prod = (claims.get("products") or {}).get("algenta", {})
        return f"valid (tier={prod.get('tier')}, exp={claims.get('exp')})"
    except Exception as exc:  # noqa: BLE001 — VerificationError, missing pubkey, unreadable token
        return f"present but NOT verified ({str(exc).splitlines()[0]})"


def _live_round_trip() -> tuple[bool, str]:
    """Execute one real kernel through the bundled runtime. Returns ``(ok, detail)``.

    Uses the same public path as ``algenta runtime execute``, so the gate proves exactly
    what a user's first workload will hit. Never raises.
    """
    try:
        from algenta import MojoRuntime

        envelope = MojoRuntime(mode="local").execute(
            "vector_kernels.dot",
            "dot64_f32",
            {"a": _DOT64_A, "b": _DOT64_B},
            timeout=_ROUND_TRIP_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — doctor must report, never raise
        return False, f"execution attempt raised {type(exc).__name__}: {exc}"
    if not isinstance(envelope, dict):
        return False, "execution returned no result envelope"
    if envelope.get("success") is True and envelope.get("result") == _DOT64_EXPECTED:
        return True, f"vector_kernels.dot dot64_f32 -> {_DOT64_EXPECTED}"
    detail = str(envelope.get("error") or "").strip()
    if not detail:
        detail = (
            f"expected success with result {_DOT64_EXPECTED}, "
            f"got result {envelope.get('result')!r}"
        )
    return False, detail.splitlines()[0]


def run(_argv: list[str] | None = None) -> int:
    info = loader.info()
    fallback = "denied" if info["fallback"] == "deny" else info["fallback"]
    tcp = "none" if not info["tcp_listeners"] else ", ".join(map(str, info["tcp_listeners"]))

    print("algenta runtime doctor")
    print(f"  runtime source:  {info['runtime_source']}")
    print(f"  mode:            {info['mode']}")
    print(f"  path:            {info['path']}")
    print(f"  platform tag:    {info['platform_tag']}")
    print(f"  package version: {info['package_version']}")
    print(f"  abi (expected):  {info['abi_version_expected']}")
    print(f"  abi (native):    {info['abi_version_native']}")
    print(f"  loaded:          {info['loaded']}")
    print(f"  verified:        {info['verified']}")
    print(f"  fallback:        {fallback}")
    print(f"  tcp listeners:   {tcp}")
    print(f"  license:         {_license_state()}")
    if info.get("error"):
        print(f"  note:            {info['error']}")

    static_healthy = bool(info["loaded"] and info["verified"] and not info["tcp_listeners"])
    if not static_healthy:
        print("  status:          NOT READY")
        return 1

    # Final gate: a runtime that merely loads is not a runtime that can execute.
    ok, detail = _live_round_trip()
    if ok:
        print(f"  execution check: ok ({detail})")
        print("  status:          READY")
        return 0
    print(f"  execution check: FAILED ({detail})")
    print(
        "  remedy:          install the system libpython for Python "
        f"{sys.version_info.major}.{sys.version_info.minor} — on Debian/Ubuntu: "
        f"`sudo apt install libpython{sys.version_info.major}.{sys.version_info.minor}` — "
        "then re-run `algenta runtime doctor`"
    )
    print("  status:          NOT READY (execution check failed)")
    return 1
