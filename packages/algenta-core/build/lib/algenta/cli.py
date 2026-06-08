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

Cloud Managed path: `algenta upgrade` shows the hosted console flow. In
`self_hosted` and `air_gapped`, use the API key provisioned by your
self-hosted operator deployment instead. Private profiles fail closed and do
not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import math
import random
import sys
import time

from algenta.branding import runtime_banner
from algenta.privacy_profile import (
    api_key_help_text,
    private_profile_enabled,
    resolve_console_base_url,
    resolve_dashboard_url,
)


def _print_scale_guidance() -> None:
    dashboard_url = resolve_dashboard_url(component="algenta CLI")
    print("  For 100–1000× speedup on large workloads:")
    print("  → pip install algenta-sdk")
    if private_profile_enabled():
        print(f"  → {dashboard_url}")
        return
    print(f"  → {dashboard_url} (free tier: 500 simulations/month)")


def _bench_normal(n: int = 100_000) -> float:
    """Baseline Python: Box-Muller normal sampling."""
    t0 = time.perf_counter()
    for _ in range(n):
        u1 = random.random()  # noqa: S311 - benchmark intentionally measures fast local PRNG
        u2 = random.random()  # noqa: S311 - benchmark intentionally measures fast local PRNG
        math.sqrt(-2 * math.log(u1 + 1e-15)) * math.cos(2 * math.pi * u2)
    return (time.perf_counter() - t0) * 1000


def _bench_simulate(n: int = 100_000) -> float:
    """algenta.simulate local engine."""
    from algenta.simulate import _box_muller

    t0 = time.perf_counter()
    for _ in range(n):
        _box_muller(100000, 15000)
    return (time.perf_counter() - t0) * 1000


def _format_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms * 1000:.0f}µs"
    return f"{ms:.1f}ms"


def cmd_benchmark() -> None:
    n_samples = 50_000
    print("\n" + "─" * 58)
    print("  Algenta Core — Local Benchmark")
    print("─" * 58)
    print(f"  Sampling {n_samples:,} normal variates\n")

    python_ms = _bench_normal(n_samples)
    algenta_ms = _bench_simulate(n_samples)
    ratio = python_ms / (algenta_ms + 1e-9)

    print(f"  Python baseline:    {_format_ms(python_ms)}")
    print(f"  algenta-core:       {_format_ms(algenta_ms)}")
    print(f"\n  Speedup:            {ratio:.1f}×")
    print()

    if ratio >= 2:
        print(f"  algenta-core is {ratio:.1f}× faster than raw Python.")
    else:
        print("  Performance is similar — algenta advantage scales with")
        print("  problem size and when the Mojo backend is available.")

    print()
    _print_scale_guidance()
    print("─" * 58 + "\n")


def cmd_simulate_quick() -> None:
    from algenta.simulate import risk

    print("\nRunning quick simulation: revenue=100,000 cost=70,000 runs=10,000\n")
    t0 = time.perf_counter()
    result = risk(revenue=100000, cost=70000, runs=10000)
    ms = (time.perf_counter() - t0) * 1000
    print(f"  Expected outcome:   {result.expected_value:,.0f}")
    print(f"  Prob. of loss:      {result.probability_of_loss:.1%}")
    print(f"  Downside (p5):      {result.percentile_5:,.0f}")
    print(f"  Upside (p95):       {result.percentile_95:,.0f}")
    print(f"  Completed in:       {ms:.0f}ms  ({result.runs:,} scenarios)\n")
    print("  Scale to 1M+ scenarios: pip install algenta-sdk")
    print("  → client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)\n")


def cmd_demo(args: list[str]) -> None:
    from algenta.demo import main as demo_main

    raise SystemExit(demo_main(args))


def cmd_version() -> None:
    from algenta import __version__

    print()
    print(
        runtime_banner(
            f"algenta-core {__version__}",
            [
                "Primary path: Runtime.resolve() -> Runtime.query()",
                "Secondary modes: simulate, decision, optimize, forecast, map_data, query_data",
                "Cloud/API mode: install algenta-sdk or algenta-core[cloud]",
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
        key_help = api_key_help_text(
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

  2. {key_help}

  3. Install the SDK:
       pip install algenta-sdk
       # or
       pip install "algenta-core[cloud]"

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

  1. {api_key_help_text(component="algenta upgrade")}

  2. Install the SDK:
       pip install algenta-sdk
       # or
       pip install "algenta-core[cloud]"

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


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

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
    else:
        print(
            runtime_banner(
                "Algenta CLI",
                [
                    "Primary path: algenta demo",
                    "Brandable import preview: algenta import <file.csv> --name orders",
                    "Deterministic local runtime: Runtime.resolve() -> Runtime.query()",
                    "Secondary tools remain available: map, query, simulate, benchmark",
                ],
            )
        )
        print()
        print(__doc__)
        sys.exit(0 if cmd == "help" else 1)


if __name__ == "__main__":
    main()
