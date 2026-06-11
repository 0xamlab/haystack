"""
Real local-runtime integration against a live API server.

This verifies the API-key-backed local runtime path, not the dev-stub path:
  1. Exchange a real API key for a device license against the live server.
  2. Seed the local credit bucket from the real registration response.
  3. Auto-start the local daemon with an explicit api_key argument.
  4. Execute through the local daemon.
"""

from __future__ import annotations

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_local_runtime_real.py",
        allow_module_level=True,
    )

import importlib
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

import httpx

socket.setdefaulttimeout(20)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from tests.integration.live_local_defaults import resolve_local_live_base_url
except ModuleNotFoundError:
    from live_local_defaults import resolve_local_live_base_url

BASE_URL = resolve_local_live_base_url(strip_trailing_slash=True)
API_KEY = os.environ.get("DE_API_KEY", "")

# ruff: noqa: E402
from tests.integration.live_integration_artifacts import write_live_integration_summary

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
SUITE_NAME = "local_runtime_real"
results: list[tuple[str, bool, str]] = []


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def check(name: str, fn):
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        results.append((name, True, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except AssertionError as exc:
        results.append((name, False, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except Exception as exc:
        results.append((name, False, f"{type(exc).__name__}: {exc}"))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(exc).__name__}: {exc}"
        )


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required")
    resp = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert resp.status_code == 200, f"/v1/health returned {resp.status_code}"


def _reload_runtime_modules() -> None:
    modules = [
        "apps.runtime.license",
        "apps.runtime.credits",
        "apps.runtime.metering",
        "apps.runtime.entitlement",
        "apps.runtime.client",
        "apps.runtime.daemon",
        "apps.runtime.sdk",
    ]
    for module_name in modules:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


def _license_verification_env() -> dict[str, str]:
    explicit = {
        "ALGENTA_LICENSE_SIGNING_SECRET": os.environ.get("ALGENTA_LICENSE_SIGNING_SECRET", ""),
        "LICENSE_SIGNING_SECRET": os.environ.get("LICENSE_SIGNING_SECRET", ""),
        "ALGENTA_JWT_SECRET": os.environ.get("ALGENTA_JWT_SECRET", ""),
        "JWT_SECRET": os.environ.get("JWT_SECRET", ""),
    }
    if any(value for value in explicit.values()):
        return {}

    try:
        from apps.api_server.config import get_settings
    except Exception:
        return {}

    settings = get_settings()
    if settings.license_signing_secret:
        return {"ALGENTA_LICENSE_SIGNING_SECRET": settings.license_signing_secret}
    if settings.jwt_secret:
        return {"ALGENTA_JWT_SECRET": settings.jwt_secret}
    return {}


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  Local Runtime Real Integration")
    _emit("=" * 70)

    if not API_KEY:
        reason = "DE_API_KEY is not set; skipping API-key-backed local runtime integration."
        _emit(f"  {SKIP} preflight: {reason}")
        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_local_runtime_real.py",
            passed=0,
            failed=0,
            skipped=1,
            total=1,
            elapsed_seconds=time.perf_counter() - started,
            details={
                "api_key_configured": False,
                "base_url": BASE_URL,
                "skipped_checks": [{"name": "preflight", "reason": reason}],
            },
        )
        _emit(f"Summary artifact: {artifact_path}")
        return 0

    _preflight()

    runtime_dir = Path(tempfile.mkdtemp(prefix="algenta-runtime-real-"))
    daemon_sock = runtime_dir / "daemon.sock"
    mojo_sock = runtime_dir / "mojo.sock"

    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_CONTROL_PLANE_URL": BASE_URL,
        "ALGENTA_BASE_URL": BASE_URL,
        "DE_BASE_URL": BASE_URL,
        "ALGENTA_API_KEY": API_KEY,
        "DE_API_KEY": API_KEY,
        "ALGENTA_DAEMON_SOCK": str(daemon_sock),
        "ALGENTA_DAEMON_TCP": "127.0.0.1:50109",
        "ALGENTA_MOJO_SOCK": str(mojo_sock),
        "JWT_SECRET": os.environ.get(
            "JWT_SECRET",
            "change-me-in-production-use-256-bit-random-value",
        ),
    }
    env_updates.update(_license_verification_env())

    old_env = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)

    try:
        _reload_runtime_modules()

        from apps.runtime.credits import get_store
        from apps.runtime.daemon import cmd_stop, is_running
        from apps.runtime.license import issue_and_store, load_license
        from apps.runtime.sdk import Runtime

        def _cleanup_daemon() -> None:
            if is_running():
                cmd_stop()

        def test_issue_and_store_uses_control_plane_license():
            _cleanup_daemon()
            lic = issue_and_store(API_KEY)
            assert lic.valid is True, "license should be valid"
            assert lic.source == "control-plane", f"expected control-plane source, got {lic.source}"
            assert lic.plan and lic.plan != "unknown", f"expected a concrete plan, got {lic.plan}"

        check(
            "issue_and_store(api_key) → control-plane license",
            test_issue_and_store_uses_control_plane_license,
        )

        def test_credit_bucket_seeded_from_registration():
            state = get_store()._read()
            assert state is not None, "credits.json was not created"
            assert state.credits_remaining > 0, "no credits granted"
            assert state.credits_total > 0, "credits_total not seeded"

        check(
            "device registration seeds local credit bucket",
            test_credit_bucket_seeded_from_registration,
        )

        def test_load_license_returns_control_plane_token():
            lic = load_license(API_KEY)
            assert lic.valid is True, "stored license should still be valid"
            assert lic.source == "control-plane", f"expected control-plane source, got {lic.source}"

        check(
            "load_license(api_key) → stored control-plane license",
            test_load_license_returns_control_plane_token,
        )

        def test_runtime_local_execute_with_explicit_api_key():
            _cleanup_daemon()
            rt = Runtime(
                mode="local",
                api_key=API_KEY,
                base_url=BASE_URL,
                auto_start_daemon=True,
                timeout=20.0,
            )
            result = rt.execute("monte_carlo", "run", {})
            assert result["success"] is True, f"local runtime execution failed: {result}"
            assert result["engine_used"] in {"mojo", "python-fallback"}, result["engine_used"]

        check(
            "Runtime(mode='local', api_key=...) executes through daemon",
            test_runtime_local_execute_with_explicit_api_key,
        )

        _cleanup_daemon()
    finally:
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        shutil.rmtree(runtime_dir, ignore_errors=True)

    failed = [name for name, ok, _ in results if not ok]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for _, ok, _ in results if ok)}")
    _emit(f"Failed: {len(failed)}")
    if failed:
        for name in failed:
            _emit(f"  - {name}")
    _emit("=" * 70)
    artifact_path = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_local_runtime_real.py",
        passed=sum(1 for _, ok, _ in results if ok),
        failed=len(failed),
        total=len(results),
        elapsed_seconds=time.perf_counter() - started,
        details={
            "api_key_configured": bool(API_KEY),
            "base_url": BASE_URL,
            "failed_checks": failed,
        },
    )
    _emit(f"Summary artifact: {artifact_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
