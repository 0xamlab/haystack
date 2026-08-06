"""bench_strategy.mojo — scenario generation, policy replay, and the price of pairing.

What is measured, and why the gates are on SHAPE
-----------------------------------------------
Absolute nanoseconds are a property of this machine, this thermal state and this JIT. They are
printed because they are useful, and NOTHING is gated on them. Nine shapes are gated, and each one
can fail:

1. *Scenario generation is linear in the number of cells.* A tape is `horizon * n_factors`
   independent addressed draws with no state between them, so per-cell cost must be flat. The gate
   is the empirical growth exponent `p` in `t ~ cells^p` over a 3-doubling window. A regression
   that made a draw depend on the draws before it — the one thing that would destroy common random
   numbers — would show up here as `p` climbing, because a sequential generator has to walk.

2. *Policy replay is linear in the horizon.* The four-factor work product says replay is
   `n_strategies * n_scenarios * horizon * (1 + n_factors)`, so holding three of them fixed and
   doubling the horizon must double the time and nothing more.

3. *THE DECLARED WORK CHARGE TRACKS MEASURED TIME ACROSS SHAPES.* This is the section that
   matters most, and it is the one this tree has already been burned by: two requests at an
   IDENTICAL declared cost measured 0.49s and 23.89s, which from the caller's side is
   indistinguishable from a hang. So nanoseconds per CHARGED UNIT is measured at four requests
   whose (strategies, scenarios, horizon, factors) mixes are deliberately as different as the
   ceilings allow — draw-saturated, replication-saturated, and balanced at four and sixteen
   factors — and the gate is the SPREAD between the cheapest and dearest per-unit cost. If the
   charge model dropped the per-factor scan or under-weighted a draw, that spread would open and
   this gate would catch it; a wall-clock gate would not.

4. *PAIRING STILL BUYS VARIANCE, at every scenario count.* The package's reason to exist is a
   measured variance reduction, so it is gated like any other regression: the unpaired-to-paired
   variance ratio is measured at three scenario counts and must clear a floor at every one. If a
   future edit made the environment depend on the strategy index, the two arms would become
   equally noisy, the ratio would collapse toward 1, and THIS GATE WOULD FAIL — which is the only
   way a correctness property that lives in a variance can be defended by a benchmark.

5. *A refusal costs the same whatever it refuses.* An over-budget request must be rejected before
   any tape is built. Measured at four horizons spanning 8x, and gated on the ratio: a driver that
   started generating and only then noticed the budget would show that 8x here. A refusal whose
   cost grows with the request is the same defect as no refusal at all, because the caller is
   already waiting.

6. *AN ACCEPTED EQUILIBRIUM REQUEST IS ONE THE MODULE FINISHES.* A game tensor's work is a
   product too — enumeration is `profiles * n_players * (n_actions + 1)` payoff reads and one
   regret-matching iteration is `profiles * n_players` accumulations, so an iteration count
   multiplies the entire tensor. Four requests each saturating `STRAT_MAX_WORK` to within 3% are
   run, two enumerations and two adaptive-play runs, with the mixes as different as the ceilings
   allow: 406 actions at 2 players, 81 at 3, 1340 iterations at 64 actions, 212 at 8 players. The
   gate is that every one of them COMPLETES and completes under five seconds, which is the
   budget's whole promise, plus a spread bound on ns per charged unit. A charge model that
   under-weighted the player count or dropped the deviation scan would let a shape through that
   runs for a wall-clock minute, and from the caller's side that is a hang.

7. *ITERATION COST IS LINEAR IN THE ITERATION COUNT, AND THE SOLVER ACTUALLY CONVERGES.* The
   first half is the shape gate: quadrupling the iteration count at a fixed game must quadruple
   the time, so `p` in `t ~ charge^p` stays near 1 and a hidden quadratic across iterations shows
   up as `p` near 2. The second half is not a timing gate at all and cannot flake: the measured
   EXPLOITABILITY of regret matching's average must fall at every step of an iteration ladder and
   end at least 5x below where it started. That is the one property a benchmark can defend that a
   type system cannot — a solver that stopped converging would still return a strategy, still
   report a residual, and still pass every other gate in this file.

8. *THE RANKING'S CHARGE TRACKS MEASURED TIME TOO, and its boundary is real.* Ranking has two
   costs a `strategies x replications` product cannot see: one Student-t quantile bisection per
   strategy (MEASURED 236-250 us in situ) and one two-sided tail per pair (1.4-1.6 us). At 1024
   strategies the quantile alone is 1.2 seconds. So cost per CHARGED unit is measured at seven
   accepted shapes from 2 to 4096 replications and gated on the spread, together with the
   assertion that one more strategy at the boundary is REFUSED. The band is deliberately wide and
   its width is measured rather than guessed: repeated timings of an identical ranking on this
   machine differ by 3-7x (54 ms and 388 ms for the same call in one process), so a tight band
   would flake and prove nothing, while a charge model that dropped the per-pair term entirely
   would move a pair-heavy shape tenfold and still be caught.

9. *THE VERDICTS, ON A FIXED SEED, WITH NO CLOCK IN THE GATE.* The only gate here that cannot
   flake at all. A threshold gap swept from 0.00 to 0.20 over 128 paired scenarios must report NO
   SIGNIFICANT DIFFERENCE with no winner at a gap of zero, a decided winner at the widest gap, and
   a p-value that falls monotonically in between. A ranking that always named a winner fails the
   first; one that always tied fails the second. It also runs the composition end to end —
   `crn_evaluate_policies` builds the payoff block and `tourney_rank_flat` consumes it with no
   reshaping, both strategy-major — so a layout disagreement between the two modules cannot pass.

Measurement method
------------------
Each gated section runs an untimed WARM-UP call and then takes the MINIMUM of three timed
repetitions per size. Without the warm-up the first timed call carries the JIT compilation of the
driver, and per-unit cost then FALLS as the problem grows — which reads as sublinear scaling and
inverts every shape gate in this file. The minimum is the robust estimator: scheduler noise only
ever adds time, so the smallest observation is closest to the work actually done.

Why every timed call sits in its own tiny function
--------------------------------------------------
`_time_tape`, `_time_policies`, `_time_audit` and `_time_refusal` each perform exactly ONE timed
driver call and return flat `Float64` slots. Written the obvious way — the driver called directly
inside a size loop inside a section inside `main` — the sibling `bench_discrete_event.mojo` did not
finish COMPILING in ten minutes, while the same measurements built in seconds once each driver call
had its own function. That failure mode is worth naming because of how it presents: a benchmark
that cannot be built is indistinguishable from one whose kernels hang.

Every input is generated by the seeded frozen generator or by closed-form arithmetic. There is no
unseeded randomness anywhere in this file, so a re-run measures the same work.
"""
from std.math import log
from std.time import perf_counter_ns

