"""
Verify local runtime execution with a real API key.

This is a user-facing self-check, not a mock smoke test:
  1. Calls the configured API base URL /v1/health.
  2. Exchanges the API key for a real device license.
  3. Verifies the local credit bucket was seeded.
  4. Auto-starts the local daemon in an isolated runtime dir.
  5. Executes a real local runtime request.

Examples:
  DE_API_KEY=de_live_... python3 scripts/verify_local_api_key_runtime.py
  DE_API_KEY=de_live_... DE_BASE_URL=https://api.algenta.ai \
      python3 scripts/verify_local_api_key_runtime.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import tempfile
from pathlib import Path

import httpx

PASS = "✅"  # noqa: S105 - status glyph, not a credential
FAIL = "❌"


def _base_url(args: argparse.Namespace) -> str:
    value = (
        args.base_url
        or os.environ.get("ALGENTA_BASE_URL", "")
        or os.environ.get("DE_BASE_URL", "")
        or os.environ.get("ALGENTA_API_URL", "")
        or "https://api.algenta.ai"
    )
    return value.rstrip("/")


def _api_key(args: argparse.Namespace) -> str:
    return (
        args.api_key
        or os.environ.get("ALGENTA_API_KEY", "")
        or os.environ.get("DE_API_KEY", "")
    )


def _print_result(ok: bool, name: str, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    suffix = f": {detail}" if detail else ""
    print(f"  {icon} {name}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify local runtime execution with a real API key"
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="API key to verify. Defaults to ALGENTA_API_KEY / DE_API_KEY.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="API base URL. Defaults to ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.",
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="Request timeout in seconds."
    )
    parser.add_argument(
        "--runtime-dir",
        default="",
        help="Optional runtime dir. Defaults to a temporary isolated dir.",
    )
    parser.add_argument(
        "--keep-runtime-dir",
        action="store_true",
        help="Keep the runtime dir after the check.",
    )
    args = parser.parse_args()

    api_key = _api_key(args)
    base_url = _base_url(args)
    if not api_key:
        print(f"  {FAIL} API key missing: set DE_API_KEY or pass --api-key")
        return 1

    runtime_dir = (
        Path(args.runtime_dir)
        if args.runtime_dir
        else Path(tempfile.mkdtemp(prefix="algenta-runtime-verify-"))
    )
    daemon_sock = runtime_dir / "daemon.sock"
    mojo_sock = runtime_dir / "mojo.sock"

    socket.setdefaulttimeout(int(max(args.timeout, 5.0)))

    print("\n" + "=" * 72)
    print("  VERIFY LOCAL API KEY RUNTIME")
    print("=" * 72)
    print(f"  Base URL:    {base_url}")
    print(f"  Runtime dir: {runtime_dir}")

    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_CONTROL_PLANE_URL": base_url,
        "ALGENTA_BASE_URL": base_url,
        "DE_BASE_URL": base_url,
        "ALGENTA_API_KEY": api_key,
        "DE_API_KEY": api_key,
        "ALGENTA_DAEMON_SOCK": str(daemon_sock),
        "ALGENTA_DAEMON_TCP": "127.0.0.1:50119",
        "ALGENTA_MOJO_SOCK": str(mojo_sock),
    }
    old_env = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)

    try:
        try:
            health = httpx.get(f"{base_url}/v1/health", timeout=args.timeout)
            health.raise_for_status()
            _print_result(True, "API health check", f"{health.status_code}")
        except Exception as exc:
            _print_result(False, "API health check", str(exc))
            return 1

        from apps.runtime.credits import get_store
        from apps.runtime.daemon import cmd_stop, is_running
        from apps.runtime.license import issue_and_store, load_license
        from apps.runtime.sdk import Runtime

        def _cleanup_daemon() -> None:
            if is_running():
                cmd_stop()

        try:
            _cleanup_daemon()
        except Exception as err:
            _print_result(False, "_cleanup_daemon()", str(err))
            return 1

        try:
            lic = issue_and_store(api_key)
            if not lic.valid:
                _print_result(False, "issue_and_store(api_key)", lic.message or "license invalid")
                return 1
            _print_result(True, "issue_and_store(api_key)", f"plan={lic.plan} source={lic.source}")
        except Exception as exc:
            _print_result(False, "issue_and_store(api_key)", str(exc))
            return 1

        try:
            state = get_store()._read()
            if state is None or state.credits_remaining <= 0 or state.credits_total <= 0:
                _print_result(False, "local credit bucket", "credits were not seeded")
                return 1
            _print_result(True, "local credit bucket", f"remaining={state.credits_remaining}")
        except Exception as exc:
            _print_result(False, "local credit bucket", str(exc))
            return 1

        try:
            lic = load_license(api_key)
            if not lic.valid:
                _print_result(
                    False, "load_license(api_key)", lic.message or "stored license invalid"
                )
                return 1
            _print_result(True, "load_license(api_key)", f"plan={lic.plan} source={lic.source}")
        except Exception as exc:
            _print_result(False, "load_license(api_key)", str(exc))
            return 1

        try:
            runtime = Runtime(
                mode="local",
                api_key=api_key,
                base_url=base_url,
                auto_start_daemon=True,
                timeout=args.timeout,
            )
            result = runtime.execute("monte_carlo", "run", {})
            if not result.get("success"):
                _print_result(False, "Runtime(mode='local').execute()", str(result))
                return 1
            engine_used = str(result.get("engine_used", "unknown"))
            latency_ms = result.get("latency_ms", "n/a")
            _print_result(
                True,
                "Runtime(mode='local').execute()",
                f"engine={engine_used} latency_ms={latency_ms}",
            )
        except Exception as exc:
            _print_result(False, "Runtime(mode='local').execute()", str(exc))
            return 1
        finally:
            try:
                _cleanup_daemon()
            except Exception as err:
                _print_result(False, "_cleanup_daemon()", str(err))

        print("=" * 72)
        print("  Local API-key runtime verification passed")
        print("=" * 72)
        return 0
    finally:
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        if not args.keep_runtime_dir:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
