"""
algenta CLI — runtime-first local demo, deterministic querying, and secondary local tools.

Usage:
  algenta demo                   # interactive local runtime demo
  algenta demo --list            # list selectable demo scenarios
  algenta demo --scenario region # run one scenario non-interactively
  algenta import orders.csv      # branded local import preview
  algenta import a.csv b.csv     # branded local bundle preview
  algenta map file1.csv [file2]  # instant local schema mapping
  algenta query "..." file.csv   # deterministic local query helper
  algenta benchmark              # show local speedup vs Python baseline
  algenta simulate               # run a quick local simulation
  algenta version                # show version and capabilities
  algenta upgrade                # show how to switch to cloud API
  algenta runtime doctor         # verify the bundled runtime
  algenta runtime modules        # list bundled runtime libraries
  algenta runtime functions NAME # list functions for one library
  algenta runtime execute NAME FUNCTION --args-json '{}'
  algenta serve --model DIR --prompt "..."       # serve on the detected backend
  algenta serve --backend cuda --model DIR --prompt-file p.txt --json
  algenta serve --backend cuda --model DIR --prompt "..." --dry-run
  algenta serve --backends       # published backends + their declared host requirements

`algenta serve` is gated, never opportunistic: an explicit `--backend` that this
host cannot satisfy exits 2 with a typed refusal (the conformance system's own
vocabulary) instead of quietly serving on a different backend.

Cloud Managed path: `algenta upgrade` shows the hosted console flow. In
`self_hosted` and `air_gapped`, use the API key provisioned by your
self-hosted operator deployment instead. Private profiles fail closed and do
not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import json
import sys
import time
from statistics import median

from algenta.branding import runtime_banner
from algenta.privacy_profile import (
    credential_setup_help_text,
    private_profile_enabled,
    resolve_console_base_url,
)


def _format_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms * 1000:.0f}µs"
    return f"{ms:.1f}ms"


def _native_simulation_request(*, runs: int) -> dict[str, object]:
    return {
        "engine_type": "monte_carlo",
        "runs": runs,
        "seed": 42,
        "variables": [
            {
                "name": "revenue",
                "distribution": "normal",
                "params": {"mean": 100000, "std": 15000},
            },
            {
                "name": "cost",
                "distribution": "normal",
                "params": {"mean": 70000, "std": 10000},
            },
        ],
        "objective_function": "revenue - cost",
    }


def _execute_native_simulation(*, runs: int) -> dict[str, object]:
    from algenta.native import loader

    result = loader.execute(_native_simulation_request(runs=runs))
    if not isinstance(result, dict):
        raise RuntimeError("The bundled runtime returned a malformed simulation result.")
    required = {"summary", "percentiles", "risk", "scenarios_run", "engine_version"}
    missing = sorted(required - set(result))
    if missing:
        raise RuntimeError(
            "The bundled runtime simulation result is incomplete: " + ", ".join(missing)
        )
    return result


def _execute_native_simulation_or_exit(*, runs: int) -> dict[str, object]:
    try:
        return _execute_native_simulation(runs=runs)
    except Exception as exc:  # noqa: BLE001 - command emits a stable public failure
        print(f"runtime execution failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def cmd_benchmark() -> None:
    runs = 10_000
    measurements = 10
    print("\n" + "─" * 58)
    print("  Algenta - Bundled Runtime Benchmark")
    print("─" * 58)
    print(f"  Workload: {runs:,}-scenario native Monte Carlo\n")

    started = time.perf_counter()
    _execute_native_simulation_or_exit(runs=runs)
    cold_ms = (time.perf_counter() - started) * 1000
    warm_ms: list[float] = []
    for _ in range(measurements):
        started = time.perf_counter()
        _execute_native_simulation_or_exit(runs=runs)
        warm_ms.append((time.perf_counter() - started) * 1000)
    ordered = sorted(warm_ms)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))

    print(f"  Cold start:         {_format_ms(cold_ms)}")
    print(f"  Warm p50:           {_format_ms(median(ordered))}")
    print(f"  Warm p95:           {_format_ms(ordered[p95_index])}")
    print(f"  Warm max:           {_format_ms(max(ordered))}")
    print("  Engine:             bundled native runtime")
    print("  Python fallback:    disabled")
    print("─" * 58 + "\n")


def cmd_simulate_quick() -> None:
    print("\nRunning quick simulation: revenue=100,000 cost=70,000 runs=10,000\n")
    t0 = time.perf_counter()
    result = _execute_native_simulation_or_exit(runs=10_000)
    ms = (time.perf_counter() - t0) * 1000
    summary = result["summary"]
    risk = result["risk"]
    percentiles = result["percentiles"]
    assert isinstance(summary, dict)
    assert isinstance(risk, dict)
    assert isinstance(percentiles, dict)
    print(f"  Expected outcome:   {float(summary['mean']):,.0f}")
    print(f"  Prob. of loss:      {float(risk['probability_of_loss']):.1%}")
    print(f"  Downside (p5):      {float(percentiles['p5']):,.0f}")
    print(f"  Upside (p95):       {float(percentiles['p95']):,.0f}")
    print(f"  Completed in:       {ms:.1f}ms  ({int(result['scenarios_run']):,} scenarios)")
    print("  Engine:             bundled native runtime")
    print("  Python fallback:    disabled\n")


def cmd_demo(args: list[str]) -> None:
    from algenta.demo import main as demo_main

    raise SystemExit(demo_main(args))


def cmd_version() -> None:
    from algenta import __version__

    print()
    print(
        runtime_banner(
            f"algenta {__version__}",
            [
                "Primary path: Runtime.resolve() -> Runtime.query()",
                "Secondary modes: simulate, decision, optimize, forecast, map_data, query_data",
                "Cloud/API mode: install algenta-sdk or algenta[cloud]",
            ],
        )
    )
    print()


def _parse_import_args(args: list[str]) -> tuple[list[str], str | None]:
    source_paths: list[str] = []
    source_name: str | None = None
    index = 0
    while index < len(args):
        current_arg = args[index]
        if current_arg == "--name":
            if index + 1 >= len(args):
                print("\n  Error: --name requires a value.\n")
                sys.exit(1)
            source_name = args[index + 1]
            index += 2
            continue
        if current_arg.startswith("--name="):
            source_name = current_arg.split("=", 1)[1]
            index += 1
            continue
        source_paths.append(current_arg)
        index += 1

    if not source_paths:
        print("\n  Usage: algenta import <file.csv> [more.csv ...] [--name orders]\n")
        print("  Example: algenta import orders.csv --name orders")
        print("           algenta import orders.csv financial.csv ratings.csv\n")
        sys.exit(1)

    if len(source_paths) > 1 and source_name is not None:
        print("\n  Error: --name is only supported when importing a single source.\n")
        sys.exit(1)

    return source_paths, source_name


def cmd_import(args: list[str]) -> None:
    from pathlib import Path

    from algenta import AlgentaRuntimeError, Runtime

    source_paths, source_name = _parse_import_args(args)
    paths = [Path(source_path).expanduser() for source_path in source_paths]
    missing_paths = [path for path in paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        print(f"\n  Error: file not found: {missing}\n")
        sys.exit(1)

    runtime = Runtime()
    if len(paths) == 1:
        path = paths[0]
        try:
            imported = runtime.import_preview(path, name=source_name, source_ref=str(path))
        except AlgentaRuntimeError as exc:
            print()
            print(
                runtime_banner(
                    "Algenta Import Failed",
                    [
                        f"Code: {exc.code}",
                        str(exc),
                        f"Source: {path}",
                    ],
                )
            )
            print()
            sys.exit(1)

        registration = imported.registration
        connected_name = registration.name or path.stem
        print()
        print(imported.preview)
        print()
        print("  Import preview complete.")
        print("  This command validates local registration and schema discovery only.")
        print("  Use Python Runtime() for a persistent local session:")
        print()
        print("    from algenta import Runtime")
        print("    rt = Runtime()")
        print(f"    rt.connect({str(path)!r}, name={connected_name!r})")
        print(f'    plan = rt.resolve({{"source_name": "{connected_name}", "metric": "revenue"}})')
        print("    result = rt.query(plan)")
        print()
        return

    bundle = runtime.import_bundle_preview(paths, source_refs=[str(path) for path in paths])
    print()
    print(bundle.preview)
    print()
    if bundle.failures:
        print("  Explicit import issues")
        for failure in bundle.failures:
            print(f"    - {failure.name or failure.source_ref}: {failure.code} — {failure.message}")
        print()
    print("  Bundle preview complete.")
    print("  This command validates local registration and schema discovery only.")
    print("  Use Python Runtime() for a persistent local session:")
    print()
    print("    from algenta import Runtime")
    print("    rt = Runtime()")
    rendered_paths = ", ".join(repr(str(path)) for path in paths)
    print(f"    rt.connect_many([{rendered_paths}])")
    if bundle.registrations:
        first_name = bundle.registrations[0].name or paths[0].stem
        print(f"    plan = rt.resolve({{'source_name': '{first_name}', 'metric': 'revenue'}})")
        print("    result = rt.query(plan)")
    print()
    if not bundle.registrations:
        sys.exit(1)


def cmd_map(args: list[str]) -> None:
    """algenta map file1.csv [file2.csv ...]"""
    if not args:
        print("\n  Usage: algenta map <file1.csv> [file2.csv ...]\n")
        print("  Example: algenta map sales.csv orders.csv\n")
        sys.exit(1)

    from pathlib import Path

    from algenta.map import map_data

    sources = args
    missing = [s for s in sources if not Path(s).exists()]
    if missing:
        print(f"\n  Error: file(s) not found: {', '.join(missing)}\n")
        sys.exit(1)

    print(f"\n  Mapping {len(sources)} source(s): {', '.join(Path(s).name for s in sources)}\n")
    t0 = time.perf_counter()
    result = map_data(*sources)
    ms = (time.perf_counter() - t0) * 1000

    print("─" * 62)
    print(
        "  Sources:  "
        f"{result.sources_analyzed}    Fields:  {result.total_fields}    "
        f"Mappings:  {len(result.mappings)}"
    )
    print(f"  Completed in {ms:.0f}ms")
    print("─" * 62)

    if result.mappings:
        print("\n  Field Mappings:\n")
        for m in result.mappings[:15]:
            bar = "█" * int(m.confidence * 10)
            pad = " " * (10 - len(bar))
            print(
                f"  [{bar}{pad}] {m.confidence:.0%}  "
                f"{m.source}.{m.source_field}  →  {m.target}.{m.target_field}"
            )
            print(f"              {' · '.join(m.reason)}")
        if len(result.mappings) > 15:
            print(f"\n  ... and {len(result.mappings) - 15} more mappings")

    if result.join_keys:
        print("\n  Join Keys:\n")
        for jk in result.join_keys:
            print(
                f"  {jk['source']}.{jk['field']} → "
                f"{jk['in_source']}.{jk['maps_to']}  "
                f"(confidence: {jk['confidence']:.0%})"
            )

    if result.simulation_ready:
        print("\n  ✓ Simulation ready — run `algenta simulate` or POST /v1/ingest")
    else:
        print("\n  ℹ Not enough numeric metric fields for simulation")

    if len(sources) == 1:
        print("\n  Tip: add another source to find cross-table relationships")
        print("       algenta map sales.csv orders.csv")
    print()


def cmd_query(args: list[str]) -> None:
    """algenta query "query text" file.csv [file2.csv ...]"""
    if len(args) < 2:
        print('\n  Usage: algenta query "<query>" <file.csv> [file2.csv ...]\n')
        print("  Examples:")
        print('    algenta query "total revenue by customer" sales.csv')
        print('    algenta query "top 10 orders by amount" orders.csv\n')
        sys.exit(1)

    query_text = args[0]
    files = args[1:]

    from pathlib import Path

    from algenta.map import query_data

    missing = [f for f in files if not Path(f).exists()]
    if missing:
        print(f"\n  Error: file(s) not found: {', '.join(missing)}\n")
        sys.exit(1)

    print(f'\n  Query: "{query_text}"')
    print(f"  Source(s): {', '.join(Path(f).name for f in files)}\n")

    t0 = time.perf_counter()
    result = query_data(query_text, *files)
    ms = (time.perf_counter() - t0) * 1000

    if not result:
        print("  No results found.\n")
        return

    # Print table
    cols = list(result[0].keys())
    col_widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in result)) for c in cols}

    header = "  " + "  ".join(c.upper().ljust(col_widths[c]) for c in cols)
    divider = "  " + "  ".join("─" * col_widths[c] for c in cols)

    print(header)
    print(divider)
    for row in result[:25]:
        line = "  " + "  ".join(str(row.get(c, "")).ljust(col_widths[c]) for c in cols)
        print(line)
    if len(result) > 25:
        print(f"\n  ... {len(result) - 25} more rows")

    print(f"\n  {len(result)} row(s) · {ms:.0f}ms\n")

    print("  Scale to millions of records: pip install algenta-sdk")
    print('  → client.query("...", sources=[...])\n')


def cmd_upgrade() -> None:
    if private_profile_enabled():
        console_base_url = resolve_console_base_url(component="algenta upgrade")
        credential_help = credential_setup_help_text(
            component="algenta upgrade",
            fallback_base_url=console_base_url,
        )
        print(
            f"""
  Connect Algenta SDK to your deployment
  ──────────────────────────────────────

  1. Configure your self-hosted API origin:
       export ALGENTA_BASE_URL="{console_base_url}"
       # or
       export DE_BASE_URL="{console_base_url}"
       # or
       export ALGENTA_API_URL="{console_base_url}"

  2. {credential_help}

  3. Install the SDK:
       pip install algenta-sdk
       # or
       pip install "algenta[cloud]"

  4. Switch from local runtime to direct API mode:

     Before:
       from algenta import Runtime
       rt = Runtime()
       plan = rt.resolve({{"metric": "revenue", "group_by": "product_line"}})
       result = rt.query(plan)

     After:
       from algenta import Runtime
       api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
       if not api_key:
           raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
       rt = Runtime(mode="api", api_key=api_key)
       plan = rt.resolve({{"source_name": "orders", "metric": "revenue", "group_by": "product_line"}})
       result = rt.query(plan)

     That upgrade example is the Cloud Managed path. In `self_hosted` and
     `air_gapped`, pass an explicit self-hosted base_url and use the API key
     provisioned by your self-hosted operator deployment instead.
