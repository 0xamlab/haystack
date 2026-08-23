"""summarize_cells.py — aggregate official max-benchmark sonnet cells into race tables.

Reads ~/maxbench/results/<cell>_<variant>/run_NN.json (max benchmark --result-filename
output), computes per-cell medians + relative IQR across runs for the headline metric set,
and applies the campaign honesty rules:

  * 20 runs/cell target; median is the headline
  * relative IQR = (p75-p25)/median, tolerance <= 5%
  * runs deviating >10% from the median are flagged outliers and excluded ONLY if >=16/20
    remain; verdicts are reported, never adjusted

Usage: python3 summarize_cells.py [results-root]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

# JSON result paths (max 26.5 BenchmarkResult schema — flat top-level keys).
KEYS = {
    "duration_s": ("duration",),
    "completed": ("completed",),
    "failures": ("failures",),
    "req_throughput": ("request_throughput",),
    "mean_ttft_ms": ("mean_ttft_ms",),
    "p99_ttft_ms": ("p99_ttft_ms",),
    "mean_tpot_ms": ("mean_tpot_ms",),
    "p99_tpot_ms": ("p99_tpot_ms",),
    "mean_itl_ms": ("mean_itl_ms",),
    "mean_e2e_ms": ("mean_latency_ms",),
    "median_e2e_ms": ("median_latency_ms",),
    "p99_e2e_ms": ("p99_latency_ms",),
    "mean_in_tok_thru": ("mean_input_throughput",),
    "mean_out_tok_thru": ("mean_output_throughput",),
    "cached_tok_rate": ("global_cached_token_rate",),
}


def dig(obj: dict, path: tuple[str, ...]):
    cur = obj
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def rel_iqr(vals: list[float]) -> float:
    if len(vals) < 4:
        return float("nan")
    med = statistics.median(vals)
    q = statistics.quantiles(vals, n=4)
    return (q[2] - q[0]) / med if med else float("nan")


def main(root: str) -> None:
    root_p = Path(root)
    for cell_dir in sorted(root_p.iterdir()):
        if not cell_dir.is_dir():
            continue
        runs = []
        for f in sorted(cell_dir.glob("run_*.json")):
            try:
                with open(f) as fh:
                    runs.append(json.load(fh))
            except (json.JSONDecodeError, OSError) as e:
                print(f"  !! {f.name}: unreadable ({e})")
        if not runs:
            print(f"{cell_dir.name}: NO RESULTS")
            continue
        print(f"\n=== {cell_dir.name} (N={len(runs)}) ===")
        failed = [dig(r, KEYS['failures']) for r in runs]
        failed = [f for f in failed if f]
        if failed:
            print(f"  !! failed requests in runs: {failed}")
        for name, path in KEYS.items():
            vals = [dig(r, path) for r in runs]
            vals = [v for v in vals if isinstance(v, (int, float))]
            if not vals:
                print(f"  {name}: MISSING (path {path})")
                continue
            med = statistics.median(vals)
            iq = rel_iqr(vals)
            outliers = [v for v in vals if abs(v - med) > 0.10 * med]
            flag = "" if iq != iq or iq <= 0.05 else "  <-- IQR > 5%"
            print(f"  {name:22s} median={med:12.3f} relIQR={iq * 100:6.2f}% "
                  f"outliers>10%={len(outliers)}{flag}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/home/angel/maxbench/results")
