"""SimPy arm: the same M/M/1 design comparison, WITHOUT CRN, and with hand-built CRN.

Model, identical to the Mojo arm: M/M/1 FIFO, single server, lam = 0.80, mu_A = 1.00,
mu_B = 1.02, N customers per replication measured from an empty system, response = mean wait in
queue over those N customers.

Three RNG regimes:
  S1  NAIVE  one stateful stream per replication, seeded identically for both designs, draws
             consumed in event order (gap at the arrival, service at the service start). This is
             what a practitioner gets by writing `random.seed(r)` and hoping for CRN.
  S2  HAND-BUILT CRN  two separate `random.Random` streams (arrivals, services), identically
             seeded across designs, service times indexed by customer. SimPy ships no CRN
             facility, so this is user code.
  S3  UNPAIRED  independent seeds per design — the honest unpaired baseline.

Also records, for S1, how many of the N arrival gaps are bit-identical across the two designs and
where they first diverge, which is the mechanism by which naive same-seed pairing fails.

HOW TO RUN IT. SimPy is NOT a repo dependency and must not become one. It was measured from a
throwaway virtualenv outside the repo and outside every lockfile:

    /path/to/pixi/env/bin/python -m venv /tmp/crn_venv
    /tmp/crn_venv/bin/pip install simpy          # measured against simpy 4.1.2
    /tmp/crn_venv/bin/python benchmarks/crn_simpy_baseline.py 2000

Run it from a directory that is not /tmp: a stray `/tmp/inspect.py` shadows the standard library
and `importlib.metadata` then fails inside SimPy's own version lookup.

MEASURED, 2000 replications, 2000 customers, macOS 26.5.2 / Apple M4 Max, load average 93 falling
to 49 during the run, 95.3 s wall for 10,000 simulation runs:

    arm A (mu 1.00)  mean 3.967355 CI95 [3.922994, 4.011716]   exact Wq 4.000000
    arm B (mu 1.02)  mean 3.540351 CI95 [3.503357, 3.577344]   exact Wq 3.565062
    S1 naive same-seed   diff var 1.17457792   ratio 1.38   corr 0.2788
    S2 hand-built CRN    diff var 0.03469128   ratio 46.76   corr 0.9962
    S3 unpaired          diff var 1.62216602   (the denominator)
    replications for the half-width S2 reaches at 2000: S2 2,039 / S1 68,689 / S3 94,305
    S1 arrival gaps bit-identical across designs: 1,835,162 of 4,000,000; first divergence at
    customer 44 of 2000

The Mojo arm of the identical comparison (benchmarks/mojo_benchmarks/bench_crn_variance_reduction
.mojo, section 5) reports 59.33 at the same 2000 replications, and both implementations' arm CIs
cover the exact M/M/1 values, so the two agree on the model and differ on the variance ratio by
about the noise of a variance estimate at this replication count (measured within each
implementation at 6-15%). The honest statement of the result is 47-59x, not a single digit.

The finding that matters is S1 versus S2: pairing that is not SYNCHRONISED buys 1.38x, which is
where Murphy et al. (2013) landed for unsynchronised partial CRN (1.06x). Changing the service
rate changes the interleaving of arrival and service draws on a single stateful stream, so 54% of
the arrival gaps differ between two designs a practitioner believes are paired.
"""

from __future__ import annotations

import math
import os
import platform
import random
import statistics
import sys
import time

import simpy

LAM = 0.80
MU_A = 1.00
MU_B = 1.02
N_CUST = 2000
LEVEL = 0.95


# ── exact t machinery, no scipy in this environment ───────────────────────────
def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 3e-16:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    front = math.exp(lb)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + b * math.log1p(-x)
        + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    p = 0.5 * betainc(0.5 * df, 0.5, x)
    return 1.0 - p if t > 0 else p


def t_quantile(p: float, df: float) -> float:
    lo, hi = -300.0, 300.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ci(sample: list[float], level: float = LEVEL) -> tuple[float, float, float, float]:
    n = len(sample)
    m = statistics.fmean(sample)
    v = statistics.variance(sample)
    tc = t_quantile(1.0 - (1.0 - level) / 2.0, n - 1)
    h = tc * math.sqrt(v / n)
    return m, v, m - h, m + h


def reps_for_halfwidth(v: float, h: float, level: float = LEVEL) -> int:
    """Smallest n >= 2 with t_{n-1} * sqrt(v/n) <= h. Exact, iterated."""
    n = 2
    while n < 10_000_000:
        tc = t_quantile(1.0 - (1.0 - level) / 2.0, n - 1)
        if tc * math.sqrt(v / n) <= h:
            return n
        n = n + 1 if n < 40 else int(n * 1.02) + 1
    return -1


# ── the SimPy model ──────────────────────────────────────────────────────────
def mm1_naive(mu: float, seed: int, n: int = N_CUST) -> tuple[float, list[float]]:
    """S1: ONE stateful stream, draws consumed in event order."""
    rng = random.Random(seed)
    env = simpy.Environment()
    server = simpy.Resource(env, capacity=1)
    waits: list[float] = []
    gaps: list[float] = []

    def customer() -> object:
        arrived = env.now
        with server.request() as req:
            yield req
            waits.append(env.now - arrived)
            yield env.timeout(rng.expovariate(mu))

    def source() -> object:
        for _ in range(n):
            gap = rng.expovariate(LAM)
            gaps.append(gap)
            yield env.timeout(gap)
            env.process(customer())

    env.process(source())
    env.run()
    return statistics.fmean(waits), gaps


