"""
Real local-runtime integration against a live API server.

This verifies the API-key-backed local runtime path, not the dev-stub path:
  1. Exchange a real API key for a device license against the live server.
  2. Seed the local credit bucket from the real registration response.
  3. Auto-start the local daemon with an explicit api_key argument.
  4. Execute through the local daemon.
"""
from __future__ import annotations

import importlib
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

import httpx

socket.setdefaulttimeout(20)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("DE_API_KEY", "")
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        fn()
        results.append((name, True, ""))
        print(f"  {PASS} {name}")
    except AssertionError as exc:
        results.append((name, False, str(exc)))
        print(f"  {FAIL} {name}: {exc}")
    except Exception as exc:
        results.append((name, False, f"{type(exc).__name__}: {exc}"))
        print(f"  {FAIL} {name}: {type(exc).__name__}: {exc}")


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


def main() -> int:
    print("\n" + "=" * 70)
    print("  Local Runtime Real Integration")
    print("=" * 70)

    _preflight()

    runtime_dir = Path(tempfile.mkdtemp(prefix="algenta-runtime-real-"))
    daemon_sock = runtime_dir / "daemon.sock"
    mojo_sock = runtime_dir / "mojo.sock"

    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_CONTROL_PLANE_URL": BASE_URL,
        "ALGENTA_BASE_URL": BASE_URL,
        "DE_BASE_URL": BASE_URL,
        "DE_API_KEY": API_KEY,
        "ALGENTA_DAEMON_SOCK": str(daemon_sock),
        "ALGENTA_DAEMON_TCP": "127.0.0.1:50109",
        "ALGENTA_MOJO_SOCK": str(mojo_sock),
        "JWT_SECRET": "change-me-in-production-use-256-bit-random-value",
    }

    old_env = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)
    os.environ.pop("ALGENTA_API_KEY", None)

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
            assert lic.plan == "developer", f"expected developer plan, got {lic.plan}"

        check("issue_and_store(api_key) → control-plane license", test_issue_and_store_uses_control_plane_license)

        def test_credit_bucket_seeded_from_registration():
            state = get_store()._read()
            assert state is not None, "credits.json was not created"
            assert state.credits_remaining > 0, "no credits granted"
            assert state.credits_total > 0, "credits_total not seeded"

        check("device registration seeds local credit bucket", test_credit_bucket_seeded_from_registration)

        def test_load_license_returns_control_plane_token():
            lic = load_license(API_KEY)
            assert lic.valid is True, "stored license should still be valid"
            assert lic.source == "control-plane", f"expected control-plane source, got {lic.source}"

        check("load_license(api_key) → stored control-plane license", test_load_license_returns_control_plane_token)

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

        check("Runtime(mode='local', api_key=...) executes through daemon", test_runtime_local_execute_with_explicit_api_key)

        _cleanup_daemon()
    finally:
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        shutil.rmtree(runtime_dir, ignore_errors=True)

    failed = [name for name, ok, _ in results if not ok]
    print("\n" + "=" * 70)
    print(f"Passed: {sum(1 for _, ok, _ in results if ok)}")
    print(f"Failed: {len(failed)}")
    if failed:
        for name in failed:
            print(f"  - {name}")
    print("=" * 70)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
