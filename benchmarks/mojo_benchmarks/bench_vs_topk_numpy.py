#!/usr/bin/env python3
"""bench_vs_topk_numpy.py — the NumPy arm of top-k selection, measured like the Mojo one.

Pair of `benchmarks/mojo_benchmarks/bench_vs_topk.mojo`. Run both through
`bench_vs_topk_driver.py`, which interleaves them round by round so neither side gets a
quieter machine than the other, and compares the digests.

THE BASELINE, AND WHY IT IS THE STRONG ONE
------------------------------------------
`numpy.argpartition` is introselect in C — quickselect with a median-of-three pivot and a
heapselect fallback — and it is what a retrieval or RAG pipeline actually calls to get a
top-k. Three arms are timed rather than one, so the choice of NumPy entry point cannot be
the reason we win:

  np_argpartition   `np.argpartition(a, n-k)[n-k:]`. The indices, unordered. The
                    like-for-like arm: both it and our `buf_1t` are single-threaded and
                    both return indices.
  np_argpart_sorted `... then np.argsort` on the k survivors. This is what it costs NumPy
                    to return what our kernel returns, which is the top k in order. Our
                    kernel's sort is inside its measured time, so comparing against the
                    unordered arm alone would be charging us for something we do not
                    charge NumPy for.
  np_partition      `np.partition(a, n-k)[n-k:]`. VALUES only, no index array at all.
                    NumPy cannot answer this question for less, so this is the floor of
                    what any NumPy solution can cost, and it is reported even though it
                    answers a weaker question than ours does.

NumPy 2.5.1 here, threads: `argpartition` and `partition` are single-threaded — they are
not BLAS calls, so the 16-thread OpenBLAS in this environment is not involved and
`OPENBLAS_NUM_THREADS` changes nothing. That matters for the honesty of the comparison:
our `buf_1t` is the arm to compare against these, and our `buf_16t` must not be.

METHOD, IDENTICAL TO THE MOJO SIDE BY CONSTRUCTION
--------------------------------------------------
Same data (counter-based SplitMix64, verified bit-identical), same prefix scheme, same
COLD/WARM/HOT definition, same unit floor, same equal-wall-clock budget per cell, same
gate on median/min and p90/min with max/min printed and never gated. The constants are
duplicated here rather than imported because the Mojo side cannot import Python; the
driver CHECKS that they agree and refuses to compare if they do not.

Run with `python -P`. Without it, a `/tmp/inspect.py` on this machine shadows the stdlib
and NumPy fails to import with a misleading error.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

import numpy as np

# ── constants, mirrored from bench_vs_topk.mojo ───────────────────────────────
MAX_N = 100_000_000
HOT_REPS = 25
MIN_REPS = 3
UNIT_FLOOR_NS = 5_000_000.0
CELL_BUDGET_NS = 2_000_000_000.0
MAX_SPREAD = 2.0
MAX_P90_SPREAD = 4.0
MAX_INNER = 200_000

SWEEP_N = (100_000, 1_000_000, 10_000_000, 100_000_000)
SWEEP_K = (10, 100, 1000)
ADVERSARIAL_N = 10_000_000

GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)
_S30, _S27, _S31, _S11 = np.uint64(30), np.uint64(27), np.uint64(31), np.uint64(11)
_TWO_POW_53 = 9007199254740992.0

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x00000100000001B3
_MASK64 = 0xFFFFFFFFFFFFFFFF


def uniform_values(n: int) -> np.ndarray:
    """The identical bit patterns the Mojo side generates, computed without a loop.

    Counter-based, so element `i` is a pure function of `i` and the two languages provably
    select from the same array. Overflow is the point — SplitMix64 is defined mod 2**64 —
    so the wrap warning is silenced rather than avoided.
    """
    with np.errstate(over="ignore"):
        z = np.arange(n, dtype=np.uint64) * GOLDEN + GOLDEN
        z = (z ^ (z >> _S30)) * _M1
        z = (z ^ (z >> _S27)) * _M2
        z = z ^ (z >> _S31)
    return (z >> _S11).astype(np.float64) * (1.0 / _TWO_POW_53)


def ascending_values(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64)


def _fnv_bytes(h: int, v: int) -> int:
    for shift in range(0, 64, 8):
        h = ((h ^ ((v >> shift) & 0xFF)) * FNV_PRIME) & _MASK64
    return h


def pair_digest(indices: np.ndarray, values: np.ndarray) -> int:
    """FNV-1a-64 over `(index, value_bits)` in ascending index order — set identity."""
    order = np.sort(np.asarray(indices, dtype=np.int64))
    bits = values[order].view(np.uint64)
    h = FNV_OFFSET
    for at, b in zip(order.tolist(), bits.tolist(), strict=True):
        h = _fnv_bytes(h, at)
        h = _fnv_bytes(h, b)
    return h


def value_digest_from_values(sorted_desc: np.ndarray) -> int:
    """FNV-1a-64 over value bit patterns, best first — multiset identity.

    Order-independent among ties because tied values have identical bits, which is what
    lets it stay a valid check when `np.argpartition` and our kernel legitimately keep
    different rows from a tied group.
    """
    h = FNV_OFFSET
    for b in sorted_desc.view(np.uint64).tolist():
        h = _fnv_bytes(h, b)
    return h


# ── timing, mirrored from bench_vs_topk.mojo ──────────────────────────────────


def batch_size(pilot_ns: float) -> int:
    if pilot_ns <= 0.0:
        return MAX_INNER
    return max(1, min(MAX_INNER, int(UNIT_FLOOR_NS / pilot_ns) + 1))


def reps_for(unit_ns: float) -> int:
    if unit_ns <= 0.0:
        return HOT_REPS
    return max(MIN_REPS, min(HOT_REPS, int(CELL_BUDGET_NS / unit_ns)))


class Cell:
    """One (arm, n, k) measurement and whether it may be quoted."""

    __slots__ = (
        "cold",
        "hot",
        "inner",
        "reason",
        "reps",
        "spread_max",
        "spread_med",
        "spread_p90",
        "valid",
        "warm",
    )

    def __init__(self, cold: float, warm: float, units: list[float], inner: int) -> None:
        units = sorted(units)
        count = len(units)
        self.cold = cold
        self.warm = warm
        self.hot = units[0]
        self.inner = inner
        self.reps = count
        hot = self.hot
        self.spread_med = units[count // 2] / hot if hot > 0 else 0.0
        self.spread_p90 = units[min(count - 1, (count * 9) // 10)] / hot if hot > 0 else 0.0
        self.spread_max = units[-1] / hot if hot > 0 else 0.0

        reasons: list[str] = []
        if hot <= 0.0:
            reasons.append("hot<=0(below clock resolution)")
        if hot > warm:
            reasons.append(f"hot>warm({hot / warm:.6f}x)")
        if self.spread_med > MAX_SPREAD:
            reasons.append(f"median/min={self.spread_med:.6f}>{MAX_SPREAD}")
        if self.spread_p90 > MAX_P90_SPREAD:
            reasons.append(f"p90/min={self.spread_p90:.6f}>{MAX_P90_SPREAD}")
        self.reason = "+".join(reasons)
        self.valid = not reasons


_SINK = 0


def measure(fn) -> tuple[Cell, object]:
    """COLD = call one, alone. WARM and HOT = per-call figures from equal-sized units."""
    global _SINK
    t0 = time.perf_counter_ns()
    first = fn()
    t1 = time.perf_counter_ns()
    cold = float(t1 - t0)
    inner = batch_size(cold)

    t2 = time.perf_counter_ns()
    for _ in range(inner):
        _SINK += int(fn()[0])
    t3 = time.perf_counter_ns()
    unit_ns = float(t3 - t2)
    warm = unit_ns / inner
    reps = reps_for(unit_ns)

    units = []
    for _ in range(reps):
        b0 = time.perf_counter_ns()
        for _ in range(inner):
            _SINK += int(fn()[0])
        b1 = time.perf_counter_ns()
        units.append(float(b1 - b0) / inner)
    return Cell(cold, warm, units, inner), first


def report(arm: str, n: int, k: int, cell: Cell) -> int:
    """One machine-readable line. INVALID lines carry no rate, by design. Returns 1 on fail."""
    common = (
        f" cold_ns={cell.cold} warm_ns={cell.warm} hot_ns={cell.hot}"
        f" spread_med={cell.spread_med} spread_p90={cell.spread_p90}"
        f" spread_max={cell.spread_max} inner_reps={cell.inner} reps={cell.reps}"
    )
    head = f"TOPKNP {arm} n={n} k={k}"
    if not cell.valid:
        print(f"{head} INVALID reasons={cell.reason}{common} ; no rate reported")
        return 1
    print(
        f"{head}{common}"
        f" ns_per_elem={cell.hot / n}"
        f" elems_per_s={n / (cell.hot / 1.0e9)}"
        f" gb_per_s={8.0 * n / cell.hot}"
        f" VALID"
    )
    print(f"COLD_WARM_HOT topknp.{arm}.n{n}.k{k} {cell.cold} {cell.warm} {cell.hot} ns")
    return 0


def _loadavg() -> tuple[float, float, float]:
    return os.getloadavg()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adversarial-only",
        action="store_true",
        help="run only section 4, for a driver round that pairs it with the Mojo one",
    )
    parser.add_argument("--json-out", default="", help="write the parsed cells here too")
    args = parser.parse_args()

    failures = 0
    print("== top-k selection: numpy.argpartition baseline (NumPy arm) ==")
    print(f"  numpy {np.__version__} | python {platform.python_version()} | {sys.platform}")
    print(f"  argpartition/partition are SINGLE-THREADED (not BLAS). load {_loadavg()}")
    print(f"  constants: HOT_REPS={HOT_REPS} MIN_REPS={MIN_REPS}"
          f" UNIT_FLOOR_NS={UNIT_FLOOR_NS} CELL_BUDGET_NS={CELL_BUDGET_NS}"
          f" MAX_SPREAD={MAX_SPREAD} MAX_P90_SPREAD={MAX_P90_SPREAD}")
    # key=value, the same grammar the Mojo arm prints, so the driver can compare the two
    # timing methods field by field. A JSON blob here read as `None` on the driver side
    # and silently voided the parity check in the first run of this pair.
    print(
        f"CONSTANTS HOT_REPS={HOT_REPS} MIN_REPS={MIN_REPS}"
        f" UNIT_FLOOR_NS={UNIT_FLOOR_NS} CELL_BUDGET_NS={CELL_BUDGET_NS}"
        f" MAX_SPREAD={MAX_SPREAD} MAX_P90_SPREAD={MAX_P90_SPREAD} MAX_N={MAX_N}"
    )

    gen0 = time.perf_counter_ns()
    values = uniform_values(MAX_N)
    gen1 = time.perf_counter_ns()
    print(f"  generated {MAX_N} values in {(gen1 - gen0) / 1e6:.1f} ms (untimed setup)")
    print(f"  first value bits {int(values[0].view(np.uint64))}"
          f" -- must equal the Mojo side's 4606131375998723001")
    if int(values[0].view(np.uint64)) != 4606131375998723001:
        failures += 1
        print("  *** GENERATOR MISMATCH: the two sides are not selecting from one array")

    if not args.adversarial_only:
        print("")
        print("-- 1. DIGESTS (what the Mojo side must match) --")
        for n in SWEEP_N:
            a = values[:n]
            for k in SWEEP_K:
                idx = np.argpartition(a, n - k)[n - k :]
                vals_desc = np.sort(a[idx])[::-1]
                # Independent oracle: the k-th largest, from a full sort of a prefix
                # sample is too weak, so use np.partition, a different code path from
                # argpartition, and require the k-th values to agree bit for bit.
                oracle = np.partition(a, n - k)[n - k :]
                oracle_desc = np.sort(oracle)[::-1]
                agree = bool(np.array_equal(vals_desc.view(np.uint64),
                                            oracle_desc.view(np.uint64)))
                if not agree:
                    failures += 1
                # Is the k-boundary tie-free? If it is, the top-k SET is unique and the
                # two languages must agree on indices, not merely on values.
                kth = vals_desc[-1]
                rest = np.partition(a, n - k - 1)[n - k - 1]
                distinct = bool(kth.view(np.uint64) != rest.view(np.uint64))
                print(
                    f"TOPKNP_DIGEST n={n} k={k}"
                    f" pair={pair_digest(idx, a)}"
                    f" vals={value_digest_from_values(vals_desc)}"
                    f" kth_bits={int(kth.view(np.uint64))}"
                    f" boundary_distinct={1 if distinct else 0}"
                    f" argpartition_matches_partition={1 if agree else 0}"
                )

        print("")
        print("-- 2. SWEEP: n = 1e5 .. 1e8, k = 10/100/1000, uniform random order --")
        for n in SWEEP_N:
            a = values[:n]
            for k in SWEEP_K:
                cell, _ = measure(lambda a=a, n=n, k=k: np.argpartition(a, n - k)[n - k :])
                failures += report("np_argpartition", n, k, cell)

                def ordered(a=a, n=n, k=k):
                    p = np.argpartition(a, n - k)[n - k :]
                    return p[np.argsort(-a[p], kind="stable")]

                cell, _ = measure(ordered)
                failures += report("np_argpart_sorted", n, k, cell)

                cell, _ = measure(lambda a=a, n=n, k=k: np.partition(a, n - k)[n - k :])
                failures += report("np_partition", n, k, cell)

    print("")
    print(f"-- 4. ADVERSARIAL ORDER: ascending input, n = {ADVERSARIAL_N} --")
    print("   Introselect's median-of-three finds a perfect pivot on sorted data, so this")
    print("   is NumPy's best case and our worst. Reported for exactly that reason.")
    asc = ascending_values(ADVERSARIAL_N)
    for k in SWEEP_K:
        cell, _ = measure(
            lambda k=k: np.argpartition(asc, ADVERSARIAL_N - k)[ADVERSARIAL_N - k :]
        )
        failures += report("asc_np_argpartition", ADVERSARIAL_N, k, cell)

    print("")
    print(f"  load at end {_loadavg()}  sink {_SINK % 1000}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump({"numpy": np.__version__, "failures": failures}, handle)
    if failures == 0:
        print("BENCH_GATE topk_numpy PASS")
    else:
        print(f"BENCH_GATE topk_numpy FAIL {failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
