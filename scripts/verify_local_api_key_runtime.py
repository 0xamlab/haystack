"""
Verify local runtime execution with a real API key.

Prefer a bounded-lifetime replacement key from `POST /v1/api-keys`, not the
one-time self-host bootstrap key.

This is a user-facing self-check, not a mock smoke test:
  1. Calls the configured API base URL /v1/health.
  2. Exchanges the API key for a real device license.
  3. Verifies the local credit bucket was seeded.
  4. Auto-starts the local daemon in an isolated runtime dir.
  5. Executes a real local runtime request.
  6. Fails closed in self_hosted / air_gapped profiles unless a self-hosted
     base URL is configured explicitly.

Examples:
  ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> python3 scripts/verify_local_api_key_runtime.py
  DE_API_KEY=<YOUR_LEGACY_DECISION_ENGINE_API_KEY> DE_BASE_URL=http://localhost:8000 \
      python3 scripts/verify_local_api_key_runtime.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.platform_contract_constants import API_BASE_URL
from apps.privacy_policy import (
    is_algenta_owned_destination,
    parse_egress_destination,
    policy_from_environment,
)
from apps.runtime.privacy_guard import RuntimeEgressPolicyDeniedError, validated_runtime_egress_url
from scripts.local_operator_contract import resolve_operator_api_key

PASS = "✅"  # noqa: S105 - status glyph, not a credential
FAIL = "❌"


def _configured_base_url(args: argparse.Namespace) -> str:
    explicit_value = args.base_url.strip()
    if explicit_value:
        return explicit_value
    for key in ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL"):
        candidate = os.environ.get(key, "").strip()
        if candidate:
            return candidate
    return ""


def _base_url_egress_class(base_url: str) -> str:
    destination = parse_egress_destination(base_url)
    if is_algenta_owned_destination(destination.host):
        return "algenta_cloud"
    return "operator_service"


def _validated_verification_base_url(
    base_url: str,
    *,
    explicit_configured: bool,
) -> str:
    try:
        return validated_runtime_egress_url(
            base_url,
            surface="verify_local_api_key_runtime",
            field_name="base_url",
            explicit_configured=explicit_configured,
            egress_class=_base_url_egress_class(base_url),
        )
    except RuntimeEgressPolicyDeniedError as exc:
        if exc.decision.reason == "algenta_cloud_disabled":
            raise ValueError(
                "Private profiles cannot verify against Codna-owned cloud URLs. "
                "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL or pass --base-url."
            ) from exc
        raise


def _base_url(args: argparse.Namespace) -> str:
    configured = _configured_base_url(args).rstrip("/")
    explicit_configured = bool(args.base_url.strip()) or any(
        os.environ.get(key, "").strip() for key in ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL")
    )
    if explicit_configured:
        return _validated_verification_base_url(configured, explicit_configured=True)

    policy = policy_from_environment()
    if policy.private_profile or policy.disable_cloud:
        raise ValueError(
            "Self-hosted and air-gapped verification requires an explicit --base-url, "
            "ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL."
        )

    return _validated_verification_base_url(API_BASE_URL, explicit_configured=False)


def _api_key(args: argparse.Namespace) -> str:
    return resolve_operator_api_key(args.api_key, os.environ)


def _runtime_execution_env(
    *,
    runtime_dir: Path,
    daemon_sock: Path,
    mojo_sock: Path,
    base_url: str,
    api_key: str,
) -> dict[str, str]:
    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_CONTROL_PLANE_URL": base_url,
        "ALGENTA_BASE_URL": base_url,
        "DE_BASE_URL": base_url,
        "ALGENTA_API_URL": base_url,
        "ALGENTA_API_KEY": api_key,
        "DE_API_KEY": api_key,
        "ALGENTA_DAEMON_SOCK": str(daemon_sock),
        "ALGENTA_DAEMON_TCP": "127.0.0.1:50119",
        "ALGENTA_MOJO_SOCK": str(mojo_sock),
    }
    env_updates.update(_license_verification_env())
    return env_updates


def _print_result(ok: bool, name: str, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    suffix = f": {detail}" if detail else ""
    print(f"  {icon} {name}{suffix}")


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
    parser = argparse.ArgumentParser(
        description=(
            "Verify local runtime execution with a real API key. "
            "Prefer a bounded-lifetime replacement key, not the one-time bootstrap key. "
            "Self-hosted and air-gapped verification requires an explicit self-hosted base URL."
        )
    )
    parser.add_argument(
        "--api-key",
        default="",
        help=(
            "API key to verify. Prefer a rotated bounded-lifetime key. "
            "Defaults to ALGENTA_API_KEY / DE_API_KEY."
        ),
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="API base URL. Defaults to ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout in seconds.")
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
    try:
        base_url = _base_url(args)
    except Exception as exc:
        print(f"  {FAIL} Base URL invalid: {exc}")
        return 1
    if not api_key:
        print(f"  {FAIL} API key missing: set ALGENTA_API_KEY or DE_API_KEY or pass --api-key")
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

    env_updates = _runtime_execution_env(
        runtime_dir=runtime_dir,
        daemon_sock=daemon_sock,
        mojo_sock=mojo_sock,
        base_url=base_url,
        api_key=api_key,
    )
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