from strategy.contract import (
    STRAT_ERR_WORK_BUDGET,
    STRAT_FACTOR_UNIFORM,
    STRAT_OK,
    STRAT_POLICY_THRESHOLD,
    STRAT_VERDICT_A_BETTER,
    STRAT_VERDICT_NO_DIFFERENCE,
)
from strategy.crn import (
    crn_evaluate_policies,
    crn_pairing_audit,
    crn_scenario_tape,
)
from strategy.equilibrium import (
    eq_enumeration_charge,
    eq_iteration_charge,
    eq_pure_nash_flat,
    eq_regret_matching_flat,
)
from strategy.tournament import (
    TOURNEY_METHOD_HOLM,
    tourney_pair_count,
    tourney_rank_flat,
    tourney_work_charge,
)


def _exponent(t_first: Float64, t_last: Float64, n_first: Int, n_last: Int) -> Float64:
    """The empirical growth exponent `p` in `t ~ n^p`, from the two endpoints.

    Reported instead of a complexity CLAIM: `p` is what was measured over two points, which is
    why every intermediate size is printed beside it.
    """
    if t_first <= 0.0 or t_last <= 0.0 or n_first <= 0 or n_last <= n_first:
        return 0.0
    return log(t_last / t_first) / log(Float64(n_last) / Float64(n_first))


def _spread(lo: Float64, hi: Float64) -> Float64:
    if lo <= 0.0:
        return 0.0
    return hi / lo


def _threshold_pair(theta_a: Float64, theta_b: Float64) -> List[Float64]:
    """A 2 x 2 THRESHOLD block over one factor: unit weight, then the threshold."""
    var out = List[Float64]()
    out.append(1.0)
    out.append(theta_a)
    out.append(1.0)
    out.append(theta_b)
    return out^


def _threshold_block(n_strategies: Int, n_factors: Int) -> List[Float64]:
    """An `n_strategies x (n_factors + 1)` THRESHOLD block with spread thresholds.

    Thresholds walk across the plausible score range so different rows really do decide
    differently; a block of identical rows would let a branch predictor make the replay look
    cheaper than a real comparison.
    """
    var out = List[Float64]()
    for s in range(n_strategies):
        for _ in range(n_factors):
            out.append(1.0)
        out.append(0.25 * Float64(n_factors) + 0.01 * Float64(s % 32))
    return out^


# ── one timed driver call per function; see the module docstring ───────────────


def _time_tape(horizon: Int, n_factors: Int) -> List[Float64]:
    """ONE timed `crn_scenario_tape`. Returns [ns, n_cells]."""
    var t0 = perf_counter_ns()
    var tape = crn_scenario_tape(7, 3, 11, horizon, n_factors, STRAT_FACTOR_UNIFORM, 0.0)
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(len(tape)))
    return out^


