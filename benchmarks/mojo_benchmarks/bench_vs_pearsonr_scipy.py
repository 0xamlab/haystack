#!/usr/bin/env python3
"""bench_vs_pearsonr_scipy.py — the scipy arm of pearson_r, measured like the Mojo one.

Pair of `benchmarks/mojo_benchmarks/bench_vs_pearsonr.mojo`. Run both through
`bench_vs_pearsonr_driver.py`, which interleaves them round by round and compares the
fingerprints, `r`, and `p_value`.

Runs under plain `python3` (not the `mojo_env` pixi environment, which has numpy but not
scipy) -- `benchmarks/crn_analytic_reference.py`'s "scipy is not importable" note is about
that separate pixi environment, used only to compile/run Mojo, and does not apply here.

THE BASELINE
------------
`scipy.stats.pearsonr` -- the function `stat_tests.mojo`'s own docstring names as what it
replaces ("Replaces: ... pearsonr"). scipy 1.14.1's implementation computes `r` the same
way (`cov(x,y) / sqrt(var(x)*var(y))`, in double precision) but gets its p-value from the
BETA DISTRIBUTION's survival function via `scipy.special.betainc` / `betaincinv`-adjacent
machinery -- real, independently-tested incomplete-beta code. `stat_tests.mojo`'s own
`_regularized_incomplete_beta` USED TO be verified wrong against `scipy.special.betainc`
directly (e.g. `betainc(4,4,0.5)` had to be 0.5 by symmetry and returned -0.099) and is
fixed as of this session (see that module's `_betacf`). The driver's `p_value` comparison
is gated now for exactly that reason -- see its own docstring for the one carve-out (mojo's
direct formula underflowing to 0.0 before scipy's does, for an already-negligible
p-value).

METHOD, IDENTICAL TO THE MOJO SIDE BY CONSTRUCTION
---------------------------------------------------
Same data (two independent counter-based SplitMix64 streams, verified bit-identical via
fingerprint), same prefix scheme, same COLD/WARM/HOT definition, same unit floor, same
equal-wall-clock budget per cell, same gate on median/min and p90/min. The constants are
duplicated here rather than imported because the Mojo side cannot import Python; the
driver checks that they agree and refuses to compare if they do not.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time

import numpy as np
from scipy import stats

# ── constants, mirrored from bench_vs_pearsonr.mojo ───────────────────────────
MAX_N = 10_000_000
HOT_REPS = 25
MIN_REPS = 3
UNIT_FLOOR_NS = 5_000_000.0
CELL_BUDGET_NS = 2_000_000_000.0
MAX_SPREAD = 2.0
MAX_P90_SPREAD = 4.0
MAX_INNER = 2_000_000

SWEEP_N = (1_000, 10_000, 100_000, 1_000_000, 10_000_000)
# 10 and 100 are extra, untimed sizes for the correctness section only -- see
# bench_vs_pearsonr.mojo's matching comment for why they are the sizes that make the
# incomplete-beta bug show as a clean disagreement rather than "both sides underflowed."
CORRECTNESS_N = (10, 100) + SWEEP_N

GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)
_S30, _S27, _S31, _S11 = np.uint64(30), np.uint64(27), np.uint64(31), np.uint64(11)
_TWO_POW_53 = 9007199254740992.0

_MASK64 = 0xFFFFFFFFFFFFFFFF


def _splitmix64_vec(counters: np.ndarray) -> np.ndarray:
    """The identical bit patterns bench_vs_pearsonr.mojo's `splitmix64` computes, no loop."""
    with np.errstate(over="ignore"):
        z = counters * GOLDEN + GOLDEN
        z = (z ^ (z >> _S30)) * _M1
        z = (z ^ (z >> _S27)) * _M2
        z = z ^ (z >> _S31)
    return z


def gen_pair(n: int) -> tuple[np.ndarray, np.ndarray]:
    """`x[i]` from counter `2i`, `noise[i]` from counter `2i+1` -- disjoint by construction,
    matching `bench_vs_pearsonr.mojo`'s `gen_pair` bit for bit."""
    idx = np.arange(n, dtype=np.uint64)
    x_bits = _splitmix64_vec(2 * idx)
    n_bits = _splitmix64_vec(2 * idx + np.uint64(1))
    x = (x_bits >> _S11).astype(np.float64) * (1.0 / _TWO_POW_53)
    noise = (n_bits >> _S11).astype(np.float64) * (1.0 / _TWO_POW_53)
    y = 0.6 * x + 0.4 * noise
    return x, y


def fingerprint(a: np.ndarray) -> int:
    """XOR fingerprint of the raw bit patterns -- must match the Mojo side's.

    Vectorised (`np.bitwise_xor.reduce`), not a Python loop: at MAX_N = 1e7 a per-element
    Python loop would itself take seconds, which is a needless cost for a correctness
    check unrelated to the timed comparison below it.
    """
    u = np.ascontiguousarray(a).view(np.uint64)
    return int(np.bitwise_xor.reduce(u)) & _MASK64


