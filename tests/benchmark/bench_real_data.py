"""
bench_real_data.py — Real-data integration test.

Tests the full pipeline: CSV files → FileConnector → auto-map → Mojo engine → results.
Uses actual data from test_files/ directory.

Usage:
    python -m tests.benchmark.bench_real_data
    make bench-real-data
"""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BINARY = Path("mojo_build/simulate")
TEST_FILES = Path("test_files")

# Maximum rows to analyze per CSV (keeps large files fast)
MAX_ROWS = 500
# Maximum variables to send to the engine (avoid giant expression trees)
MAX_VARS = 10


def _summarize_distributions(variables: list[dict[str, Any]]) -> dict[str, int]:
    """Count how many variables use each distribution type."""
    counts: dict[str, int] = {}
    for v in variables:
        d = v.get("distribution", "unknown")
        counts[d] = counts.get(d, 0) + 1
    return counts


async def test_csv_pipeline(csv_path: str, description: str) -> bool | None:
    """Test full pipeline: CSV → connector → auto-map → simulate → verify.

    Returns True on pass, False on failure, None on skip.
    """
    from apps.api_server.connectors.file_connector import FileConnector

    print(f"\n  [{description}] {csv_path}")

    # ── 1. Locate file ──────────────────────────────────────────────────
    path = TEST_FILES / csv_path
    if not path.exists():
        print(f"    ⚠️  File not found: {path}")
        return None

    file_size_kb = path.stat().st_size / 1024
    print(f"    File size: {file_size_kb:.0f} KB")

    # ── 2. Read CSV via FileConnector ────────────────────────────────────
    connector = FileConnector({
        "file_type": "csv",
        "file_path": str(path),
    })

    t0 = time.perf_counter()
    try:
        data = await connector.fetch_data()
    except Exception as e:
        print(f"    ❌ Parse failed: {e}")
        return False

    parse_ms = (time.perf_counter() - t0) * 1000

    if not data:
        print("    ⚠️  No data rows")
        return None

    total_records = len(data)
    # Sub-sample for mapping speed on large files
    sample_data = data[:MAX_ROWS]
    print(f"    Records: {total_records} (analyzing first {len(sample_data)})")
    print(f"    Parse time: {parse_ms:.1f} ms")

    # ── 3. Field analysis ────────────────────────────────────────────────
    sample = sample_data[0]
    all_fields = list(sample.keys())
    numeric_fields = [k for k, v in sample.items() if isinstance(v, (int, float))]
    string_fields = [k for k in all_fields if k not in numeric_fields]

    print(f"    Total fields: {len(all_fields)}")
    print(f"    Numeric fields ({len(numeric_fields)}): {', '.join(numeric_fields[:8])}"
          f"{'...' if len(numeric_fields) > 8 else ''}")

    if len(numeric_fields) < 2:
        print("    ⚠️  Not enough numeric fields for meaningful simulation")
        return None

    # ── 4. Auto-map to simulation payload ────────────────────────────────
    t0 = time.perf_counter()
    payload = await connector.map_to_simulation(sample_data)
    map_ms = (time.perf_counter() - t0) * 1000

    variables = payload.get("variables", [])
    obj_fn = payload.get("objective_function", "")

    print(f"    Map time: {map_ms:.1f} ms")
    print(f"    Variables mapped: {len(variables)}")

    # Show distribution breakdown
    dist_counts = _summarize_distributions(variables)
    dist_str = ", ".join(f"{d}={n}" for d, n in sorted(dist_counts.items()))
    print(f"    Distributions: {dist_str}")

    # Show variable details (first few)
    for v in variables[:5]:
        p = v.get("params", {})
        p_str = ", ".join(f"{k}={val:.2f}" if isinstance(val, float) else f"{k}={val}"
                          for k, val in p.items())
        print(f"      • {v['name']:30s}  {v['distribution']:12s}  ({p_str})")
    if len(variables) > 5:
        print(f"      ... and {len(variables) - 5} more")

    print(f"    Objective: {obj_fn[:100]}{'...' if len(obj_fn) > 100 else ''}")

    if not variables:
        print("    ⚠️  No variables mapped — nothing to simulate")
        return None

    # ── 5. Trim variables for engine limits ──────────────────────────────
    if len(variables) > MAX_VARS:
        payload["variables"] = variables[:MAX_VARS]
        # Rebuild objective with limited variable set
        var_names = [v["name"] for v in payload["variables"]]
        # Separate positive/negative polarity based on original objective
        pos_names = [n for n in var_names if f"- {n}" not in obj_fn]
        neg_names = [n for n in var_names if f"- {n}" in obj_fn]
        if pos_names and neg_names:
            payload["objective_function"] = " + ".join(pos_names) + " - " + " - ".join(neg_names)
        elif pos_names:
            payload["objective_function"] = " + ".join(pos_names)
        else:
            payload["objective_function"] = " + ".join(var_names)
        print(f"    (trimmed to {MAX_VARS} vars for engine)")

    # ── 6. Run through Mojo engine ───────────────────────────────────────
    payload["runs"] = 5000
    payload_json = json.dumps(payload)
    payload_kb = len(payload_json) / 1024
    print(f"    Payload size: {payload_kb:.1f} KB")

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [str(BINARY)],
            input=payload_json.encode(),
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("    ❌ Engine timed out (>30s)")
        return False

    engine_ms = (time.perf_counter() - t0) * 1000

    if result.returncode != 0:
        print(f"    ❌ Engine failed (exit {result.returncode})")
        stderr = result.stderr.decode(errors="replace")[:300]
        if stderr:
            print(f"    stderr: {stderr}")
        return False

    # ── 7. Parse and validate output ─────────────────────────────────────
    stdout = result.stdout.decode(errors="replace").strip()
    # Engine may emit debug lines; JSON is the last line
    lines = stdout.split("\n")
    json_line = lines[-1]

    try:
        output = json.loads(json_line)
    except (json.JSONDecodeError, IndexError) as e:
        print(f"    ❌ Invalid JSON output: {e}")
        if len(stdout) < 500:
            print(f"    stdout: {stdout}")
        return False

    summary = output.get("summary", {})
    mean = summary.get("mean", 0)
    std = summary.get("std", 0)
    score = output.get("score", -1)
    engine_version = output.get("engine_version", "?")
    engine_type = output.get("engine_type", "?")
    scenarios_run = output.get("scenarios_run", 0)
    has_histogram = bool(output.get("histogram_data"))
    has_cdf = bool(output.get("cdf_data"))
    result_hash = output.get("result_hash", "")

    print(f"    Engine: {engine_version} ({engine_type})  ({engine_ms:.0f} ms)")
    print(f"    Result: mean={mean:,.2f}  std={std:,.2f}  score={score:.4f}")
    print(f"    Scenarios: {scenarios_run}  histogram={has_histogram}  cdf={has_cdf}")
    if result_hash:
        print(f"    Hash: {result_hash[:16]}...")

    # ── 8. Assertions ────────────────────────────────────────────────────
    errors = []
    if score < 0 or score > 1:
        errors.append(f"score {score:.4f} out of [0,1] range")
    if std < 0:
        errors.append(f"negative std: {std}")
    if scenarios_run == 0:
        errors.append("no scenarios were run")

    if errors:
        for err in errors:
            print(f"    ❌ {err}")
        return False

    print("    ✅ PASS")
    return True