def _time_policies(s: Int, r: Int, h: Int, f: Int) -> List[Float64]:
    """ONE timed `crn_evaluate_policies`. Returns [ns, status, charge, tapes_built].

    The parameter block is built inside so the timer covers the driver only.
    """
    var block = _threshold_block(s, f)
    var t0 = perf_counter_ns()
    var run = crn_evaluate_policies(
        4242, 9, r, h, f, STRAT_FACTOR_UNIFORM, 0.0, 0.5 * Float64(f),
        STRAT_POLICY_THRESHOLD, block, s, f + 1, 1.0,
    )
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(run.status))
    out.append(Float64(run.work_charged))
    out.append(Float64(run.n_tapes_built))
    return out^


def _time_audit(n_scenarios: Int) -> List[Float64]:
    """ONE timed `crn_pairing_audit`. Returns [ns, status, ratio, paired_var, unpaired_var, ok]."""
    var block = _threshold_pair(0.40, 0.50)
    var t0 = perf_counter_ns()
    var au = crn_pairing_audit(
        12345, 7, n_scenarios, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5,
        STRAT_POLICY_THRESHOLD, block, 2, 2, 0, 1, 1.0, 0.95,
    )
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(au.status))
    out.append(au.variance_ratio)
    out.append(au.paired_variance)
    out.append(au.unpaired_variance)
    var sane = au.has_variance_ratio and au.pairing_reduces_variance
    sane = sane and au.n_scenarios_bit_identical == n_scenarios
    out.append(1.0 if sane else 0.0)
    return out^


def _time_refusal(horizon: Int) -> List[Float64]:
    """ONE timed REFUSED `crn_pairing_audit`. Returns [ns, status].

    2048 scenarios at these horizons is inside every allocation ceiling and past the work budget,
    so the driver must reject it without building a single tape.
    """
    var block = _threshold_pair(0.40, 0.50)
    var t0 = perf_counter_ns()
    var au = crn_pairing_audit(
        1, 1, 2048, horizon, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0,
        STRAT_POLICY_THRESHOLD, block, 2, 2, 0, 1, 1.0, 0.95,
    )
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(au.status))
    return out^


# ── 1. scenario generation is linear in cells ─────────────────────────────────


def _eq_tensor(n_players: Int, n_actions: Int) -> List[Float64]:
    """A payoff tensor filled by closed-form arithmetic — no randomness, so a re-run is the same
    work. `(k * 7919) % 101 / 100` spreads the payoffs over [0, 1] without ties everywhere, which
    matters: an all-ties tensor would make every profile an equilibrium and the enumeration would
    measure the listing cap instead of the scan.
    """
    var profiles = 1
    for _ in range(n_players):
        profiles = profiles * n_actions
    var out = List[Float64]()
    for k in range(n_players * profiles):
        out.append(Float64((k * 7919) % 101) * 0.01)
    return out^


def _time_enumeration(payoffs: List[Float64], p: Int, a: Int) -> List[Float64]:
    """ONE timed `eq_pure_nash_flat`. Returns [ns, status, charge]."""
    var t0 = perf_counter_ns()
    var r = eq_pure_nash_flat(payoffs, p, a, 0.0)
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(r.status))
    out.append(Float64(eq_enumeration_charge(p, a)))
    return out^


def _time_regret(payoffs: List[Float64], p: Int, a: Int, iters: Int) -> List[Float64]:
    """ONE timed `eq_regret_matching_flat`. Returns [ns, status, charge, residual]."""
    var t0 = perf_counter_ns()
    var r = eq_regret_matching_flat(payoffs, p, a, iters, 1.0e-9)
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(r.status))
    out.append(Float64(eq_iteration_charge(p, a, iters)))
    out.append(r.residual)
    return out^


def _bench_tape() -> Int:
    print("  [1] scenario generation: per-cell cost as the tape grows")
    print("      cells    ms       ns/cell")
    var sizes = List[Int]()
    sizes.append(8192)
    sizes.append(16384)
    sizes.append(32768)
    sizes.append(65536)
    _ = _time_tape(1024, 1)  # untimed warm-up: the first call carries the JIT
    var total = List[Float64]()
    var per_cell = List[Float64]()
    var ok = True
    for i in range(len(sizes)):
        var cells = sizes[i]
        var best: Float64 = 0.0
        var have = False
        for _ in range(3):
            var m = _time_tape(cells, 1)
            if Int(m[1]) != cells:
                ok = False
            if not have or m[0] < best:
                best = m[0]
                have = True
        total.append(best)
        per_cell.append(best / Float64(cells))
        print("      ", cells, best / 1.0e6, best / Float64(cells))
    var p = _exponent(total[0], total[3], sizes[0], sizes[3])
    var drift = _spread(per_cell[0], per_cell[3])
    print("      growth exponent p =", p, " per-cell drift =", drift, "x")
    if not ok:
        print("  FAIL a tape did not return horizon * n_factors cells")
        return 1
    if p > 1.25 or drift > 1.6:
        print("  FAIL scenario generation is not linear in cells: p =", p)
        return 1
    print(
        "  PASS per-cell cost is flat — every draw is a pure function of its coordinates and",
        "nothing accumulates between them",
    )
    return 0


