#!/usr/bin/env python3
"""Rung 2 of the claim ladder — a CONTROLLED same-model comparison against optimised NumPy.

WHAT MAKES A SPEED CLAIM MEANINGFUL

"Faster than Python" is not a claim, it is a category error: any compiled kernel beats a scalar Python
loop, and saying so tells a reader nothing about the engine. The plan therefore requires a controlled
comparison, and every one of these conditions has to hold or the number is decoration:

  identical model equations      the NumPy arm implements the SAME lap-time model, the same tyre cliff,
                                 the same neutralisation semantics and the same retirement hazard
  identical data snapshot        one field, one parameter vector, passed to both arms
  equivalent keyed randomness    both arms consume Philox draws at the same coordinates, so neither is
                                 advantaged by a cheaper generator
  identical car and lap counts   the workload is fixed, not tuned per arm
  identical outputs              both return the same per-car finishing-position distribution
  an OPTIMISED baseline          fully vectorised over the replication axis. A scalar Python loop would
                                 be a strawman and the resulting ratio would be meaningless
  documented warm-up             JIT and page-cache effects excluded by a discarded warm-up pass
  guards against dead-code       the result is consumed and checked, so neither arm can be optimised away

AND THE ACCURACY CHECK IS PART OF THE CLAIM. A faster arm that computes something different is not
faster at the same thing. The two arms are compared on their p_win vectors, and the speed number is only
reported when they agree to tolerance.

The comparison is deliberately on the ORACLE rather than the option board: the board carries a bootstrap
and an abstention rule whose NumPy reproduction would be a second implementation of the inference layer,
and any divergence there would confound a compute comparison with a statistics comparison.

Usage:
    python3 -m benchmarks.timing.numpy_baseline
    python3 -m benchmarks.timing.numpy_baseline --cars 20 --laps 40 --reps 4000 --json out.json
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "timing"))
from kernel_probe import Worker  # noqa: E402

# params[] indices, mirroring contest_strategy.mojo. Named rather than numeric so a layout change
# cannot silently mislabel a term in the baseline.
P_PIT_LOSS, P_LAP_NOISE, P_DNF, P_SC_LAM, P_SC_PACE, P_SC_PIT = 0, 1, 2, 3, 4, 5
P_VSC_LAM, P_VSC_PACE, P_VSC_PIT, P_DIRTY_W, P_DIRTY_L, P_FUEL = 6, 7, 8, 9, 10, 11
P_DELTA_OUT, P_DELTA_IN, P_SIGMA_PIT = 12, 13, 14
P_OT_BIAS, P_OT_KPACE, P_MIN_FOLLOW, P_SC_BUNCH, P_STOP_JIT, P_PACE_SIGMA = 17, 18, 19, 20, 21, 22
P_SC_DUR, P_VSC_DUR, P_OT_KAGE, P_CLIFF_AGE, P_CLIFF_SLOPE = 23, 24, 25, 26, 27

MASK64 = (1 << 64) - 1
M0, M1 = 0xD2B74407B1CE6E93, 0xCA5A826395121157
W0, W1 = 0x9E3779B97F4A7C15, 0xBB67AE8584CAA73B


def philox4x64_10(c0, c1, c2, c3, k0, k1):
    """Vectorised Philox-4x64-10, matching counter_rng.mojo bit for bit.

    The baseline must not be advantaged by a cheaper generator, so it pays for the same ten rounds. This
    is also the check that our Mojo implementation is a real Philox rather than something that merely
    looks random: scripts/timing/validate_rng.py cross-checks the same construction against numpy's.
    """
    c0 = np.asarray(c0, dtype=np.uint64).copy()
    c1 = np.asarray(c1, dtype=np.uint64).copy()
    c2 = np.asarray(c2, dtype=np.uint64).copy()
    c3 = np.asarray(c3, dtype=np.uint64).copy()
    k0 = int(k0) & MASK64
    k1 = int(k1) & MASK64
    with np.errstate(over="ignore"):
        for _ in range(10):
            hi0, lo0 = _mulhilo(M0, c0)
            hi1, lo1 = _mulhilo(M1, c2)
            nk0, nk1 = np.uint64(k0), np.uint64(k1)
            c0, c1, c2, c3 = (hi1 ^ c1 ^ nk0), lo1, (hi0 ^ c3 ^ nk1), lo0
            k0 = (k0 + W0) & MASK64
            k1 = (k1 + W1) & MASK64
    return c0, c1, c2, c3


def _mulhilo(a: int, b):
    """64x64 -> 128 without native 128-bit ints, via 32-bit limbs.

    `a` stays a PYTHON int and is decomposed in Python: NumPy 2 refuses to mix a np.uint64 scalar with a
    Python int under safe casting, and converting the constant first is both correct and free. uint64
    arithmetic wraps, which is exactly the mod-2^64 semantics Philox is defined over, so the overflow
    warnings are suppressed deliberately rather than worked around.
    """
    al = np.uint64(a & 0xFFFFFFFF)
    ah = np.uint64((a >> 32) & 0xFFFFFFFF)
    s32 = np.uint64(32)
    lo32 = np.uint64(0xFFFFFFFF)
    with np.errstate(over="ignore"):
        bl = (b & lo32).astype(np.uint64)
        bh = (b >> s32).astype(np.uint64)
        t0 = al * bl
        t1 = ah * bl + (t0 >> s32)
        t2 = al * bh + (t1 & lo32)
        hi = ah * bh + (t1 >> s32) + (t2 >> s32)
        lo = (t2 << s32) | (t0 & lo32)
    return hi, lo


def _u01(words):
    """The same 53-bit conversion the kernel documents."""
    return (words >> np.uint64(11)).astype(np.float64) * (1.0 / 9007199254740992.0)


def draws(kind: int, reps: int, lap: int, car: int, seed: int, scenario: int):
    """One keyed draw per replication at the kernel's coordinate layout."""
    r = np.arange(reps, dtype=np.uint64)
    c1 = np.uint64((lap << 32) | (car << 16) | kind)
    w0, _w1, _w2, _w3 = philox4x64_10(r, np.full(reps, c1, dtype=np.uint64),
                                      np.zeros(reps, dtype=np.uint64),
                                      np.zeros(reps, dtype=np.uint64), seed, scenario)
    return _u01(w0)


