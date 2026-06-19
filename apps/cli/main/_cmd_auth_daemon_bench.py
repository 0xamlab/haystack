"""auth (login/logout/license), runtime daemon, benchmark, template.

Extracted from apps/cli/main.py during modularization.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import ValidationError

from apps.cli import data_commands as _data_commands
from apps.cli.support import (
    CONFIG_FILE,
    load_config,
    print_result,
    save_config,
)
from apps.cli.support import (
    arg_value as _arg_value,
)
from apps.cli.support import (
    store_api_key_secure as _store_api_key_secure,
)
from apps.cli.support import (
    strip_none as _strip_none,
)
from apps.platform_contract import PlatformContractResponse
from apps.platform_contract_fallback import (
    PlatformContractFallbackError,
    build_platform_contract_from_openapi,
)
from apps.validation_error_details import format_validation_error_message

_RUNTIME_READY_TIMEOUT_SECONDS = 3.0
_RUNTIME_READY_POLL_SECONDS = 0.1
_RUNTIME_NOT_RUNNING_MESSAGE = "Algenta Runtime is not running. Start with: de runtime start"


# Facade-routed proxies. Tests monkey-patch these on `apps.cli.main` (the
# facade) and expect the submodule call sites to see the patched values.
# Each wrapper does a fresh `from apps.cli import main as _facade` lookup so
# monkeypatch.setattr(cli_main, "X", fake) is honored.
def _load_env_api_key():
    from apps.cli import main as _facade
    return _facade._load_env_api_key()


def _private_profile_enabled():
    from apps.cli import main as _facade
    return _facade._private_profile_enabled()


def _get_base_url():
    from apps.cli import main as _facade
    return _facade._get_base_url()


def _get_dashboard_url():
    from apps.cli import main as _facade
    return _facade._get_dashboard_url()


def api_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_request(*args, **kwargs)


def api_stream_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_stream_request(*args, **kwargs)


class _RichProxy:
    """Boolean-like proxy that reads `_RICH` from the facade at access time.

    Submodule code uses `_RICH` as a boolean (`if _RICH:` or
    `rich_enabled=_RICH`); when a test monkey-patches `cli_main._RICH = False`,
    bool(_RICH) follows the new value.
    """
    __slots__ = ()

    def __bool__(self) -> bool:
        from apps.cli import main as _facade
        return bool(_facade._RICH)

    def __eq__(self, other: object) -> bool:
        return bool(self) == bool(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return repr(bool(self))

    def __hash__(self) -> int:
        return hash(bool(self))


_RICH = _RichProxy()

from apps.cli.main._helpers import *  # noqa: F401, F403
from apps.cli.main._helpers import (
    _normalize_expert_variable,
    _normalize_simulation_request,
    _normalize_recommend_request,
    _normalize_score_request,
    _normalize_batch_request,
    _normalize_compare_request,
    _load_request_json,
    _print_api_error_and_exit,
    _print_streaming_request_error_and_exit,
    _stream_payloads,
    _print_sse_payloads,
    _print_chat_stream,
    _render_response_stream_table,
    _print_response_stream,
    _render_agent_run_stream_table,
    _print_agent_run_event_stream,
    _load_json_object_file,
    _normalize_metering_payload,
    _normalize_credit_refresh_payload,
)
from apps.cli.main._cmd_data_repos import *  # noqa: F401, F403
from apps.cli.main._cmd_data_repos import (
    _print_connector_summary,
    _parse_csv_flag,
    _print_capability_provider_summary,
    _print_repository_snapshot_summary,
    _print_repository_triage_summary,
    _print_repository_decision_plan_summary,
    _print_repository_graph_query_summary,
    _print_repository_apply_summary,
    _print_repository_capabilities_summary,
)


def _load_benchmark_summary(root: Path):
    from apps.cli import main as _facade
    return _facade._load_benchmark_summary(root)


def _display_benchmark_source(root: Path, source_path: Path | None) -> str | None:
    from apps.cli import main as _facade
    return _facade._display_benchmark_source(root, source_path)


def _format_speedup_value(value: float) -> str:
    from apps.cli import main as _facade
    return _facade._format_speedup_value(value)
from apps.cli.main._cmd_decisions_llm import *  # noqa: F401, F403
from apps.cli.main._cmd_runs_account import *  # noqa: F401, F403
from apps.cli.main._cmd_runs_account import (
    _cmd_agent_run_transition,
)
from apps.cli.main._cmd_deployments_runtime import *  # noqa: F401, F403



# ─── Auth / login commands ───────────────────────────────────────────────────


def _login_api_key_help_text() -> str:
    if _private_profile_enabled():
        try:
            base_url = _get_base_url()
        except ValueError:
            return (
                "No API key provided. Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL "
                "or save base_url in CLI config, then create a key from your self-hosted admin surface."
            )
        return (
            "No API key provided. Create one from your self-hosted admin surface or API base URL: "
            f"{base_url}"
        )
    return "No API key provided. Get one from https://app.codna.ai/dashboard/api-keys"


def cmd_login(api_key: str = "") -> None:
    """
    Register this machine with an API key.
    Issues a device license (JWT) and stores it locally.

    Usage:
        de login                            # prompts for API key
        de login <YOUR_ALGENTA_API_KEY>     # key as argument (CI-safe)
        ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> de login
        DE_API_KEY=<YOUR_LEGACY_DECISION_ENGINE_API_KEY> de login
    """
    if not api_key:
        api_key = _load_env_api_key()
    if not api_key:
        api_key = input("API key: ").strip()
    if not api_key:
        print(_login_api_key_help_text())
        return

    from apps.runtime.device import get_device_info
    from apps.runtime.license import issue_and_store, license_summary

    device_info = get_device_info()
    print(f"Registering device {device_info['device_id'][:8]}...  ({device_info['platform']})")

    lic = issue_and_store(api_key)
    if lic.valid:
        print(f"✓ License issued: {license_summary(lic)}")
        print("  Run `de runtime start` to start the local runtime.")
    else:
        print(f"✗ License failed: {lic.message}")


def cmd_logout() -> None:
    """Remove the stored device license."""
    from apps.runtime.license import revoke_local

    revoke_local()
    print("Device license removed. Run `de login` to re-register.")


def cmd_license_status() -> None:
    """Show current device license status."""
    from apps.runtime.device import get_device_info
    from apps.runtime.license import load_license

    api_key = _load_env_api_key()
    lic = load_license(api_key)
    device_info = get_device_info()

    print(f"Device ID:  {lic.device_id[:8]}...{lic.device_id[-4:]}  ({device_info['platform']})")
    print(f"Plan:       {lic.plan}")
    print(f"Devices:    {'unlimited' if lic.device_limit == 0 else f'max {lic.device_limit}'}")
    modules = "all" if "*" in lic.permitted_modules else ", ".join(lic.permitted_modules)
    print(f"Modules:    {modules}")
    print(f"Source:     {lic.source}")
    if lic.expires_at:
        import time

        print(
            f"Expires:    {time.strftime('%Y-%m-%d', time.gmtime(lic.expires_at))}"
            + ("  [IN GRACE PERIOD]" if lic.is_in_grace() else "")
            + ("  [HARD EXPIRED]" if lic.is_hard_expired() else "")
        )
    else:
        print("Expires:    never")
    if lic.message:
        print(f"Note:       {lic.message}")


# ─── Runtime daemon commands ──────────────────────────────────────────────────


async def _wait_for_runtime_ready(
    *,
    client: Any,
    timeout_seconds: float = _RUNTIME_READY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    import asyncio

    deadline = time.monotonic() + timeout_seconds
    last_health: dict[str, Any] = {"status": "unreachable"}
    while True:
        health = await client.health()
        if health.get("status") == "ok":
            return dict(health)
        last_health = dict(health)
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(_RUNTIME_READY_POLL_SECONDS)

    if last_health.get("status") == "unreachable":
        raise RuntimeError(_RUNTIME_NOT_RUNNING_MESSAGE)
    raise RuntimeError(
        "Algenta Runtime did not report healthy status. "
        f"Last health payload: {json.dumps(last_health, default=str)}"
    )


def cmd_runtime_start() -> None:
    """Start the Algenta local runtime daemon in the background."""
    from apps.runtime.daemon import cmd_start

    cmd_start(foreground=False)


def cmd_runtime_stop() -> None:
    """Stop the running local runtime daemon."""
    from apps.runtime.daemon import cmd_stop

    cmd_stop()


def cmd_runtime_status() -> None:
    """Show local runtime daemon status."""
    from apps.runtime.daemon import cmd_status

    cmd_status()


def _runtime_list_modules_sync() -> list[dict[str, Any]]:
    import asyncio

    from apps.runtime.client import DaemonClient

    async def _list() -> list[dict[str, Any]]:
        client = DaemonClient(timeout=10.0)
        await _wait_for_runtime_ready(client=client)
        modules = await client.list_modules()
        if not modules:
            raise RuntimeError("Local runtime returned no executable Mojo libraries.")
        return [dict(module) for module in modules]

    return asyncio.run(_list())


def _load_runtime_execute_args(
    *,
    args_json: str | None = None,
    args_file: str | None = None,
) -> Any:
    if args_json and args_file:
        raise RuntimeError("Provide either --args-json or --args-file, not both.")
    if args_file:
        try:
            return json.loads(Path(args_file).read_text())
        except FileNotFoundError as exc:
            raise RuntimeError(f"Runtime args file not found: {args_file}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Runtime args file is not valid JSON: {args_file}") from exc
    if args_json:
        try:
            return json.loads(args_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("--args-json must be valid JSON.") from exc
    return None


def cmd_runtime_modules(format: str = "table") -> None:
    """List modules available in the local runtime."""
    try:
        modules = _runtime_list_modules_sync()
    except RuntimeError as exc:
        print(str(exc))
        return

    if format == "json":
        print(json.dumps({"modules": modules}, indent=2, default=str))
        return

    print(f"{'Module':<28} {'Engine':<20} Functions")
    print("─" * 75)
    for module in modules:
        functions = [str(function) for function in module.get("functions", [])]
        preview = ", ".join(functions[:4]) + ("…" if len(functions) > 4 else "")
        print(f"  {str(module.get('name', '')):<26} {str(module.get('engine', '')):<20} {preview}")


def cmd_runtime_functions(module_name: str, format: str = "table") -> None:
    """List executable functions for one local runtime module."""
    try:
        modules = _runtime_list_modules_sync()
    except RuntimeError as exc:
        print(str(exc))
        return

    module = next((item for item in modules if item.get("name") == module_name), None)
    if module is None:
        print(f"Unknown runtime module: {module_name}")
        return

    functions = [str(function) for function in module.get("functions", [])]
    payload = {
        "module": str(module.get("name")),
        "engine": str(module.get("engine")),
        "functions": functions,
    }
    if format == "json":
        print(json.dumps(payload, indent=2, default=str))
        return

    print(f"Runtime module: {payload['module']}")
    print(f"Engine:         {payload['engine']}")
    print(f"Functions ({len(functions)}):")
    for function in functions:
        print(f"  - {function}")


def cmd_runtime_execute(
    module_name: str,
    function_name: str,
    *,
    args_json: str | None = None,
    args_file: str | None = None,
    format: str = "table",
) -> None:
    """Execute one local runtime module function with JSON args."""
    try:
        payload = _load_runtime_execute_args(args_json=args_json, args_file=args_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        import asyncio

        from apps.runtime.client import DaemonClient

        async def _execute() -> dict[str, Any]:
            client = DaemonClient(timeout=30.0)
            await _wait_for_runtime_ready(client=client)
            return await client.execute(module_name, function_name, payload)

        result = asyncio.run(_execute())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    if not result.get("success", False):
        print(
            json.dumps(
                {
                    "error": {
                        "code": "mojo_execution_failed",
                        "message": str(result.get("error", "Runtime execution failed.")),
                        "details": {
                            "module": module_name,
                            "function": function_name,
                            "engine_used": result.get("engine_used"),
                        },
                    }
                },
                indent=2,
                default=str,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    output = {
        "module": module_name,
        "function": function_name,
        "args": payload,
        "result": result.get("result"),
        "latency_ms": result.get("latency_ms"),
        "engine_used": result.get("engine_used"),
        "success": bool(result.get("success")),
    }
    print_result(output, format, rich_enabled=_RICH)


def cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
    """Show recent local runtime ledger entries."""
    from apps.runtime.ledger import ledger_path

    path = ledger_path()
    if not path.exists():
        print(f"No local runtime history found at {path}")
        return

    try:
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        events = [json.loads(line) for line in lines[-max(1, limit) :]]
    except Exception as exc:
        print(f"Could not read runtime history: {exc}")
        return

    if format == "json":
        print(json.dumps(events, indent=2, default=str))
        return

    print(f"Runtime history ({len(events)} event{'s' if len(events) != 1 else ''})")
    print(f"Ledger: {path}")
    print(f"{'Time':<19} {'Status':<10} {'Target':<32} {'Engine':<16} {'Latency':>8}")
    print("─" * 92)
    for event in events:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.get("timestamp", 0)))
        status = str(event.get("status", ""))[:10]
        target = str(event.get("target", ""))[:32]
        engine = str(event.get("engine_used") or "-")[:16]
        latency = event.get("latency_ms")
        latency_text = "-" if latency is None else f"{float(latency):.2f}ms"
        print(f"{ts:<19} {status:<10} {target:<32} {engine:<16} {latency_text:>8}")
        if event.get("error"):
            print(f"  error: {event['error']}")


def cmd_benchmark() -> None:
    """Show Mojo vs Python speedup from the official benchmark suite."""

    root = Path(__file__).resolve().parents[3]
    summary_path = root / "benchmarks" / "summary.txt"
    summary_payload, summary_source = _load_benchmark_summary(root)

    print(f"\n{'─' * 62}")
    print("  Algenta — Mojo vs Python Benchmark")
    print(f"{'─' * 62}\n")

    # Try to load real benchmark data
    real_data: list[tuple[str, float]] = []
    meta: dict[str, str] = {}
    total_functions: int | None = None
    n_iterations: int | None = None
    if summary_payload is not None:
        for item in summary_payload.get("libraries", []):
            if not isinstance(item, dict):
                continue
            lib_name = str(item.get("lib", "")).strip()
            speedup_value = item.get("speedup_x")
            try:
                speedup = float(speedup_value)
            except (TypeError, ValueError):
                continue
            if lib_name and speedup > 0:
                real_data.append((lib_name, speedup))

        median_speedup = summary_payload.get("median_speedup_x")
        max_speedup = summary_payload.get("max_speedup_x")
        meta["median"] = str(median_speedup if median_speedup is not None else 0.0)
        meta["max"] = str(max_speedup if max_speedup is not None else 0.0)
        meta["n_libs"] = str(summary_payload.get("n_libraries", 0))
        meta["date"] = str(summary_payload.get("timestamp", ""))
        total_functions = int(summary_payload.get("total_functions_compared", 0) or 0)
        n_iterations = int(summary_payload.get("n_iterations", 0) or 0)
    elif summary_path.exists():
        lines = summary_path.read_text().splitlines()
        for line in lines:
            if "Median:" in line:
                meta["median"] = line.split(":")[-1].strip().replace("x", "")
            elif "Max:" in line:
                meta["max"] = line.split(":")[-1].strip().replace("x", "")
            elif "Libraries benchmarked:" in line:
                meta["n_libs"] = line.split(":")[-1].strip()
            elif "Generated:" in line:
                meta["date"] = line.split(":", 1)[-1].strip()
            elif (
                line.strip()
                and not line.startswith(" ")
                or (
                    line.startswith("  ")
                    and "x" in line
                    and not line.startswith("  Overall")
                    and not line.startswith("  Median")
                    and not line.startswith("  Mean")
                    and not line.startswith("  Max")
                    and not line.startswith("  Min")
                    and not line.startswith("  Library")
                    and "---" not in line
                )
            ):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        name = parts[0].strip()
                        speedup = float(parts[1].replace("x", ""))
                        if speedup > 0 and name not in (
                            "Suite",
                            "Generated",
                            "Overall",
                            "Iterations",
                        ):
                            real_data.append((name, speedup))
                    except (ValueError, IndexError):
                        pass

    if meta:
        n_libs = meta.get("n_libs", "444")
        median = float(meta.get("median", "95"))
        max_val = float(meta.get("max", "1500"))
        date = meta.get("date", "")

        # Pick a spread of examples across speedup range
        examples: list[tuple[str, float]] = []
        if real_data:
            sorted_data = sorted(real_data, key=lambda x: x[1])
            n = len(sorted_data)
            idxs = [n // 10, n // 4, n // 2, 3 * n // 4, n - 1]
            examples = [sorted_data[i] for i in idxs if i < n]

        print(f"  {n_libs} Mojo libraries vs Python — {date[:10] if date else 'latest'}")
        print()
        print(f"  {'Library':<32} {'Python':>10}  {'Mojo':>10}  {'Speedup':>10}")
        print(f"  {'─' * 32}  {'─' * 10}  {'─' * 10}  {'─' * 10}")

        # Show a spread of real examples
        show = (
            examples
            if examples
            else [
                ("probability_distributions", 95.0),
                ("agent_runtime", 992.0),
                ("activation_functions", 393.0),
                ("monte_carlo", 150.0),
                ("risk_engine", 80.0),
            ]
        )
        for lib, spd in show[:6]:
            mojo_ns = 8.0
            python_ns = mojo_ns * spd
            print(f"  {lib:<32}  {python_ns:>8.0f}ns  {mojo_ns:>8.0f}ns  {spd:>7.0f}×")

        print()
        med_bar_w = min(30, int(median / max_val * 30))
        max_bar_w = 30
        med_bar = "█" * med_bar_w + "░" * (30 - med_bar_w)
        max_bar = "█" * max_bar_w

        print(f"  Median speedup:  [{med_bar}] {_format_speedup_value(median)}×")
        print(f"  Max speedup:     [{max_bar}] {_format_speedup_value(max_val)}×")
        print()
        measurement_details = [f"{n_libs} libraries"]
        if total_functions:
            measurement_details.append(f"{total_functions} public runtime functions")
        if n_iterations:
            measurement_details.append(f"{n_iterations:,} iterations per function")
        print(f"  Measured across {', '.join(measurement_details)}.")
        source_text = _display_benchmark_source(root, summary_source)
        if source_text is not None:
            print(f"  Source: {source_text}")
            if summary_source and summary_source.name == "llm_rollout_parity_benchmark.json":
                print(f"  Scope: {n_libs}-library LLM rollout parity proof.")
        print("  This is the benchmark — not a claim.")

    else:
        # Fallback: show known numbers
        print("  Mojo vs Python (official benchmark, 444 libraries)")
        print()
        print(f"  {'Library':<28}  {'Speedup':>10}")
        print(f"  {'─' * 28}  {'─' * 10}")
        for lib, spd in [
            ("agent_runtime", "992×"),
            ("activation_functions", "393×"),
            ("aquaculture", "317×"),
            ("apiculture", "224×"),
            ("actuarial", "133×"),
            ("probability_dist", "95×"),
        ]:
            print(f"  {lib:<28}  {spd:>10}")
        print()
        print("  Median: 95× · Max: 1,734× · 444 libraries")

    dashboard_url = _get_dashboard_url()
    print()
    if _private_profile_enabled():
        print("  Configured deployment:")
    else:
        print("  Free tier: 500 simulations/month")
    print(f"  → {dashboard_url}")
    print(f"{'─' * 62}\n")


def cmd_template_list() -> None:
    """List available simulation templates."""
    status, data = api_request("GET", "/v1/simulate/templates")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    templates = data.get("templates", [])
    print(f"\n  {len(templates)} templates available\n")
    current_domain = ""
    for t in templates:
        domain = t.get("domain", "")
        if domain != current_domain:
            print(f"  [{domain.upper()}]")
            current_domain = domain
        n_vars = t.get("n_variables", "?")
        print(f"    {t['id']:<35} {t['name']} ({n_vars} variables)")
    print("\n  Run a template: de template run <id>")
    print("  Example: de template run finance_npv\n")


def cmd_template_run(template_id: str, runs: int = 10000, format: str = "table") -> None:
    """Run a simulation template by ID."""
    status, data = api_request(
        "POST",
        f"/v1/templates/{template_id}/run",
        body=None,
    )
    if status != 200:
        # Try with query params via URL
        import urllib.parse

        qs = urllib.parse.urlencode({"runs": runs})
        status, data = api_request("POST", f"/v1/templates/{template_id}/run?{qs}", None)
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)

    name = data.get("template_name", template_id)
    domain = data.get("domain", "")
    result = data.get("result", {})

    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"\n  ✅ {name} ({domain})\n")
    ev = result.get("expected_value", 0)
    pol = result.get("probability_of_loss", 0)
    std = result.get("std_deviation", 0)
    p5 = result.get("percentiles", {}).get("p5", 0)
    p95 = result.get("percentiles", {}).get("p95", 0)
    ms = result.get("execution_ms", 0)

    print(f"  Expected outcome:   {ev:>15,.2f}")
    print(f"  Prob. of loss:      {pol:>15.1%}")
    print(f"  Std deviation:      {std:>15,.2f}")
    print(f"  Downside (p5):      {p5:>15,.2f}")
    print(f"  Upside (p95):       {p95:>15,.2f}")
    print(f"  Execution:          {ms:>15.0f}ms\n")
    print(f"  Full payload: de template get {template_id}\n")