# ── 2. policy replay is linear in the horizon ─────────────────────────────────


def _bench_replay() -> Int:
    print("  [2] policy replay: 4 strategies x 16 scenarios x 2 factors, horizon doubling")
    print("      horizon  ms       ns/step")
    var sizes = List[Int]()
    sizes.append(256)
    sizes.append(512)
    sizes.append(1024)
    sizes.append(2048)
    _ = _time_policies(4, 16, 128, 2)  # untimed warm-up
    var total = List[Float64]()
    var per_step = List[Float64]()
    var ok = True
    for i in range(len(sizes)):
        var h = sizes[i]
        var best: Float64 = 0.0
        var have = False
        for _ in range(3):
            var m = _time_policies(4, 16, h, 2)
            if Int(m[1]) != STRAT_OK or Int(m[3]) != 16:
                ok = False
            if not have or m[0] < best:
                best = m[0]
                have = True
        total.append(best)
        per_step.append(best / Float64(4 * 16 * h))
        print("      ", h, best / 1.0e6, best / Float64(4 * 16 * h))
    var p = _exponent(total[0], total[3], sizes[0], sizes[3])
    var drift = _spread(per_step[0], per_step[3])
    print("      growth exponent p =", p, " per-step drift =", drift, "x")
    if not ok:
        print("  FAIL a replay refused, or built more tapes than there were scenarios")
        return 1
    if p > 1.25 or drift > 1.6:
        print("  FAIL replay is not linear in the horizon: p =", p)
        return 1
    print(
        "  PASS replay is linear in the horizon, and one tape was built per scenario — not one",
        "per (strategy, scenario), which is what makes the comparison paired",
    )
    return 0


# ── 3. the declared charge tracks measured time across very different shapes ──


def _bench_charge() -> Int:
    print("  [3] ns per CHARGED unit, at four deliberately different shapes")
    print("      s     r     h     f    charge       ms       ns/unit")
    var ss = List[Int]()
    var rs = List[Int]()
    var hs = List[Int]()
    var fs = List[Int]()
    ss.append(1)
    rs.append(64)
    hs.append(1024)
    fs.append(8)
    ss.append(32)
    rs.append(256)
    hs.append(256)
    fs.append(1)
    ss.append(16)
    rs.append(64)
    hs.append(512)
    fs.append(4)
    ss.append(8)
    rs.append(32)
    hs.append(512)
    fs.append(16)
    _ = _time_policies(2, 8, 128, 2)  # untimed warm-up
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    var have = False
    var ok = True
    for i in range(4):
        var best: Float64 = 0.0
        var charge: Float64 = 0.0
        var seen = False
        for _ in range(3):
            var m = _time_policies(ss[i], rs[i], hs[i], fs[i])
            if Int(m[1]) != STRAT_OK or m[2] <= 0.0:
                ok = False
            charge = m[2]
            if not seen or m[0] < best:
                best = m[0]
                seen = True
        if charge <= 0.0:
            ok = False
            continue
        var unit = best / charge
        print(
            "      ", ss[i], rs[i], hs[i], fs[i], Int(charge), best / 1.0e6, unit
        )
        if not have or unit < lo:
            lo = unit
        if not have or unit > hi:
            hi = unit
        have = True
    var spread = _spread(lo, hi)
    print("      cheapest", lo, " dearest", hi, " SPREAD =", spread, "x")
    if not ok or not have:
        print("  FAIL a charge-model shape refused or reported no charge")
        return 1
    if spread > 4.0:
        print("  FAIL the declared charge does not track time across shapes: spread =", spread)
        return 1
    print(
        "  PASS one charged unit costs within", spread, "x the same wall time whatever the shape",
        "— the four-factor product is charging what it runs",
    )
    return 0


# ── 4. pairing still buys variance, at every scenario count ───────────────────


def _bench_pairing() -> Int:
    print("  [4] the variance reduction, re-measured as a regression gate")
    print("      scenarios  ms       paired var    unpaired var   ratio")
    var sizes = List[Int]()
    sizes.append(32)
    sizes.append(64)
    sizes.append(128)
    _ = _time_audit(8)  # untimed warm-up
    var ok = True
    var worst: Float64 = 0.0
    var have = False
    for i in range(len(sizes)):
        var n = sizes[i]
        var best: Float64 = 0.0
        var ratio: Float64 = 0.0
        var pv: Float64 = 0.0
        var uv: Float64 = 0.0
        var seen = False
        for _ in range(3):
            var m = _time_audit(n)
            if Int(m[1]) != STRAT_OK or m[5] != 1.0:
                ok = False
            ratio = m[2]
            pv = m[3]
            uv = m[4]
            if not seen or m[0] < best:
                best = m[0]
                seen = True
        print("      ", n, best / 1.0e6, pv, uv, ratio)
        if not have or ratio < worst:
            worst = ratio
        have = True
    print("      worst ratio across scenario counts =", worst, "x")
    if not ok or not have:
        print("  FAIL an audit refused, or a scenario was not bit-identical across strategies")
        return 1
    if worst < 20.0:
        print("  FAIL pairing no longer reduces variance: worst ratio =", worst)
        return 1
    print(
        "  PASS the paired comparison carries at least", worst, "x less variance than the",
        "unpaired one at every scenario count — the property this package exists for, gated",
    )
    return 0