def bits_of(v: float) -> int:
    return int(np.float64(v).view(np.uint64))


# ── timing, mirrored from bench_vs_pearsonr.mojo ──────────────────────────────


def batch_size(pilot_ns: float) -> int:
    if pilot_ns <= 0.0:
        return MAX_INNER
    return max(1, min(MAX_INNER, int(UNIT_FLOOR_NS / pilot_ns) + 1))


def reps_for(unit_ns: float) -> int:
    if unit_ns <= 0.0:
        return HOT_REPS
    return max(MIN_REPS, min(HOT_REPS, int(CELL_BUDGET_NS / unit_ns)))


class Cell:
    __slots__ = (
        "cold", "warm", "hot", "inner", "reps",
        "spread_med", "spread_p90", "spread_max", "valid", "reason",
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


_SINK = 0.0


def measure(fn) -> Cell:
    """COLD = call one, alone. WARM and HOT = per-call figures from equal-sized units."""
    global _SINK
    t0 = time.perf_counter_ns()
    r0, _p0 = fn()
    t1 = time.perf_counter_ns()
    cold = float(t1 - t0)
    inner = batch_size(cold)

    t2 = time.perf_counter_ns()
    for _ in range(inner):
        r, _p = fn()
        _SINK += float(r)
    t3 = time.perf_counter_ns()
    unit_ns = float(t3 - t2)
    warm = unit_ns / inner
    reps = reps_for(unit_ns)

    units = []
    for _ in range(reps):
        b0 = time.perf_counter_ns()
        for _ in range(inner):
            r, _p = fn()
            _SINK += float(r)
        b1 = time.perf_counter_ns()
        units.append(float(b1 - b0) / inner)
    return Cell(cold, warm, units, inner)


def report(n: int, cell: Cell) -> int:
    common = (
        f" cold_ns={cell.cold} warm_ns={cell.warm} hot_ns={cell.hot}"
        f" spread_med={cell.spread_med} spread_p90={cell.spread_p90}"
        f" spread_max={cell.spread_max} inner_reps={cell.inner} reps={cell.reps}"
    )
    head = f"PEARSONRSCIPY pearsonr n={n}"
    if not cell.valid:
        print(f"{head} INVALID reasons={cell.reason}{common} ; no rate reported")
        return 1
    print(f"{head}{common} ns_per_elem={cell.hot / n} elems_per_s={n / (cell.hot / 1.0e9)} VALID")
    print(f"COLD_WARM_HOT pearsonr.scipy.n{n} {cell.cold} {cell.warm} {cell.hot} ns")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    failures = 0
    print("== pearson_r: scipy.stats.pearsonr baseline (scipy arm) ==")
    print(f"  scipy {__import__('scipy').__version__} | numpy {np.__version__}"
          f" | python {platform.python_version()} | {sys.platform}")
    print(f"  load {os.getloadavg()}")
    print(
        f"CONSTANTS HOT_REPS={HOT_REPS} MIN_REPS={MIN_REPS}"
        f" UNIT_FLOOR_NS={UNIT_FLOOR_NS} CELL_BUDGET_NS={CELL_BUDGET_NS}"
        f" MAX_SPREAD={MAX_SPREAD} MAX_P90_SPREAD={MAX_P90_SPREAD} MAX_N={MAX_N}"
    )

    gen0 = time.perf_counter_ns()
    x_full, y_full = gen_pair(MAX_N)
    gen1 = time.perf_counter_ns()
    print(f"  generated {MAX_N} pairs in {(gen1 - gen0) / 1e6:.1f} ms (untimed setup)")
    print("")

    print("-- 1. CORRECTNESS: fingerprints and r/p_value, what the Mojo side must match --")
    for n in CORRECTNESS_N:
        px = x_full[:n]
        py = y_full[:n]
        fx = fingerprint(px)
        fy = fingerprint(py)
        r, p = stats.pearsonr(px, py)
        print(
            f"PEARSONRSCIPY_DIGEST n={n} fx={fx} fy={fy}"
            f" r={r!r} r_bits={bits_of(r)} p_value={p!r} p_bits={bits_of(p)}"
        )
    print("")

    print("-- 2. SWEEP: n = 1e3 .. 1e7 --")
    for n in SWEEP_N:
        px = x_full[:n]
        py = y_full[:n]
        cell = measure(lambda px=px, py=py: stats.pearsonr(px, py))
        failures += report(n, cell)
    print("")

    print(f"  load at end {os.getloadavg()}  sink {_SINK}")
    if failures == 0:
        print("BENCH_GATE pearsonr_scipy PASS")
    else:
        print(f"BENCH_GATE pearsonr_scipy FAIL {failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