async def main() -> None:
    if not BINARY.exists():
        print(f"❌ Binary not found at {BINARY}. Run: make build-mojo")
        sys.exit(1)

    if not TEST_FILES.exists():
        print("❌ test_files/ directory not found")
        sys.exit(1)

    print("━" * 60)
    print("  Real-Data Integration Test")
    print("  CSV files → FileConnector → auto-map → Mojo engine")
    print("━" * 60)
    print(f"  Binary : {BINARY}")
    print(f"  Data   : {TEST_FILES}")
    print(f"  Max rows/file : {MAX_ROWS}")
    print(f"  Max vars/sim  : {MAX_VARS}")

    # Test cases: (filename, description)
    test_cases = [
        ("bookings_new.csv", "Bookings (new)"),
        ("pos_new.csv", "Point of Sale (new)"),
        ("quotes_new.csv", "Quotes (new)"),
        ("Available_Inventory.csv", "Available Inventory"),
        ("Backlog.csv", "Backlog"),
        ("Bookings.csv", "Bookings (full)"),
        ("POS.csv", "POS (full)"),
    ]

    passed = 0
    failed = 0
    skipped = 0
    total_start = time.perf_counter()

    for csv_file, desc in test_cases:
        try:
            result = await test_csv_pipeline(csv_file, desc)
            if result is True:
                passed += 1
            elif result is False:
                failed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"    ❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    total_ms = (time.perf_counter() - total_start) * 1000

    print()
    print("━" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"  Total time: {total_ms:.0f} ms")
    print("━" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
