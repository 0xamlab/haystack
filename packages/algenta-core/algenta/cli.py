"""
algenta CLI — local benchmark, quick simulation, and cloud upgrade tool.

Usage:
  algenta benchmark              # show local speedup vs Python baseline
  algenta simulate               # run a quick local simulation
  algenta map file1.csv [file2]  # instantly map and join datasets
  algenta query "..." file.csv   # query any data in plain English
  algenta version                # show version and capabilities
  algenta upgrade                # show how to switch to cloud API
"""
from __future__ import annotations

import math
import random
import sys
import time


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
        return f"{ms*1000:.0f}µs"
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
    print("  For 100–1000× speedup on large workloads:")
    print("  → pip install algenta-sdk")
    print("  → algenta.ai/dashboard (free tier: 500 simulations/month)")
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


def cmd_version() -> None:
    from algenta import __version__
    print(f"\n  algenta-core {__version__}")
    print("  Local simulation engine — no API key required")
    print("  Functions: simulate, decision, optimize, forecast")
    print("  Upgrade:   pip install algenta-sdk   →  cloud API, 100× more scale\n")


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
        print("\n  Usage: algenta query \"<query>\" <file.csv> [file2.csv ...]\n")
        print("  Examples:")
        print("    algenta query \"total revenue by customer\" sales.csv")
        print("    algenta query \"top 10 orders by amount\" orders.csv\n")
        sys.exit(1)

    query_text = args[0]
    files = args[1:]

    from pathlib import Path

    from algenta.map import query_data

    missing = [f for f in files if not Path(f).exists()]
    if missing:
        print(f"\n  Error: file(s) not found: {', '.join(missing)}\n")
        sys.exit(1)

    print(f"\n  Query: \"{query_text}\"")
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
    print("  → client.query(\"...\", sources=[...])\n")


def cmd_upgrade() -> None:
    print("""
  Upgrade to Algenta Cloud
  ─────────────────────────

  1. Get a free API key at: https://algenta.ai/dashboard

  2. Install the SDK:
       pip install algenta-sdk

  3. Switch from local to cloud in one line:

     Before:
       from algenta import simulate
       result = simulate.risk(revenue=100000, cost=70000, runs=10000)

     After:
       from algenta import AlgentaClient
       client = AlgentaClient(api_key="de_live_...")
       result = client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)

  Free tier:  500 simulations/month
  Developer:  10,000 simulations/month
  Pro:        100,000 simulations/month + all engines
""")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd == "benchmark":
        cmd_benchmark()
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
        print(__doc__)
        sys.exit(0 if cmd == "help" else 1)


if __name__ == "__main__":
    main()