# ── 5. a refusal costs the same whatever it refuses ───────────────────────────


def _bench_refusal() -> Int:
    print("  [5] refusal cost against the size of the request it refuses")
    print("      horizon  ns")
    var sizes = List[Int]()
    sizes.append(2048)
    sizes.append(4096)
    sizes.append(8192)
    sizes.append(16384)
    _ = _time_refusal(2048)  # untimed warm-up
    var total = List[Float64]()
    var ok = True
    for i in range(len(sizes)):
        var best: Float64 = 0.0
        var have = False
        for _ in range(3):
            var m = _time_refusal(sizes[i])
            if Int(m[1]) != STRAT_ERR_WORK_BUDGET:
                ok = False
            if not have or m[0] < best:
                best = m[0]
                have = True
        total.append(best)
        print("      ", sizes[i], best)
    var growth = _spread(total[0], total[3])
    print("      request grew 8x; refusal cost grew", growth, "x")
    if not ok:
        print("  FAIL a request that should be over budget was not refused")
        return 1
    if growth > 3.0:
        print("  FAIL refusal cost grows with the request — work is happening before the",
              "budget check:", growth)
        return 1
    print(
        "  PASS an 8x larger request is refused for the same cost, so nothing is generated",
        "before the charge is decided",
    )
    return 0


# ── 6. an accepted equilibrium request is one the module finishes ─────────────


def _bench_equilibrium_charge() -> Int:
    print("  [6] equilibrium requests that saturate the work budget, two of each kind")
    print("      p     a     iters  charge       % ceil   s        ns/unit")
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    var have = False
    var ok = True
    var slowest: Float64 = 0.0
    var warm = _eq_tensor(2, 8)
    _ = _time_enumeration(warm, 2, 8)
    _ = _time_regret(warm, 2, 8, 4)

    var ep = List[Int]()
    var ea = List[Int]()
    ep.append(2)
    ea.append(406)
    ep.append(3)
    ea.append(81)
    for i in range(2):
        var payoffs = _eq_tensor(ep[i], ea[i])
        var best: Float64 = 0.0
        var charge: Float64 = 0.0
        var seen = False
        for _ in range(2):
            var m = _time_enumeration(payoffs, ep[i], ea[i])
            if Int(m[1]) != STRAT_OK or m[2] <= 0.0:
                ok = False
            charge = m[2]
            if not seen or m[0] < best:
                best = m[0]
                seen = True
        if charge <= 0.0:
            ok = False
            continue
        var unit = best / charge
        print(
            "      ", ep[i], ea[i], 0, Int(charge), charge / 536870912.0 * 100.0,
            best / 1.0e9, unit,
        )
        if best > slowest:
            slowest = best
        if not have or unit < lo:
            lo = unit
        if not have or unit > hi:
            hi = unit
        have = True

    var rp = List[Int]()
    var ra = List[Int]()
    var ri = List[Int]()
    rp.append(2)
    ra.append(64)
    ri.append(1340)
    rp.append(8)
    ra.append(3)
    ri.append(212)
    for i in range(2):
        var payoffs = _eq_tensor(rp[i], ra[i])
        var best: Float64 = 0.0
        var charge: Float64 = 0.0
        var seen = False
        for _ in range(2):
            var m = _time_regret(payoffs, rp[i], ra[i], ri[i])
            if Int(m[1]) != STRAT_OK or m[2] <= 0.0:
                ok = False
            charge = m[2]
            if not seen or m[0] < best:
                best = m[0]
                seen = True
        if charge <= 0.0:
            ok = False
            continue
        var unit = best / charge
        print(
            "      ", rp[i], ra[i], ri[i], Int(charge), charge / 536870912.0 * 100.0,
            best / 1.0e9, unit,
        )
        if best > slowest:
            slowest = best
        if not have or unit < lo:
            lo = unit
        if not have or unit > hi:
            hi = unit
        have = True

    var spread = _spread(lo, hi)
    print("      slowest accepted request", slowest / 1.0e9, "s   per-unit SPREAD =", spread, "x")
    # The edge of the gate, and it is deterministic: 406 actions fits and 407 does not.
    var edge_ok = eq_enumeration_charge(2, 406) > 0 and eq_enumeration_charge(2, 407) < 0
    edge_ok = edge_ok and eq_iteration_charge(2, 64, 4000) < 0
    if not ok or not have:
        print("  FAIL a saturating request refused or reported no charge")
        return 1
    if not edge_ok:
        print("  FAIL the charge ceiling does not refuse the shape one step past it")
        return 1
    if slowest > 5.0e9:
        print("  FAIL an accepted request took", slowest / 1.0e9, "s — the budget under-charges")
        return 1
    if spread > 20.0:
        print("  FAIL the charge mis-ranks equilibrium shapes: spread =", spread)
        return 1
    print(
        "  PASS every request the budget accepts finished, the slowest in", slowest / 1.0e9,
        "s, and the shape one step past the ceiling is refused",
    )
    return 0