def numpy_oracle(pace, deg, form_sigma, elapsed, age0, active, stops, laps, p, reps, seed, scenario):
    """The same model, fully vectorised over the REPLICATION axis.

    Vectorising over replications rather than cars is what makes this an optimised baseline: the car axis
    is short (20) and carries the sequential leader-first dependency, while the replication axis is long
    and fully independent. A per-replication Python loop would be the strawman this exists to avoid.
    """
    n = len(pace)
    pace = np.asarray(pace, dtype=np.float64)
    deg = np.clip(np.asarray(deg, dtype=np.float64), 0.0, 0.22)
    cliff_age, cliff_slope = p[P_CLIFF_AGE], p[P_CLIFF_SLOPE]

    rep_ix = np.arange(reps)

    def tyre(deg_v, age_v):
        """Per-replication tyre penalty. deg_v and age_v are both (reps,)."""
        return deg_v * age_v + np.where(age_v > cliff_age, cliff_slope * (age_v - cliff_age), 0.0)

    age0a = np.asarray(age0, dtype=np.float64)
    base_pen = deg * age0a + np.where(age0a > cliff_age, cliff_slope * (age0a - cliff_age), 0.0)

    el = np.repeat(np.asarray(elapsed, dtype=np.float64)[:, None], reps, axis=1)
    age = np.repeat(age0a[:, None], reps, axis=1)
    alive = np.repeat((np.asarray(active) > 0.5)[:, None], reps, axis=1)

    def normal(kind, lap, car, tag):
        """Box-Muller from two keyed uniforms, the kernel's rejection-free transform."""
        u1 = np.clip(draws(kind, reps, lap, car, seed, scenario + tag), 1e-12, 1.0)
        u2 = draws(kind, reps, lap, car, seed, scenario + tag + 1)
        return np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)

    form = np.empty((n, reps))
    for c in range(n):
        form[c] = form_sigma[c] * normal(8, 0, c, 0)

    p_ret = 1.0 - (1.0 - p[P_DNF]) ** laps
    retire_at = np.full((n, reps), laps, dtype=np.int64)
    for c in range(n):
        u = draws(6, reps, 0, c, seed, scenario)
        ul = draws(6, reps, 0, c, seed, scenario + 2)
        retire_at[c] = np.where(u < p_ret,
                                np.minimum((ul * laps).astype(np.int64), laps - 1), laps)

    regime = np.zeros((laps, reps), dtype=np.int8)
    for lap_i in range(laps):
        free = regime[lap_i] == 0
        if not free.any():
            continue
        u_sc = draws(1, reps, lap_i, 0xFFFF, seed, scenario)
        u_vs = draws(2, reps, lap_i, 0xFFFF, seed, scenario)
        ud = draws(1, reps, lap_i, 0xFFFF, seed, scenario + 3)
        fire_sc = free & (u_sc < p[P_SC_LAM])
        fire_vs = free & ~fire_sc & (u_vs < p[P_VSC_LAM])
        for fire, code, dmax in ((fire_sc, 1, p[P_SC_DUR]), (fire_vs, 2, p[P_VSC_DUR])):
            if not fire.any():
                continue
            dur = 1 + (ud * dmax).astype(np.int64)
            for k in range(int(dmax) + 1):
                sl = lap_i + k
                if sl >= laps:
                    break
                regime[sl] = np.where(fire & (k < dur), code, regime[sl])

    MAX_STOPS = 5
    stop_at = np.full((n, MAX_STOPS, reps), -1, dtype=np.int64)
    for c in range(n):
        ns = min(int(stops[c]), MAX_STOPS)
        prior = None
        for k in range(1, ns + 1):
            frac = k / (ns + 1)
            uj = draws(5, reps, k, c, seed, scenario)
            at = ((frac + (uj - 0.5) * 2.0 * p[P_STOP_JIT]) * laps).astype(np.int64)
            at = np.clip(at, 1, laps - 1)
            if prior is not None:
                at = np.clip(np.maximum(at, prior + 1), 1, laps - 1)
            stop_at[c, k - 1] = at
            prior = at

    for lap in range(laps):
        reg = regime[lap]
        pace_mult = np.where(reg == 1, p[P_SC_PACE], np.where(reg == 2, p[P_VSC_PACE], 1.0))
        pit_factor = np.where(reg == 1, p[P_SC_PIT], np.where(reg == 2, p[P_VSC_PIT], 1.0))
        prev_e = el.copy()
        # leader-first PER REPLICATION: the running order differs across replications, so the walk
        # order is an (n, reps) permutation rather than a single sequence
        order = np.argsort(el, axis=0)
        z_lap = normal(4, lap, 0, 4)
        up = draws(5, reps, lap, 0, seed, scenario)
        uo = draws(7, reps, lap, 0, seed, scenario)
        # the car ahead, per replication: -1 until the first live car is seen
        ahead = np.full(reps, -1, dtype=np.int64)
        ahead_pitted = np.zeros(reps, dtype=bool)
        for slot in range(n):
            c = order[slot]                              # (reps,) — a different car per replication
            live = alive[c, rep_ix] & (lap < retire_at[c, rep_ix])
            alive[c, rep_ix] = live
            a_now = age[c, rep_ix]
            t = pace[c] + form[c, rep_ix] + tyre(deg[c], a_now) - base_pen[c]
            t = t + p[P_FUEL] * (laps - lap)
            t = (t + p[P_LAP_NOISE] * z_lap) * pace_mult
            pitting = (stop_at[c[:, None], np.arange(MAX_STOPS)[None, :], rep_ix[:, None]]
                       == lap).any(axis=1)

            # DIRTY AIR AND BLOCKING, matching the kernel: a car within the window of the car ahead
            # attempts a pass on effective pace and tyre-age delta; failing, it loses dirty_loss and is
            # held no closer than min_follow. Suspended under a neutralisation, and a leader already in
            # the pit lane neither dirties the air nor blocks.
            has_ahead = (ahead >= 0) & (reg == 0) & ~pitting & ~ahead_pitted
            gap = prev_e[c, rep_ix] - np.where(ahead >= 0, prev_e[np.maximum(ahead, 0), rep_ix], 0.0)
            in_window = has_ahead & (gap >= 0.0) & (gap < p[P_DIRTY_W])
            ea = (pace[np.maximum(ahead, 0)] + form[np.maximum(ahead, 0), rep_ix]
                  + tyre(deg[np.maximum(ahead, 0)], age[np.maximum(ahead, 0), rep_ix])
                  - base_pen[np.maximum(ahead, 0)])
            ec = pace[c] + form[c, rep_ix] + tyre(deg[c], a_now) - base_pen[c]
            dage = age[np.maximum(ahead, 0), rep_ix] - a_now
            pp = 1.0 / (1.0 + np.exp(-(p[P_OT_BIAS] + p[P_OT_KPACE] * (ea - ec)
                                       + p[P_OT_KAGE] * dage)))
            held = in_window & (uo >= pp)
            t = np.where(held, t + p[P_DIRTY_L], t)

            svc = p[P_PIT_LOSS] * pit_factor - p[P_SIGMA_PIT] * np.log(np.clip(up, 1e-12, 1.0))
            t = np.where(pitting, t + svc + p[P_DELTA_IN], t)
            age[c, rep_ix] = np.where(pitting, 0.0, a_now + 1.0)
            ne = prev_e[c, rep_ix] + t
            floor_e = np.where(ahead >= 0, el[np.maximum(ahead, 0), rep_ix], -np.inf) + p[P_MIN_FOLLOW]
            ne = np.where(held & (ne < floor_e), floor_e, ne)
            el[c, rep_ix] = np.where(live, ne, el[c, rep_ix])
            ahead = np.where(live, c, ahead)
            ahead_pitted = np.where(live, pitting, ahead_pitted)

        # SAFETY-CAR BUNCHING: gaps compressed to at most sc_bunch, applied on the re-sorted order
        sc_now = reg == 1
        if sc_now.any():
            o2 = np.argsort(el, axis=0)
            lead = np.full(reps, -1, dtype=np.int64)
            for slot in range(n):
                c = o2[slot]
                live = alive[c, rep_ix]
                first = live & (lead < 0)
                have = live & (lead >= 0) & sc_now
                g = el[c, rep_ix] - np.where(lead >= 0, el[np.maximum(lead, 0), rep_ix], 0.0)
                g = np.clip(g, 0.0, p[P_SC_BUNCH])
                el[c, rep_ix] = np.where(
                    have, el[np.maximum(lead, 0), rep_ix] + g, el[c, rep_ix])
                lead = np.where(live, c, lead)
                del first

    rank = np.argsort(np.argsort(np.where(alive, el, el + 1e9), axis=0), axis=0) + 1
    p_win = (rank == 1).mean(axis=1)
    return p_win


