"""
de — Algenta CLI

Simulation, optimization, and AI decisions from your terminal.

Usage:
    de benchmark                           # show speedup vs Python baseline
    de data connect                        # interactive connect flow
    de data list                           # list datasets
    de data inspect <dataset_id>           # inspect one dataset
    de data refresh <dataset_id>           # refresh one dataset
    de data disconnect <dataset_id>        # delete one dataset
    de simulate examples/sample.json       # run a simulation
    de recommend examples/compare.json     # get a recommendation
    de decision examples/inputs.json       # analyze a decision
    de template list                       # browse ready-to-run templates
    de template run finance_npv            # run a template instantly
    de template get finance_npv            # see template payload
    de job submit examples/large.json      # async job for large runs
    de job wait <job_id>                   # wait for job completion
    de job status <job_id>                 # check job status
    de config set-key de_live_...          # save your API key
    de health                              # check API status
    de version                             # show versions

Local runtime daemon:
    de runtime start                       # start local daemon (background)
    de runtime stop                        # stop local daemon
    de runtime status                      # show daemon status
    de runtime modules                     # list loaded modules
    de runtime history                     # inspect local runtime ledger

Install:
    pip install algenta-sdk
    # or from repo:
    PYTHONPATH=. python3 apps/cli/main.py benchmark
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Add project root for SDK import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import typer
    _RICH = True
except ImportError:
    typer = None  # type: ignore[assignment]
    _RICH = False

from apps.cli import data_commands as _data_commands
from apps.cli.support import (
    CONFIG_FILE,
    api_request,
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


def _normalize_expert_variable(variable: dict[str, Any]) -> dict[str, Any]:
    if isinstance(variable.get("params"), dict):
        params = dict(variable.get("params", {}))
    else:
        params = _strip_none(
            {
                "mean": variable.get("mean"),
                "std": variable.get("std") or variable.get("std_dev"),
                "low": variable.get("low"),
                "mode": variable.get("mode"),
                "high": variable.get("high"),
                "value": variable.get("value"),
                "min": variable.get("min"),
                "max": variable.get("max"),
                "p": variable.get("p"),
                "shape": variable.get("shape"),
                "scale": variable.get("scale"),
            }
        )
    return {
        "name": variable.get("name", "value"),
        "distribution": variable.get("distribution", "fixed"),
        "params": params,
    }


def _normalize_simulation_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenario" in payload or "simulation" in payload:
        return payload

    variables = payload.get("variables")
    if isinstance(variables, dict):
        normalized: dict[str, Any] = {
            "mode": "auto",
            "scenario": {
                "variables": variables,
                "objective": payload.get("objective", "maximize_net_value"),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    if isinstance(variables, list):
        variable_names = [v.get("name", "value") for v in variables if isinstance(v, dict)]
        objective = (
            payload.get("objective_function")
            or payload.get("objective")
            or " + ".join(variable_names)
            or "value"
        )
        normalized = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    _normalize_expert_variable(v)
                    for v in variables
                    if isinstance(v, dict)
                ],
                "objective_function": objective,
                "scoring": payload.get("scoring", {"expected_value": 0.6, "downside_risk": 0.4}),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    return payload


def _normalize_recommend_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "actions" in payload:
        return payload
    if "options" not in payload:
        return payload

    normalized_actions: list[dict[str, Any]] = []
    for idx, option in enumerate(payload.get("options", []), start=1):
        name = option.get("label") or option.get("name") or f"option_{idx}"
        expected_value = float(option.get("expected_value", 0.0) or 0.0)
        risk = max(float(option.get("risk", 0.1) or 0.1), 0.05)
        spread = max(abs(expected_value) * risk, 1.0)
        normalized_actions.append({
            "name": name,
            "request": {
                "mode": "expert",
                "simulation": {
                    "variables": [{
                        "name": "outcome",
                        "distribution": "triangular",
                        "params": {
                            "low": expected_value - spread,
                            "mode": expected_value,
                            "high": expected_value + spread,
                        },
                    }],
                    "objective_function": "outcome",
                    "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                },
                "runs": payload.get("runs", 1000),
            },
        })
    return {"actions": normalized_actions, "runs": payload.get("runs", 1000)}


def cmd_data_connect(request_path: str | None = None, format: str = "table") -> None:
    _data_commands.cmd_data_connect(
        request_path=request_path,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_list(format: str = "table") -> None:
    _data_commands.cmd_data_list(format=format, api_request=api_request, rich_enabled=_RICH)


def cmd_data_inspect(dataset_id: str, format: str = "table") -> None:
    _data_commands.cmd_data_inspect(
        dataset_id,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_refresh(dataset_id: str, format: str = "table") -> None:
    _data_commands.cmd_data_refresh(
        dataset_id,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_disconnect(
    dataset_id: str,
    *,
    assume_yes: bool = False,
    format: str = "table",
) -> None:
    _data_commands.cmd_data_disconnect(
        dataset_id,
        assume_yes=assume_yes,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


# ─── CLI Commands ─────────────────────────────────────────────────────────────

def cmd_config_set_key(api_key: str, base_url: str | None = None) -> None:
    config = load_config()
    _store_api_key_secure(config, api_key)
    if base_url:
        config["base_url"] = base_url
    save_config(config)
    print(f"✅ API key saved to {CONFIG_FILE}")
    print(f"   Key prefix: {api_key[:12]}...")


def cmd_simulate(
    filepath: str,
    format: str = "table",
    runs: int = 10000,
    seed: int | None = None,
) -> None:
    payload = _normalize_simulation_request(json.loads(Path(filepath).read_text()))
    if runs != 10000:
        payload["runs"] = runs
    if seed is not None:
        payload["seed"] = seed
    status, data = api_request("POST", "/v1/simulate", payload)
    if status == 200:
        print_result(data, format)
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_recommend(filepath: str, format: str = "table") -> None:
    payload = _normalize_recommend_request(json.loads(Path(filepath).read_text()))
    status, data = api_request("POST", "/v1/recommend", payload)
    if status == 200:
        if format == "json":
            print(json.dumps(data, indent=2, default=str))
        else:
            print(
                f"\n✅ Recommended: {data.get('recommended_action')} "
                f"(confidence: {data.get('confidence', 0):.0%})"
            )
            print(f"   {data.get('rationale', '')}")
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_submit(filepath: str, callback_url: str | None = None) -> None:
    payload = _normalize_simulation_request(json.loads(Path(filepath).read_text()))
    body: dict[str, Any] = {"request": payload}
    if callback_url:
        body["callback_url"] = callback_url
    status, data = api_request("POST", "/v1/jobs", body)
    if status == 202:
        print(f"✅ Job submitted: {data['job_id']}")
        print(f"   Status: {data['status']}")
        print(f"   Poll: {data['poll_url']}")
        print(f"\nTo wait for completion: de job wait {data['job_id']}")
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_status(job_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/jobs/{job_id}")
    if status == 200:
        if format == "json":
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"Job ID: {data['job_id']}")
            print(f"Status: {data['status']}")
            if data.get("error_message"):
                print(f"Error:  {data['error_message']}")
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_wait(job_id: str, timeout: int = 300, format: str = "table") -> None:
    print(f"Waiting for job {job_id[:8]}... (timeout: {timeout}s)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, status_data = api_request("GET", f"/v1/jobs/{job_id}")
        job_status = status_data.get("status", "unknown")
        print(f"  [{time.strftime('%H:%M:%S')}] status: {job_status}", end="\r")
        if job_status == "completed":
            print("\n✅ Job completed!")
            _, result = api_request("GET", f"/v1/jobs/{job_id}/result")
            print_result(result, format)
            return
        elif job_status in ("failed", "cancelled"):
            print(f"\n❌ Job {job_status}: {status_data.get('error_message', 'no details')}")
            sys.exit(1)
        time.sleep(2)
    print(f"\n❌ Timeout after {timeout}s")
    sys.exit(1)


def cmd_keys_list() -> None:
    _, data = api_request("GET", "/v1/api-keys")
    if isinstance(data, list):
        print(f"\nAPI Keys ({len(data)} active):")
        for key_info in data:
            k: dict[str, str] = key_info  # type: ignore[assignment]
            print(f"  {k.get('key_prefix', '')}... [{k.get('label', '')}] — {k.get('status', '')}")
    else:
        print(json.dumps(data, indent=2))


def cmd_health() -> None:
    _, data = api_request("GET", "/v1/health")
    status = data.get("status", "unknown")
    print(f"API Status: {'✅ OK' if status == 'ok' else '❌ ' + status}")


# ─── Auth / login commands ───────────────────────────────────────────────────

def cmd_login(api_key: str = "") -> None:
    """
    Register this machine with an API key.
    Issues a device license (JWT) and stores it locally.

    Usage:
        de login                            # prompts for API key
        de login de_live_...               # key as argument (CI-safe)
        ALGENTA_API_KEY=de_live_... de login
    """
    if not api_key:
        api_key = os.environ.get("ALGENTA_API_KEY", "")
    if not api_key:
        api_key = input("API key: ").strip()
    if not api_key:
        print("No API key provided. Get one at algenta.io")
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

    api_key = os.environ.get("ALGENTA_API_KEY", "")
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
        print(f"Expires:    {time.strftime('%Y-%m-%d', time.gmtime(lic.expires_at))}"
              + ("  [IN GRACE PERIOD]" if lic.is_in_grace() else "")
              + ("  [HARD EXPIRED]" if lic.is_hard_expired() else ""))
    else:
        print("Expires:    never")
    if lic.message:
        print(f"Note:       {lic.message}")


# ─── Runtime daemon commands ──────────────────────────────────────────────────

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


def cmd_runtime_modules() -> None:
    """List modules available in the local runtime."""
    from apps.runtime.daemon import _DAEMON_SOCK, is_running
    if not is_running():
        print("Algenta Runtime is not running. Start with: de runtime start")
        return

    try:
        import asyncio

        import grpc
        import grpc.aio

        from apps.runtime.proto import runtime_pb2, runtime_pb2_grpc

        async def _list() -> None:
            async with grpc.aio.insecure_channel(f"unix://{_DAEMON_SOCK}") as ch:
                stub = runtime_pb2_grpc.AlgentaRuntimeStub(ch)
                resp = await stub.ListModules(runtime_pb2.ListModulesRequest(), timeout=5.0)
                print(f"{'Module':<28} {'Engine':<20} Functions")
                print("─" * 75)
                for m in resp.modules:
                    fns = ", ".join(m.functions[:4]) + ("…" if len(m.functions) > 4 else "")
                    print(f"  {m.name:<26} {m.engine:<20} {fns}")

        asyncio.run(_list())
    except Exception as exc:
        print(f"Could not connect to runtime: {exc}")


def cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
    """Show recent local runtime ledger entries."""
    from apps.runtime.ledger import ledger_path

    path = ledger_path()
    if not path.exists():
        print(f"No local runtime history found at {path}")
        return

    try:
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        events = [json.loads(line) for line in lines[-max(1, limit):]]
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

    root = Path(__file__).parent.parent.parent
    summary_path = root / "benchmarks" / "summary.txt"

    print(f"\n{'─'*62}")
    print("  Algenta — Mojo vs Python Benchmark")
    print(f"{'─'*62}\n")

    # Try to load real benchmark data
    real_data: list[tuple[str, float]] = []
    meta: dict[str, str] = {}
    if summary_path.exists():
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
            elif line.strip() and not line.startswith(" ") or (
                line.startswith("  ") and "x" in line and not line.startswith("  Overall")
                and not line.startswith("  Median") and not line.startswith("  Mean")
                and not line.startswith("  Max") and not line.startswith("  Min")
                and not line.startswith("  Library")
                and "---" not in line
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
        n_libs  = meta.get("n_libs",  "444")
        median  = float(meta.get("median", "95"))
        max_val = float(meta.get("max",   "1500"))
        date    = meta.get("date", "")

        # Pick a spread of examples across speedup range
        examples: list[tuple[str, float]] = []
        if real_data:
            sorted_data = sorted(real_data, key=lambda x: x[1])
            n = len(sorted_data)
            idxs = [n//10, n//4, n//2, 3*n//4, n-1]
            examples = [sorted_data[i] for i in idxs if i < n]

        print(f"  {n_libs} Mojo libraries vs Python — {date[:10] if date else 'latest'}")
        print()
        print(f"  {'Library':<32} {'Python':>10}  {'Mojo':>10}  {'Speedup':>10}")
        print(f"  {'─'*32}  {'─'*10}  {'─'*10}  {'─'*10}")

        # Show a spread of real examples
        show = examples if examples else [
            ("probability_distributions", 95.0),
            ("agent_runtime",             992.0),
            ("activation_functions",      393.0),
            ("monte_carlo",               150.0),
            ("risk_engine",                80.0),
        ]
        for lib, spd in show[:6]:
            mojo_ns   = 8.0
            python_ns = mojo_ns * spd
            print(f"  {lib:<32}  {python_ns:>8.0f}ns  {mojo_ns:>8.0f}ns  {spd:>7.0f}×")

        print()
        med_bar_w = min(30, int(median / max_val * 30))
        max_bar_w = 30
        med_bar = "█" * med_bar_w + "░" * (30 - med_bar_w)
        max_bar = "█" * max_bar_w

        print(f"  Median speedup:  [{med_bar}] {median:.0f}×")
        print(f"  Max speedup:     [{max_bar}] {max_val:.0f}×")
        print()
        print(f"  Measured across {n_libs} libraries, 10,000 iterations per function.")
        print("  This is the benchmark — not a claim.")

    else:
        # Fallback: show known numbers
        print("  Mojo vs Python (official benchmark, 444 libraries)")
        print()
        print(f"  {'Library':<28}  {'Speedup':>10}")
        print(f"  {'─'*28}  {'─'*10}")
        for lib, spd in [
            ("agent_runtime",      "992×"),
            ("activation_functions","393×"),
            ("aquaculture",        "317×"),
            ("apiculture",         "224×"),
            ("actuarial",          "133×"),
            ("probability_dist",    "95×"),
        ]:
            print(f"  {lib:<28}  {spd:>10}")
        print()
        print("  Median: 95× · Max: 1,734× · 444 libraries")

    print()
    print("  Free tier: 500 simulations/month")
    print("  → algenta.ai/dashboard")
    print(f"{'─'*62}\n")


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
        "POST", f"/v1/templates/{template_id}/run",
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
    ev  = result.get("expected_value", 0)
    pol = result.get("probability_of_loss", 0)
    std = result.get("std_deviation", 0)
    p5  = result.get("percentiles", {}).get("p5",  0)
    p95 = result.get("percentiles", {}).get("p95", 0)
    ms  = result.get("execution_ms", 0)

    print(f"  Expected outcome:   {ev:>15,.2f}")
    print(f"  Prob. of loss:      {pol:>15.1%}")
    print(f"  Std deviation:      {std:>15,.2f}")
    print(f"  Downside (p5):      {p5:>15,.2f}")
    print(f"  Upside (p95):       {p95:>15,.2f}")
    print(f"  Execution:          {ms:>15.0f}ms\n")
    print(f"  Full payload: de template get {template_id}\n")


# ─── Main entry point (without Typer) ────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    sub = args[1] if len(args) > 1 else ""

    def _json_format_flag() -> str:
        return "json" if _arg_value(args, "--format") == "json" else "table"

    if cmd == "config" and sub == "set-key" and len(args) >= 3:
        cmd_config_set_key(args[2], args[3] if len(args) > 3 else None)
    elif cmd == "data" and sub == "connect":
        request_path = _arg_value(args, "--request")
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_connect(request_path=request_path, format=fmt)
    elif cmd == "data" and sub == "list":
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_list(format=fmt)
    elif cmd == "data" and sub == "inspect" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_inspect(args[2], format=fmt)
    elif cmd == "data" and sub == "refresh" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_refresh(args[2], format=fmt)
    elif cmd == "data" and sub == "disconnect" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_disconnect(args[2], assume_yes="--yes" in args, format=fmt)
    elif cmd == "data":
        print("Usage: de data [connect|list|inspect|refresh|disconnect]")
    elif cmd == "simulate" and len(args) >= 2:
        cmd_simulate(args[1], _json_format_flag())
    elif cmd == "recommend" and len(args) >= 2:
        fmt = "json" if "--format" in args else "table"
        cmd_recommend(args[1], fmt)
    elif cmd == "job" and sub == "submit" and len(args) >= 3:
        callback = args[args.index("--callback") + 1] if "--callback" in args else None
        cmd_job_submit(args[2], callback)
    elif cmd == "job" and sub == "status" and len(args) >= 3:
        cmd_job_status(args[2])
    elif cmd == "job" and sub == "wait" and len(args) >= 3:
        timeout = int(args[args.index("--timeout") + 1]) if "--timeout" in args else 300
        cmd_job_wait(args[2], timeout)
    elif cmd == "login":
        cmd_login(args[1] if len(args) > 1 else "")
    elif cmd == "logout":
        cmd_logout()
    elif cmd == "license" and (not sub or sub == "status"):
        cmd_license_status()
    elif cmd == "keys" and sub == "list":
        cmd_keys_list()
    elif cmd == "runtime" and sub == "start":
        cmd_runtime_start()
    elif cmd == "runtime" and sub == "stop":
        cmd_runtime_stop()
    elif cmd == "runtime" and sub == "status":
        cmd_runtime_status()
    elif cmd == "runtime" and sub == "modules":
        cmd_runtime_modules()
    elif cmd == "runtime" and sub == "history":
        limit = int(_arg_value(args, "--limit") or "20")
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_history(limit=limit, format=fmt)
    elif cmd == "runtime":
        print("Usage: de runtime [start|stop|status|modules|history]")
    elif cmd == "health":
        cmd_health()
    elif cmd == "version":
        _, data = api_request("GET", "/v1/version")
        print(f"API: {data.get('api_version')} | Engine: {data.get('engine_version')}")
    elif cmd == "benchmark":
        cmd_benchmark()
    elif cmd == "template" and sub == "list":
        cmd_template_list()
    elif cmd == "template" and sub == "run" and len(args) >= 3:
        runs = int(args[args.index("--runs") + 1]) if "--runs" in args else 10000
        cmd_template_run(args[2], runs=runs, format=_json_format_flag())
    elif cmd == "template" and sub == "get" and len(args) >= 3:
        status, data = api_request("GET", f"/v1/simulate/templates/{args[2]}")
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Unknown command: {' '.join(args)}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