# ── 7. iteration cost is linear, and the solver converges ─────────────────────


def _bench_equilibrium_convergence() -> Int:
    print("  [7] adaptive play: cost linear in iterations, exploitability falling")
    print("      iters  charge       ms        ns/unit")
    var ladder = List[Int]()
    ladder.append(250)
    ladder.append(500)
    ladder.append(1000)
    ladder.append(2000)
    var game = _eq_tensor(3, 8)
    _ = _time_regret(game, 3, 8, 4)
    var times = List[Float64]()
    var charges = List[Float64]()
    var ok = True
    for i in range(4):
        var best: Float64 = 0.0
        var charge: Float64 = 0.0
        var seen = False
        for _ in range(2):
            var m = _time_regret(game, 3, 8, ladder[i])
            if Int(m[1]) != STRAT_OK:
                ok = False
            charge = m[2]
            if not seen or m[0] < best:
                best = m[0]
                seen = True
        times.append(best)
        charges.append(charge)
        print("      ", ladder[i], Int(charge), best / 1.0e6, best / charge)
    var p = _exponent(times[0], times[3], Int(charges[0]), Int(charges[3]))
    print("      growth exponent p in t ~ charge^p =", p)

    print("      measured exploitability of the same solver, 3 players x 4 actions")
    print("      iters  residual")
    var quality = List[Int]()
    quality.append(25)
    quality.append(50)
    quality.append(200)
    quality.append(800)
    var small = _eq_tensor(3, 4)
    var residuals = List[Float64]()
    for i in range(4):
        var m = _time_regret(small, 3, 4, quality[i])
        if Int(m[1]) != STRAT_OK or m[3] < 0.0:
            ok = False
        residuals.append(m[3])
        print("      ", quality[i], m[3])
    var falling = True
    for i in range(3):
        if residuals[i + 1] >= residuals[i]:
            falling = False
    var reduction = _spread(residuals[3], residuals[0])
    print("      exploitability fell", reduction, "x over a 32x iteration ladder")
    if not ok:
        print("  FAIL an adaptive-play run refused inside the budget")
        return 1
    if p > 1.5:
        print("  FAIL iteration cost is superlinear in the iteration count: p =", p)
        return 1
    if not falling or reduction < 5.0:
        print("  FAIL the solver is not converging:", residuals[0], "->", residuals[3])
        return 1
    print(
        "  PASS cost is linear in the iteration count and exploitability fell monotonically by",
        reduction, "x — a solver that stopped converging would fail HERE and nowhere else",
    )
    return 0


# ── 8. the RANKING's charge model, and the verdicts it produces ───────────────
# Two sections, and the second one is the more valuable of the pair because it is NOISE-FREE.
#
# `tourney_rank_flat`'s cost is dominated by two FIXED costs that no `n_strategies *
# n_replications` product can see: one `inference_t_quantile` bisection per strategy (MEASURED
# 236-250 us in situ) and one `inference_t_sf_two_sided` per pair (1.4-1.6 us). At 1024
# strategies the quantile alone is 1.2 s, so the charge model is the only thing standing between
# a caller and an accepted request that looks like a hang. Section 8 measures nanoseconds per
# CHARGED UNIT at seven accepted shapes spanning 2 to 4096 replications and 32 to 372 strategies,
# and gates the SPREAD rather than any absolute time.
#
# The band is wide on purpose and the width is measured, not guessed: repeated timings of an
# IDENTICAL call on this machine under the JIT differ by 3-7x (54 ms and 388 ms for the same
# 128-strategy ranking in one process), so a tight band would fail on scheduler noise and prove
# nothing. What it still catches is a charge model that drops a factor: removing the per-pair term
# would shrink the charge of a pair-heavy shape tenfold and push its cost-per-unit straight out of
# the band.
#
# Section 9 gates the ANSWERS instead of the clock, on a fixed seed, so it has no noise at all: a
# threshold gap swept from 0 upwards must produce NO SIGNIFICANT DIFFERENCE at a gap of zero and a
# decided winner at the widest gap, with the p-value falling monotonically in between. A ranking
# that always named a winner, or that reported a tie for a real difference, fails there. It also
# runs the composition end to end — `crn_evaluate_policies` produces the payoff block and
# `tourney_rank_flat` consumes it with no reshaping, both being strategy-major — so a layout
# disagreement between the two modules cannot pass unnoticed.