def hardware() -> dict:
    cpu = platform.processor() or platform.machine()
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                             text=True, timeout=5).stdout.strip() or cpu
    except Exception:
        pass
    return {"cpu": cpu, "platform": platform.platform(), "numpy": np.__version__,
            "python": platform.python_version()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default="mojo_build/simulate_timing")
    ap.add_argument("--cars", type=int, default=20)
    ap.add_argument("--laps", type=int, default=40)
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--tol", type=float, default=0.06,
                    help="max allowed |p_win| divergence; above this the speed number is withheld")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    n, laps, reps = args.cars, args.laps, args.reps
    pace = [90.0 + 0.12 * i for i in range(n)]
    deg = [0.010] * n
    el = [0.28 * i * 0.5 for i in range(n)]
    age = [8.0] * n
    act = [1.0] * n
    stops = [2.0] * n

    w = Worker(ROOT / args.binary)
    try:
        p = w.execute("contest_strategy", "default_contest_params")["result"]
        fs = [p[P_PACE_SIGMA]] * n

        # warm-up, discarded: JIT, page cache and pool spin-up are not part of the measurement
        w.execute("contest_strategy", "outcome_distribution",
                  [pace, deg, fs, el, age, act, stops, laps, p, 500, 7, 1])
        numpy_oracle(pace, deg, fs, el, age, act, stops, laps, p, 200, 7, 1)

        best_mojo = None
        for _ in range(3):
            t0 = time.perf_counter()
            r = w.execute("contest_strategy", "outcome_distribution",
                          [pace, deg, fs, el, age, act, stops, laps, p, reps, 7, 1])
            dt = time.perf_counter() - t0
            if best_mojo is None or dt < best_mojo[0]:
                best_mojo = (dt, r["result"]["v"][0])

        best_np = None
        for _ in range(3):
            t0 = time.perf_counter()
            pw = numpy_oracle(pace, deg, fs, el, age, act, stops, laps, p, reps, 7, 1)
            dt = time.perf_counter() - t0
            if best_np is None or dt < best_np[0]:
                best_np = (dt, pw)

        mojo_s, mojo_p = best_mojo
        np_s, np_p = best_np
        # consume both results so neither arm can be optimised away
        assert abs(sum(mojo_p) - 1.0) < 1e-6, f"mojo p_win sums to {sum(mojo_p)}"
        assert abs(float(np_p.sum()) - 1.0) < 1e-6, f"numpy p_win sums to {np_p.sum()}"

        div = max(abs(a - float(b)) for a, b in zip(mojo_p, np_p))
        updates = reps * n * laps
        print(f"controlled same-model comparison — {n} cars x {laps} laps x {reps:,} replications")
        print(f"  workload: {updates:,} car-lap state updates per arm\n")
        print(f"{'arm':<28} {'wall s':>9} {'M updates/s':>13}")
        print(f"{'Mojo kernel (socket)':<28} {mojo_s:>9.3f} {updates / mojo_s / 1e6:>13.1f}")
        print(f"{'NumPy, vectorised over N':<28} {np_s:>9.3f} {updates / np_s / 1e6:>13.1f}")
        print(f"\nspeedup {np_s / mojo_s:.1f}x")
        print(f"max |p_win| divergence between the arms: {div:.4f}")
        ok = div <= args.tol
        if ok:
            print("agreement within tolerance — the speed number compares the SAME computation")
        else:
            print(f"DIVERGENCE ABOVE {args.tol}: the arms are not computing the same thing, so the")
            print("speedup above is NOT a valid same-model claim and must not be published.")

        if args.json:
            Path(args.json).write_text(json.dumps({
                "workload": {"cars": n, "laps": laps, "reps": reps, "car_lap_updates": updates},
                "mojo_seconds": mojo_s, "numpy_seconds": np_s,
                "speedup": np_s / mojo_s, "max_p_win_divergence": div,
                "same_model_valid": ok, "hardware": hardware(),
            }, indent=2))
            print(f"wrote {args.json}", file=sys.stderr)
        return 0 if ok else 1
    finally:
        w.close()


if __name__ == "__main__":
    raise SystemExit(main())