def mm1_streams(mu: float, seed_arr: int, seed_srv: int, n: int = N_CUST) -> float:
    """S2/S3: separate arrival and service streams, service indexed by customer."""
    ra = random.Random(seed_arr)
    rs = random.Random(seed_srv)
    gaps = [ra.expovariate(LAM) for _ in range(n)]
    services = [rs.expovariate(mu) for _ in range(n)]
    env = simpy.Environment()
    server = simpy.Resource(env, capacity=1)
    waits: list[float] = []

    def customer(service: float) -> object:
        arrived = env.now
        with server.request() as req:
            yield req
            waits.append(env.now - arrived)
            yield env.timeout(service)

    def source() -> object:
        for i in range(n):
            yield env.timeout(gaps[i])
            env.process(customer(services[i]))

    env.process(source())
    env.run()
    return statistics.fmean(waits)


def closed_form_wq(lam: float, mu: float) -> float:
    return lam / (mu * (mu - lam))


def loadavg() -> str:
    la = os.getloadavg()
    return f"{la[0]:.2f}/{la[1]:.2f}/{la[2]:.2f}"


def main() -> None:
    n_reps = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    print("=== SimPy arm: same M/M/1 comparison without CRN ===")
    print(f"python {platform.python_version()}  simpy {simpy.__version__}  "
          f"platform {platform.platform()}")
    print(f"lam={LAM} mu_A={MU_A} mu_B={MU_B} customers={N_CUST} reps={n_reps} level={LEVEL}")
    print(f"closed-form Wq: A={closed_form_wq(LAM, MU_A):.6f}  B={closed_form_wq(LAM, MU_B):.6f}  "
          f"delta={closed_form_wq(LAM, MU_B) - closed_form_wq(LAM, MU_A):.6f}")
    print(f"load average before: {loadavg()}")

    a_naive, b_naive = [], []
    a_crn, b_crn = [], []
    b_indep = []
    gap_id_total = 0
    gap_total = 0
    first_div = None
    t0 = time.perf_counter()
    for r in range(1, n_reps + 1):
        # S1 naive: identical seed for both designs, one interleaved stream
        wa, ga = mm1_naive(MU_A, 4242 + r)
        wb, gb = mm1_naive(MU_B, 4242 + r)
        a_naive.append(wa)
        b_naive.append(wb)
        gap_total += len(ga)
        same = sum(1 for x, y in zip(ga, gb) if x == y)
        gap_id_total += same
        if first_div is None:
            for i, (x, y) in enumerate(zip(ga, gb)):
                if x != y:
                    first_div = i
                    break
        # S2 hand-built CRN: same two stream seeds for both designs
        a_crn.append(mm1_streams(MU_A, 90000 + r, 70000 + r))
        b_crn.append(mm1_streams(MU_B, 90000 + r, 70000 + r))
        # S3 unpaired: design B on independent streams
        b_indep.append(mm1_streams(MU_B, 500000 + r, 600000 + r))
    elapsed = time.perf_counter() - t0
    print(f"load average after:  {loadavg()}   wall {elapsed:.2f}s for "
          f"{5 * n_reps} runs of {N_CUST} customers")

    d_naive = [b - a for a, b in zip(a_naive, b_naive)]
    d_crn = [b - a for a, b in zip(a_crn, b_crn)]
    d_unp = [b - a for a, b in zip(a_crn, b_indep)]

    for name, arm in (("A_naive", a_naive), ("B_naive", b_naive), ("A_crn", a_crn),
                      ("B_crn", b_crn), ("B_indep", b_indep)):
        m, v, lo, hi = ci(arm)
        print(f"  arm {name:8s} mean={m:.6f} var={v:.6f} CI95=[{lo:.6f},{hi:.6f}]")

    rows = []
    for name, d in (("S1_naive_same_seed", d_naive), ("S2_handbuilt_CRN", d_crn),
                    ("S3_unpaired", d_unp)):
        m, v, lo, hi = ci(d)
        excl = lo > 0.0 or hi < 0.0
        rows.append((name, m, v, lo, hi, excl))
        print(f"  diff {name:20s} mean={m:+.6f} var={v:.8f} CI95=[{lo:+.6f},{hi:+.6f}] "
              f"excludes_zero={excl}")

    v_unp = rows[2][2]
    for name, _m, v, _lo, _hi, _e in rows[:2]:
        print(f"  variance ratio unpaired/{name} = {v_unp / v:.2f}")

    corr_naive = statistics.correlation(a_naive, b_naive)
    corr_crn = statistics.correlation(a_crn, b_crn)
    corr_unp = statistics.correlation(a_crn, b_indep)
    print(f"  corr(A,B) naive={corr_naive:.6f} handbuilt_CRN={corr_crn:.6f} "
          f"unpaired={corr_unp:.6f}")
    print(f"  S1 arrival gaps bit-identical across designs: {gap_id_total}/{gap_total}"
          f"  first divergence at gap index {first_div}")

    # replications to reach the half-width the CRN arm already reaches
    _m, v_crn, lo_crn, hi_crn = ci(d_crn)
    h = 0.5 * (hi_crn - lo_crn)
    n_crn = reps_for_halfwidth(v_crn, h)
    n_naive = reps_for_halfwidth(rows[0][2], h)
    n_unp = reps_for_halfwidth(v_unp, h)
    print(f"  target half-width h={h:.6f} (what S2 achieves at {n_reps} reps)")
    print(f"  replications needed: S2_CRN={n_crn}  S1_naive={n_naive}  S3_unpaired={n_unp}")
    print("  t-quantile self-check (p=0.975): "
          + " ".join(f"df{int(df)}={t_quantile(0.975, df):.4f}"
                     for df in (1, 2, 5, 10, 30, 39, 399)))
    print("DONE")


if __name__ == "__main__":
    main()