"""
        )
        return

    print(
        f"""
  Upgrade to Algenta Cloud
  ─────────────────────────

  1. {credential_setup_help_text(component="algenta upgrade")}

  2. Install the SDK:
       pip install algenta-sdk
       # or
       pip install "algenta[cloud]"

  3. Switch from local runtime to direct API mode:

     Before:
       from algenta import Runtime
       rt = Runtime()
       plan = rt.resolve({{"metric": "revenue", "group_by": "product_line"}})
       result = rt.query(plan)

     After:
       from algenta import Runtime
       api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
       if not api_key:
           raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
       rt = Runtime(mode="api", api_key=api_key)
       plan = rt.resolve({{"source_name": "orders", "metric": "revenue", "group_by": "product_line"}})
       result = rt.query(plan)

     That upgrade example is the Cloud Managed path. In `self_hosted` and
     `air_gapped`, pass an explicit self-hosted base_url and use the API key
     provisioned by your self-hosted operator deployment instead.
"""
    )


def cmd_login(args: list[str]) -> None:
    """`algenta login` — browser device-code sign-in → free key + offline license. Lazy-imports login."""
    from algenta import login as _login

    open_browser = "--no-browser" not in args
    try:
        summary = _login.login(open_browser=open_browser)
    except _login.LoginError as exc:
        print(f"login failed: {exc}")
        sys.exit(1)
    print(f"  credentials: {summary['credential_storage']}")


def _runtime_option(args: list[str], name: str) -> str | None:
    for index, value in enumerate(args):
        if value == name:
            if index + 1 >= len(args):
                raise ValueError(f"{name} requires a value")
            return args[index + 1]
        if value.startswith(f"{name}="):
            return value.split("=", 1)[1]
    return None


def cmd_runtime(args: list[str]) -> None:
    """Inspect and execute the automatically managed bundled runtime."""
    sub = args[0] if args else ""
    if sub == "doctor":
        from algenta.native import doctor

        sys.exit(doctor.run())
    from algenta import MojoRuntime

    runtime = MojoRuntime(mode="local")
    if sub == "modules":
        print(json.dumps({"modules": runtime.list_modules()}, separators=(",", ":")))
        return
    if sub == "functions" and len(args) >= 2:
        module_name = args[1]
        print(
            json.dumps(
                {"module": module_name, "functions": runtime.list_functions(module_name)},
                separators=(",", ":"),
            )
        )
        return
    if sub == "execute" and len(args) >= 3:
        try:
            raw_args = _runtime_option(args[3:], "--args-json")
            payload = None if raw_args is None else json.loads(raw_args)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"invalid runtime arguments: {exc}", file=sys.stderr)
            sys.exit(2)
        result = runtime.execute(args[1], args[2], payload)
        print(json.dumps(result, separators=(",", ":"), default=str))
        if not result.get("success"):
            sys.exit(1)
        return
    print(
        "usage: algenta runtime "
        "[doctor|modules|functions <module>|execute <module> <function> [--args-json JSON]]"
    )
    sys.exit(2)


def cmd_whoami() -> None:
    from algenta import auth

    try:
        key = auth.read_api_key()
    except auth.CredentialStoreError as exc:
        print(f"not logged in: {exc}")
        sys.exit(1)
    if not key:
        print("not logged in — run `algenta login`")
        sys.exit(1)
    print("logged in")


def cmd_mcp(args: list[str]) -> None:
    """`algenta mcp` — run the thin stdio MCP bridge (separate `algenta-mcp` package, no native import)."""
    try:
        from algenta_mcp.server import main as mcp_main  # type: ignore
    except ImportError:
        print("The Algenta MCP bridge is a separate package. Install it with: pip install algenta-mcp")
        sys.exit(1)
    sys.exit(int(mcp_main() or 0))


def cmd_serve(args: list[str]) -> None:
    """`algenta serve` — serve one prompt on an explicitly gated engine backend.

    Lazy-imported like every other command here: importing `algenta.cli` must not
    drag the capability table, the tokenizer or the native worker onto the path of
    an `algenta version`. The exit codes are the conformance CLI's (documented in
    `algenta.serve.cli`), so an operator's wrapper branches identically on
    `algenta serve` and on `scripts/algenta_conform.py`.
    """
    from algenta.serve.cli import main as serve_main

    sys.exit(serve_main(args))


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    # One-time migration check: warn (never fail) if a legacy file-owning `algenta-core` shadows us.
    try:
        import algenta as _algenta

        _warn = _algenta.check_migration()
        if _warn:
            print(_warn, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — migration diagnostics are non-fatal
        print(
            f"warning: package migration check unavailable ({type(exc).__name__})",
            file=sys.stderr,
        )

    if cmd == "demo":
        cmd_demo(args[1:])
    elif cmd == "benchmark":
        cmd_benchmark()
    elif cmd == "import":
        cmd_import(args[1:])
    elif cmd in ("simulate", "sim"):
        cmd_simulate_quick()
    elif cmd == "map":
        cmd_map(args[1:])
    elif cmd == "query":
        cmd_query(args[1:])
    elif cmd == "version":
        cmd_version()
    elif cmd == "upgrade":
        cmd_upgrade()
    elif cmd == "login":
        cmd_login(args[1:])
    elif cmd == "runtime":
        cmd_runtime(args[1:])
    elif cmd == "whoami":
        cmd_whoami()
    elif cmd == "mcp":
        cmd_mcp(args[1:])
    elif cmd == "serve":
        cmd_serve(args[1:])
    else:
        print(
            runtime_banner(
                "Algenta CLI",
                [
                    "Primary path: algenta demo",
                    "Brandable import preview: algenta import <file.csv> --name orders",
                    "Deterministic local runtime: Runtime.resolve() -> Runtime.query()",
                    "Engine serving: algenta serve --model <ckpt> --prompt '...' [--backend cuda]",
                    "Secondary tools remain available: map, query, simulate, benchmark",
                ],
            )
        )
        print()
        print(__doc__)
        sys.exit(0 if cmd == "help" else 1)


if __name__ == "__main__":
    main()
