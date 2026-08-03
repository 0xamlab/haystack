"""depth_bucket_compare.py — the FULL depth-range self-comparison this task's own report relies on:
buckets each arm's own per-step `generated_ids.txt` timing (already recorded by every
`qwen3_generate_batch_i8_allsimd*_longctx_probe.mojo` run, column 5, `step_ms`, real wall time per
`step()` call, no GPU counters needed) by `n_keys` depth range, at the SAME bucket boundaries the
calibration sweep used (`benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_splitk_native_sweep.
mojo`'s own 8 depth buckets plus the dead-zone extension), and reports mean per-step ms for
`_MBQwen3I8AllSimd3` (original two-level kernel), `_MBQwen3I8AllSimd6` (fixed `n_splits=80`) and
`_MBQwen3I8AllSimd7` (this task's own dynamic, per-step policy) side by side in each bucket — this is
what actually answers whether "dynamic, calibrated" beats "one well-tuned fixed value" in practice,
across the WHOLE range a real generation passes through, not at one depth alone.

Usage:
    python3 depth_bucket_compare.py <allsimd3_generated_ids.txt> <allsimd6_generated_ids.txt> \\
        <allsimd7_generated_ids.txt>
"""
import sys
from pathlib import Path

BUCKETS = [
    (1, 31, "dead-zone (unsplit, n_keys<32)"),
    (32, 127, "32-127 (shallow split)"),
    (128, 255, "128-255"),
    (256, 499, "256-499"),
    (500, 749, "500-749"),
    (750, 999, "750-999"),
    (1000, 1999, "1000-1999"),
    (2000, 3999, "2000-3999"),
    (4000, 10 ** 9, "4000+"),
]


def load(path: str):
    lines = Path(path).read_text().splitlines()
    n_prompt = int(lines[0].split()[1])
    n_generated = int(lines[1].split()[1])
    steps = []
    for line in lines[3:3 + n_generated]:
        parts = line.split()
        pos = int(parts[1])
        tok_id = int(parts[2])
        step_ms = float(parts[4])
        n_keys = pos + 1
        steps.append((n_keys, tok_id, step_ms))
    return n_prompt, steps


def bucket_stats(steps):
    out = {}
    for lo, hi, label in BUCKETS:
        vals = [ms for (n_keys, _tok, ms) in steps if lo <= n_keys <= hi]
        if vals:
            out[label] = (len(vals), sum(vals) / len(vals), min(vals), max(vals))
        else:
            out[label] = (0, 0.0, 0.0, 0.0)
    return out


def main() -> int:
    path_a3, path_a6, path_a7 = sys.argv[1], sys.argv[2], sys.argv[3]
    _, steps_a3 = load(path_a3)
    _, steps_a6 = load(path_a6)
    _, steps_a7 = load(path_a7)

    ids_a3 = [t for (_, t, _) in steps_a3]
    ids_a6 = [t for (_, t, _) in steps_a6]
    ids_a7 = [t for (_, t, _) in steps_a7]
    n = min(len(ids_a3), len(ids_a6), len(ids_a7))
    mism_36 = sum(1 for i in range(n) if ids_a3[i] != ids_a6[i])
    mism_37 = sum(1 for i in range(n) if ids_a3[i] != ids_a7[i])
    mism_67 = sum(1 for i in range(n) if ids_a6[i] != ids_a7[i])
    print(f"correctness over {n} compared steps: A3-vs-A6 mismatches={mism_36}  "
          f"A3-vs-A7 mismatches={mism_37}  A6-vs-A7 mismatches={mism_67}")
    print()

    stats_a3 = bucket_stats(steps_a3)
    stats_a6 = bucket_stats(steps_a6)
    stats_a7 = bucket_stats(steps_a7)

    header = f"{'bucket':32s} {'n':>5s}  {'A3 mean ms':>11s}  {'A6 mean ms':>11s}  {'A7 mean ms':>11s}  {'A7 vs A3':>9s}  {'A7 vs A6':>9s}"
    print(header)
    print("-" * len(header))
    total_ms_a3 = 0.0
    total_ms_a6 = 0.0
    total_ms_a7 = 0.0
    total_n = 0
    for lo, hi, label in BUCKETS:
        n3, m3, _, _ = stats_a3[label]
        n6, m6, _, _ = stats_a6[label]
        n7, m7, _, _ = stats_a7[label]
        if n7 == 0:
            continue
        speedup_37 = m3 / m7 if m7 > 0 else float("nan")
        speedup_67 = m6 / m7 if m7 > 0 else float("nan")
        print(f"{label:32s} {n7:5d}  {m3:11.4f}  {m6:11.4f}  {m7:11.4f}  {speedup_37:8.3f}x  {speedup_67:8.3f}x")
        total_ms_a3 += m3 * n3
        total_ms_a6 += m6 * n6
        total_ms_a7 += m7 * n7
        total_n += n7

    print()
    print(f"whole-run decode tok/s: A3={total_n / (total_ms_a3 / 1000.0):.2f}  "
          f"A6={total_n / (total_ms_a6 / 1000.0):.2f}  A7(dynamic)={total_n / (total_ms_a7 / 1000.0):.2f}")
    print(f"whole-run mean step ms: A3={total_ms_a3/total_n:.4f}  A6={total_ms_a6/total_n:.4f}  A7={total_ms_a7/total_n:.4f}")
    return 0 if (mism_36 == 0 and mism_37 == 0 and mism_67 == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