def _tourney_block(n_strategies: Int, n_factors: Int) -> List[Float64]:
    """An `n_strategies x (n_factors + 1)` THRESHOLD block with a DISTINCT threshold per row.

    Distinct, unlike `_threshold_block`'s `s % 32` walk, because two identical rows produce
    identical payoffs, and identical payoffs take the deterministic branch that SKIPS the
    p-value entirely. A block with repeats would quietly measure a ranking that never called the
    expensive frozen function the charge model exists to account for.
    """
    var out = List[Float64]()
    for s in range(n_strategies):
        for _ in range(n_factors):
            out.append(1.0)
        out.append(0.20 + 0.0005 * Float64(s))
    return out^


def _outcomes(s: Int, r: Int, h: Int, gap_kind: Int) -> List[Float64]:
    """A real payoff block from `crn_evaluate_policies`, strategy-major. Empty on refusal.

    `gap_kind < 0` builds the distinct-threshold block over `s` strategies. `gap_kind >= 0`
    builds a TWO-strategy block whose thresholds are 0.40 and `0.40 + gap_kind/100`, so a
    `gap_kind` of 0 is two IDENTICAL policies — the case a ranking must call a tie.
    """
    var block = _tourney_block(s, 1)
    if gap_kind >= 0:
        block = _threshold_pair(0.40, 0.40 + 0.01 * Float64(gap_kind))
    var run = crn_evaluate_policies(
        7, 3, r, h, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        block, s, 2, 0.9,
    )
    if run.status != STRAT_OK or run.n_absent != 0:
        return List[Float64]()
    return run.payoffs.copy()


def _time_rank(outcomes: List[Float64], s: Int, r: Int) -> List[Float64]:
    """THE ONLY timed `tourney_rank_flat` call in this file. Flat slots, in this order:

    `[0] ns  [1] status  [2] charge  [3] verdict  [4] n_significant  [5] n_comparisons`
    `[6] winner  [7] first pair's p  [8] first pair's paired variance  [9] min variance ratio`

    Both tournament sections read it, so the driver is instantiated ONCE. That is not tidiness:
    this file's sibling did not finish COMPILING in ten minutes when its timed calls were written
    inline, and a benchmark that cannot be built is indistinguishable from one whose kernels hang.
    """
    var t0 = perf_counter_ns()
    var t = tourney_rank_flat(outcomes, s, r, 0.95, 0.05, TOURNEY_METHOD_HOLM, True, 1.0e-12)
    var dt = perf_counter_ns() - t0
    var out = List[Float64]()
    out.append(Float64(Int(dt)))
    out.append(Float64(t.status))
    out.append(Float64(t.work_charge))
    out.append(Float64(t.verdict))
    out.append(Float64(t.n_significant))
    out.append(Float64(t.n_comparisons))
    out.append(Float64(t.winner))
    # The first pair exists whenever the ranking did; a refusal leaves the lists EMPTY, so the
    # absent slots stay 0.0 rather than reading past the end of a list.
    if len(t.pair_p) > 0:
        out.append(t.pair_p[0])
        out.append(t.pair_paired_variance[0])
    else:
        out.append(0.0)
        out.append(0.0)
    if t.has_min_variance_ratio:
        out.append(t.min_variance_ratio)
    else:
        out.append(0.0)
    return out^


def _bench_tournament_charge() -> Int:
    print("  [8] the ranking's declared charge against measured time")
    print("      s     R     pairs   charge      %ceil   ms      ns/charged-unit")
    var ss = List[Int]()
    var rs = List[Int]()
    ss.append(32); rs.append(2)
    ss.append(128); rs.append(2)
    ss.append(372); rs.append(2)
    ss.append(315); rs.append(64)
    ss.append(146); rs.append(1024)
    ss.append(64); rs.append(2048)
    ss.append(82); rs.append(4096)
    var warm = _outcomes(4, 8, 8, -1)
    _ = _time_rank(warm, 4, 8)  # untimed warm-up: the first timed call otherwise carries the JIT
    var ok = True
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    var slowest: Float64 = 0.0
    var seen = False
    for i in range(len(ss)):
        var s = ss[i]
        var r = rs[i]
        var charge = tourney_work_charge(s, r)
        if charge < 0:
            print("       (refused by the charge model, not measured)", s, r)
            ok = False
            continue
        var outcomes = _outcomes(s, r, 8, -1)
        if len(outcomes) != s * r:
            print("       (scenario generation refused)", s, r, len(outcomes))
            ok = False
            continue
        var best: Float64 = 0.0
        for k in range(3):
            var m = _time_rank(outcomes, s, r)
            if Int(m[1]) != STRAT_OK or Int(m[2]) != charge:
                ok = False
            if k == 0 or m[0] < best:
                best = m[0]
        var per_unit = best / Float64(charge)
        print("      ", s, r, tourney_pair_count(s), charge,
              100.0 * Float64(charge) / 536870912.0, best / 1.0e6, per_unit)
        if not seen or per_unit < lo:
            lo = per_unit
        if not seen or per_unit > hi:
            hi = per_unit
        if best > slowest:
            slowest = best
        seen = True
    var drift = _spread(lo, hi)
    print("      cost per charged unit spans", lo, "to", hi, "ns =", drift, "x;",
          "slowest accepted shape", slowest / 1.0e6, "ms")
    # The boundary itself: one more strategy at two replications is refused, and the refusal is a
    # DECLARED -1 rather than a wrapped product.
    var boundary_ok = tourney_work_charge(372, 2) > 0 and tourney_work_charge(374, 2) == -1
    boundary_ok = boundary_ok and tourney_work_charge(1024, 2) == -1
    if not ok or not seen:
        print("  FAIL a shape inside the declared budget refused, or its charge disagreed")
        return 1
    if not boundary_ok:
        print("  FAIL the budget boundary moved:", tourney_work_charge(372, 2),
              tourney_work_charge(374, 2))
        return 1
    if lo < 0.05 or hi > 4.0 or drift > 12.0:
        print("  FAIL the charge no longer tracks measured time:", lo, "to", hi, "ns/unit")
        return 1
    if slowest > 3.0e9:
        print("  FAIL the worst request the budget accepts takes", slowest / 1.0e9, "s")
        return 1
    print(
        "  PASS the charge tracks measured cost within", drift, "x across a 2048x range of",
        "replication counts, and the worst shape the budget accepts finishes in",
        slowest / 1.0e6, "ms",
    )
    return 0


# ── 9. the verdicts themselves, on a fixed seed, with no timing in the gate ───


def _bench_tournament_verdicts() -> Int:
    print("  [9] verdicts across a threshold gap — crn_evaluate_policies into tourney_rank_flat")
    print("      gap    verdict  winner  p            paired var    ratio")
    var gaps = List[Int]()
    gaps.append(0)
    gaps.append(2)
    gaps.append(5)
    gaps.append(10)
    gaps.append(20)
    var reps = 128
    var ok = True
    var ps = List[Float64]()
    var verdicts = List[Int]()
    for i in range(len(gaps)):
        var g = gaps[i]
        # A gap of 0 is two IDENTICAL thresholds; `_outcomes` reserves the negative kind for the
        # many-strategy block so a zero gap and "no gap requested" cannot collide.
        var outcomes = _outcomes(2, reps, 32, g)
        if len(outcomes) != 2 * reps:
            ok = False
            print("       (generation refused at gap)", g, len(outcomes))
            continue
        # Through the SAME one-call helper the timing section uses, so `tourney_rank_flat` is
        # instantiated exactly once in this file. Two call sites of a driver this large is what
        # took the sibling benchmark's compile past ten minutes.
        var m = _time_rank(outcomes, 2, reps)
        if Int(m[1]) != STRAT_OK or Int(m[5]) != 1:
            ok = False
        print("      ", g, Int(m[3]), Int(m[6]), m[7], m[8], m[9])
        ps.append(m[7])
        verdicts.append(Int(m[3]))
    if not ok or len(ps) != len(gaps):
        print("  FAIL a ranking refused inside the budget")
        return 1
    # A zero gap must tie, and the widest gap must decide. Both directions, or the gate is
    # satisfied by a ranking that always answers the same thing.
    var ties_at_zero = verdicts[0] == STRAT_VERDICT_NO_DIFFERENCE and ps[0] == 1.0
    var decides_at_widest = verdicts[len(gaps) - 1] == STRAT_VERDICT_A_BETTER
    var monotone = True
    for i in range(len(ps) - 1):
        if ps[i + 1] > ps[i]:
            monotone = False
    if not ties_at_zero:
        print("  FAIL two IDENTICAL policies were not reported as indistinguishable:",
              verdicts[0], ps[0])
        return 1
    if not decides_at_widest:
        print("  FAIL a 0.20 threshold gap over 128 paired scenarios was not detected:",
              verdicts[len(gaps) - 1])
        return 1
    if not monotone:
        print("  FAIL the p-value does not fall as the gap widens:", ps[0], "->",
              ps[len(gaps) - 1])
        return 1
    print(
        "  PASS a zero gap ties at p = 1.0 with no winner and a 0.20 gap is decided, with the",
        "p-value falling monotonically between them — a ranking that always named a winner, or",
        "always tied, fails here regardless of how fast it is",
    )
    return 0


def main():
    print("\n=== bench_strategy: scenarios, replay, and the price of pairing ===")
    print("Gates are on SHAPE. Absolute times are informational and are not gated.\n")
    var failures = 0
    failures += _bench_tape()
    print("")
    failures += _bench_replay()
    print("")
    failures += _bench_charge()
    print("")
    failures += _bench_pairing()
    print("")
    failures += _bench_refusal()
    print("")
    failures += _bench_equilibrium_charge()
    print("")
    failures += _bench_equilibrium_convergence()
    print("")
    failures += _bench_tournament_charge()
    print("")
    failures += _bench_tournament_verdicts()
    print("")
    if failures == 0:
        print("BENCH_GATE strategy PASS")
    else:
        print("BENCH_GATE strategy FAIL " + String(failures))
