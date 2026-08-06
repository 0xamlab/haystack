"""`bench_queueing_validation.mojo` — the simulator against closed-form queueing theory.

Why this file is the credibility deliverable, and not the event rate
-------------------------------------------------------------------
An event rate is unfalsifiable. A simulator that processes 10 million events per second and
disagrees with `L = rho/(1-rho)` is not fast, it is wrong, and no throughput figure redeems it.
Queueing theory supplies EXACT answers — algebra, not estimates — so a discrete-event simulator
has a right answer to be wrong against. This file runs the simulator, forms confidence intervals
from independent replications, and reports whether each analytical value falls INSIDE its
interval, printed side by side with the replication count.

If an analytical value falls outside its interval that is a DEFECT REPORT, not a reason to widen
the interval. Nothing in this file has a tolerance a failing comparison could be nursed through:
the interval is what the replications produced, and `_covers` is a plain inequality.

The five references, and the exact form each one is checked in
-------------------------------------------------------------
1. **M/M/1** — `Wq = rho/(mu-lambda)`, `W = 1/(mu-lambda)`, `L = rho/(1-rho)`,
   utilisation `= rho`. Three utilisations (0.5, 0.8, 0.9), four metrics each.
2. **M/M/c** — `Wq = C(c,A)/(c*mu-lambda)` with `C` the exact Erlang C, then `W = Wq + 1/mu`,
   `L = lambda*W`. Two configurations (c=3 and c=5, both at rho = 0.8).
3. **Erlang B** — the M/M/c/c LOSS system. `B(A,c)` by the exact recursion
   `B(A,n) = A*B(A,n-1) / (n + A*B(A,n-1))`. Two quantities are checked per configuration: the
   fraction of arrivals blocked (which equals `B` by PASTA, since arrivals are Poisson) and the
   time-average number of busy servers (which equals the carried traffic `A*(1-B)` exactly).
   Both frozen Erlang B kernels are also cross-checked against each other — see the note on the
   duplicate signatures below.
4. **Erlang C** — the DELAY probability in an M/M/c queue, measured as the fraction of arrivals
   whose waiting time is strictly positive. Again PASTA makes the arrival-average equal the
   time-average `P(all c servers busy)`, which is Erlang C.
5. **Lindley recursion** — `W_{n+1} = max(0, W_n + S_n - A_{n+1})`. This is the strongest check
   available anywhere in this file and it is not statistical: it is a PER-CUSTOMER identity on a
   single sample path. It is checked in two forms, and the distinction matters —

     * the ABSOLUTE-TIME form `D_i = max(A_i, D_{i-1}) + S_i`, `W_i = max(0, D_{i-1} - A_i)`,
       performs exactly the additions `resource_serve_flat` performs, and is therefore gated
       BIT-EXACT on every customer. Not "within a tolerance" — bit-for-bit, all n of them.
     * the canonical GAP form above accumulates `W_i + S_i - g_{i+1}` where the engine
       accumulates absolute instants, so the two differ by floating-point summation ORDER alone.
       The magnitude that sets that difference is the CLOCK, not the wait: the engine forms every
       wait as `D_{i-1} - A_i`, a difference of two instants of magnitude up to the horizon, so
       the absolute rounding floor of a 0.001-long wait late in a run of horizon 6250 is
       `eps * 6250`, not `eps * 0.001`. A tolerance built from the wait's own magnitude is
       therefore the WRONG error model for this one comparison and rejects rounding as if it were
       disagreement — which is exactly what happened when this file was first run, and it is
       recorded here because the fix is a derivation and not a widening. The gate is stated two
       ways: per customer against `de_scaled_tol_additions(horizon, 0, i+1)`, and in aggregate as
       the largest deviation expressed in ULPS OF THE CLOCK, which must stay inside the tree's
       own 256-ulp base budget. Observed: 2.8 ulps at rho = 0.5 rising to 17.5 at rho = 1.05,
       against a ceiling of 256. A genuine disagreement between the two recursions would be of
       order one wait unit, which is about 1e12 clock ulps, so the margin is not the gate's
       weakness.

   The pathwise identity does not need a steady state, so it is also checked at rho = 1.05 where
   no closed form exists at all.

Little's law is checked on the SIMULATED OUTPUT, which is a different claim
--------------------------------------------------------------------------
Sections 1-4 compare the simulator to external algebra. Section 6 compares the simulator to
ITSELF: over a complete observation window the time integral of the number in system equals the
sum of every customer's sojourn time, term for term, so `L = lambda * W` must hold to
floating-point rounding on the run's own numbers with no theory involved.
`resource_serve_flat` computes that check internally and reports the gap; this file gates it and
prints the gap. It is an internal-consistency proof, so it holds at every utilisation including
the unstable ones, and it would catch an accounting error that a CI comparison could absorb.

The warm-up question, answered in both directions
-------------------------------------------------
Section 7 exists because warm-up detection has to EARN its place rather than be decoration. The
same replications are estimated twice — once retaining every customer, once discarding the
transient the MSER-5 pilot identified — and the un-truncated estimate is shown to be biased AWAY
from the analytical value by enough that its 95% interval EXCLUDES it. That direction is gated:
if the un-truncated estimator ever started covering the exact answer at these parameters, either
the transient stopped existing or the estimator stopped being computed.

A FINDING IS REPORTED THERE, AND IT IS NOT A PASS. MSER-5 selects a truncation of zero at run
lengths where a measurable initialisation bias remains. At rho = 0.8 with 200 replications the
observed picture is:

    n      MSER-5 d    bias of the no-discard mean    |bias| / CI half-width   covers Wq = 4
    100    45          -0.903                          3.18                    NO
    150    40          -0.593                          1.99                    NO
    200    0           -0.452                          1.55                    NO
    400    0           -0.123                          0.46                    yes
    1000   460         -0.150                          0.84                    yes
    4000   0           -0.032                          0.34                    yes

At n = 200 MSER-5 discards nothing and `replicate_mm1_flat` consequently reports 1 of 4 metrics
covered. That is a WARM-UP DETECTOR weakness, not a simulator-mechanics defect — the mechanics
are proved exactly by section 5's bit-exact Lindley identity and section 6's Little's law — but
it is a real limitation of the shipped pipeline and it is printed as a FINDING on every run.
The cause is structural: MSER's score is the estimated standard error of the retained mean, which
grows like `1/(m-d)` as `d` rises, so truncation only wins when the transient's contribution to
the batch-mean spread exceeds the variance cost of the shorter sample. On a long, noisy series the
transient is a small fraction of the total spread and `d = 0` wins even though bias remains.

Coverage is statistical, so the count is gated and not each verdict
------------------------------------------------------------------
There are 29 interval-coverage checks in sections 1-4. Each one has a 5% chance of missing by
construction at a 95% level, so `P(all 29 cover) = 0.95^29 = 0.226` — gating "every interval
covers" would be a gate that fails three runs in four on a correct simulator. The hard gate is
therefore on the MISS COUNT: 6 or more misses fails. Under independent intervals
`P(X >= 6) = 0.0028` for `Binomial(29, 0.05)`, and the four metrics within one configuration are
strongly correlated (a shifted `Wq` shifts `W` and `L` with it), so in practice misses arrive in
clusters of up to three and the threshold is roughly "two whole configurations may miss".

Every individual verdict is still printed with its interval, its exact value and its replication
count, because the count alone would hide WHICH reference disagreed.

The gates whose answer does not depend on statistics at all are the ones that carry the weight:

  * Lindley absolute-time form BIT-EXACT on every customer, at four utilisations.
  * Little's law exact on the simulator's own output at every configuration.
  * The two frozen Erlang B kernels agree with each other.
  * The Student-t quantile matches published two-sided 95% table values at ten degrees of
    freedom — which is what makes the intervals above intervals rather than arithmetic.
  * Six NEGATIVE CONTROLS in section 9, each one a deliberately wrong input that the
    corresponding gate must reject. A gate that cannot fail is not a gate, and the controls are
    re-run on every invocation so the file proves its own detection power rather than asserting
    it.

The gate has been PROVEN to fail, twice, on mutated copies
---------------------------------------------------------
A gate nobody has seen fail is a claim, not a gate. Two mutants were built in `/tmp` (never in
the repository) and run:

  * MUTANT A — a STREAM COLLISION, which is the realistic defect this package's docstrings warn
    about: service times drawn on the ARRIVAL stream (`qs_interarrivals(mu, ...)` in place of
    `qs_service_times(mu, ...)`, four call sites). The marginal distribution is still
    Exponential(mu), so every distributional check still passes and every input still looks
    right — only the queueing algebra can see it, because service is now a deterministic
    multiple of the preceding gap. Result: 8 of 29 intervals missed, Erlang B off by 19-27% and
    the carried traffic off by 12-27%, `BENCH_GATE queueing_validation FAIL 1`, exit code 1.
    That is the case this file exists for: a bug that no self-consistency test can detect and
    that closed-form theory catches immediately.
  * MUTANT B — the `max(0, .)` clamp removed from the absolute-time Lindley reference. Result:
    bit-exactness collapsed from 5000/5000 to 1/5000 at every utilisation,
    `BENCH_GATE queueing_validation FAIL 4`, exit code 1.

Section 9's six negative controls re-prove the same discrimination in-process on every run, so
the file does not depend on anyone remembering to re-run a mutant.

No wall clock anywhere
----------------------
Nothing in this file is timed and nothing in it can fail because of machine load. Every gate is
an interval membership, an integer identity or a bit-comparison, so the verdict is identical on a
quiet machine and on one at load average 550 (which is where these numbers were produced — the
runner should record the load average beside the log for the reader's benefit, since it affects
only how long the file takes, never what it decides).

Where the loss-system driver lives, and why that is a reported gap
-----------------------------------------------------------------
`discrete_event.resource` is an infinite-buffer pool: a job that finds every server busy waits.
An M/M/c/c LOSS system needs a job that finds every server busy to be REJECTED, which no shipped
driver does, so `_loss_serve` below is new code. It is built on the same `_EventHeap` seam
`resource.mojo` uses and follows the same conventions (departures at calendar priority 0 so a
coincident departure frees its server before an arrival is tested — which matters more in a loss
system than in a queue, because there the convention decides whether that arrival is blocked at
all). It sits in this benchmark rather than in the package because the package is being worked on
concurrently; **a loss-system driver belongs in `discrete_event/` as additive new code and its
absence is reported as a package gap.** Same for a Jackson-network product-form solver, which
does not exist anywhere in `mojo/engine/` and is not checked here.

Two frozen Erlang B kernels, with reversed argument order
---------------------------------------------------------
`queueing.erlang_b(traffic_intensity: Float64, servers: Int)` and
`telecommunications.erlang_b(n: Int, a: Float64)` are both frozen, take their arguments in the
OPPOSITE order, and use different recursions (forward on `B`, inverse on `1/B`). Neither is
called by `discrete_event/`. This file calls the `queueing` one for its reference values and
cross-checks the `telecommunications` one against it, because a caller who reaches for the wrong
signature gets a plausible number rather than a type error. Their agreement is gated.

All inputs are generated by the seeded frozen counter-based generator or by closed-form
arithmetic. There is no unseeded randomness anywhere in this file, so a re-run reproduces every
number in the log bit for bit.
"""
from std.math import abs as fabs
from std.time import perf_counter_ns

from inference.core import inference_t_quantile
from queueing import erlang_b as queueing_erlang_b, mmc_erlang_c
from telecommunications import erlang_b as telecom_erlang_b

from discrete_event.calendar import _EventHeap, _heap_drop_root, _heap_push, _heap_size
from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NEGATIVE_DURATION,
    DE_ERR_NON_FINITE,
    DE_ERR_TIME_BACKWARD,
    DE_ERR_WARMUP_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_JOBS,
    DE_MAX_SERVERS,
    DE_MAX_WORK,
    DE_OK,
    de_agrees,
    de_all_finite,
    de_finite,
    de_heap_levels,
    de_nondecreasing,
    de_product_fits,
    de_scaled_tol_additions,
    de_status_name,
)
from discrete_event.queue_sim import (
    qs_arrival_times,
    qs_closed_form_flat,
    qs_interarrivals,
    qs_service_times,
)
from discrete_event.replicate import replicate_ci_flat, replicate_mm1_flat
from discrete_event.resource import resource_serve_flat
from discrete_event.warmup import warmup_bias_audit, warmup_mser_flat

# One seed for the whole file, so every number below is reproducible from the log alone.
comptime QV_SEED: Int = 20260731
comptime QV_LEVEL: Float64 = 0.95
comptime QV_BATCH: Int = 5

# 29 coverage checks at a 95% level: 6 misses or more fails. See the module docstring for the
# binomial arithmetic behind the threshold.
comptime QV_MAX_MISSES: Int = 6


# ── shared helpers ────────────────────────────────────────────────────────────


def _covers(lo: Float64, hi: Float64, target: Float64) -> Bool:
    """Interval membership, with no tolerance. An epsilon here would report coverage for a value
    the replications excluded, which is the one thing this file must never do."""
    if not de_finite(lo) or not de_finite(hi) or not de_finite(target):
        return False
    return target >= lo and target <= hi


def _ones(n: Int) -> List[Int]:
    """FIFO priorities — every customer at rank 0, so the discipline is first-come-first-served
    and the closed forms apply."""
    var out = List[Int]()
    for _ in range(n):
        out.append(0)
    return out^


def _pct(a: Float64, b: Float64) -> Float64:
    if b == 0.0:
        return 0.0
    return 100.0 * (a - b) / b


# ── the M/M/c/c loss driver (new code; see the module docstring) ───────────────


@fieldwise_init
struct LossRun(Copyable, Movable):
    """One run of an M/M/c/c loss system: c servers, NO waiting room.

    `blocking_fraction` counts only RETAINED arrivals (index >= `warmup_jobs`), and
    `mean_busy_servers` integrates only over the retained window, so the two quantities answer
    the same question about the same stretch of the run.

    Every `has_*` flag guards the field named after it and an absent slot holds exactly `0.0`,
    matching `discrete_event.resource` — a blocking fraction of zero is a real answer for a
    lightly-loaded group, so the flag and not the value says whether the number exists.
    """

    var status: Int
    var n_offered: Int
    var n_retained: Int
    var n_blocked: Int
    var n_accepted: Int
    var capacity: Int
    var events_processed: Int
    var work_charged: Int
    var horizon: Float64
    var observed_from: Float64
    var observed_span: Float64
    var has_blocking: Bool
    var blocking_fraction: Float64
    var has_busy: Bool
    var mean_busy_servers: Float64


def _loss_refusal(code: Int) -> LossRun:
    return LossRun(code, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, False, 0.0, False, 0.0)


def _loss_work_charge(n_jobs: Int, capacity: Int) -> Int:
    """Charged operations, or -1 when the charge does not fit `DE_MAX_WORK`.

    The calendar holds all `n` arrivals plus at most `capacity` in-service departures, and at
    most `2n` entries are pushed and popped over the run (every arrival, plus one departure per
    accepted arrival), each at a cost of one heap depth. Charging `n` alone would drop the depth
    factor, and a budget that counts one factor of a product is not a budget.
    """
    if n_jobs <= 0:
        return 0
    if capacity < 0 or capacity > DE_MAX_SERVERS:
        return -1
    var resident = n_jobs + capacity
    if resident < 0:
        return -1
    var levels = de_heap_levels(resident)
    if not de_product_fits(4 * n_jobs, levels, DE_MAX_WORK):
        return -1
    return 4 * n_jobs * levels


def _loss_serve(
    arrival: List[Float64], service: List[Float64], n_jobs: Int, capacity: Int,
    warmup_jobs: Int,
) -> LossRun:
    """Run `n_jobs` Poisson arrivals at a group of `capacity` servers with NO waiting room.

    An arrival that finds every server busy is LOST — it never enters the system and never
    generates a departure. That is the whole difference from `resource_serve_flat`, and it is
    what makes the Erlang B blocking formula the right reference instead of Erlang C.

    Coincident events resolve departures first, exactly as `discrete_event.resource` does:
    departures carry calendar priority 0 and arrivals carry 1. In an infinite-buffer queue that
    convention only affects the reported maximum queue length; HERE it decides whether a
    coincident arrival is blocked, so it is stated rather than left implicit. With continuous
    service times a coincidence has probability zero, but determinism is not a probability claim.

    Refusals mirror `resource_serve_flat` code for code, and all of them are checked BEFORE the
    first subscript because a read past a `List` end is an uncatchable abort that ends the whole
    worker process rather than raising something a caller could handle.
    """
    if n_jobs > len(arrival) or n_jobs > len(service):
        return _loss_refusal(DE_ERR_COUNT)
    if n_jobs <= 0:
        return _loss_refusal(DE_ERR_EMPTY)
    if n_jobs > DE_MAX_JOBS:
        return _loss_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if capacity < 1 or capacity > DE_MAX_SERVERS:
        return _loss_refusal(DE_ERR_CAPACITY)
    if warmup_jobs < 0 or warmup_jobs >= n_jobs:
        return _loss_refusal(DE_ERR_WARMUP_RANGE)
    if not de_all_finite(arrival, n_jobs) or not de_all_finite(service, n_jobs):
        return _loss_refusal(DE_ERR_NON_FINITE)
    if arrival[0] < 0.0 or not de_nondecreasing(arrival, n_jobs):
        return _loss_refusal(DE_ERR_TIME_BACKWARD)
    for i in range(n_jobs):
        if service[i] < 0.0:
            return _loss_refusal(DE_ERR_NEGATIVE_DURATION)
    var charge = _loss_work_charge(n_jobs, capacity)
    if charge < 0:
        return _loss_refusal(DE_ERR_WORK_BUDGET)

    var blocked_flag = List[Int]()
    for _ in range(n_jobs):
        blocked_flag.append(0)

    var cal = _EventHeap()
    var seq = 0
    for i in range(n_jobs):
        _heap_push(cal, arrival[i], 1, seq, 0, i)
        seq += 1

    var free = capacity
    var accepted = 0
    var blocked = 0
    var events = 0
    var t_prev: Float64 = 0.0
    var busy_area: Float64 = 0.0
    var observed_from = arrival[warmup_jobs]

    while _heap_size(cal) > 0:
        var t = cal.t[0]
        var kind = cal.kind[0]
        var job = cal.ent[0]
        _heap_drop_root(cal)
        events += 1

        # Integrate the number of busy servers over [t_prev, t] clipped to the window, using the
        # state BEFORE this event — which is what "busy during that interval" means.
        var lo = t_prev
        if observed_from > lo:
            lo = observed_from
        if t > lo:
            busy_area += Float64(capacity - free) * (t - lo)
        t_prev = t

        if kind == 0:
            if free > 0:
                free -= 1
                accepted += 1
                var dep = t + service[job]
                if not de_finite(dep):
                    return _loss_refusal(DE_ERR_NON_FINITE)
                _heap_push(cal, dep, 0, seq, 1, job)
                seq += 1
            else:
                blocked += 1
                blocked_flag[job] = 1
        else:
            free += 1

    var horizon = t_prev
    var span = horizon - observed_from
    var n_retained = n_jobs - warmup_jobs

    var retained_blocked = 0
    for i in range(warmup_jobs, n_jobs):
        retained_blocked += blocked_flag[i]

    var has_block = False
    var block_frac: Float64 = 0.0
    if n_retained > 0:
        var bf = Float64(retained_blocked) / Float64(n_retained)
        if de_finite(bf):
            has_block = True
            block_frac = bf

    var has_busy = False
    var busy: Float64 = 0.0
    if span > 0.0 and de_finite(span) and de_finite(busy_area):
        var b = busy_area / span
        if de_finite(b):
            has_busy = True
            busy = b

    return LossRun(
        DE_OK, n_jobs, n_retained, blocked, accepted, capacity, events, charge,
        horizon, observed_from, span, has_block, block_frac, has_busy, busy,
    )


# ── section 1 and 2: M/M/1 and M/M/c through the package's own validator ──────


@no_inline
def _mmc_config(
    lam: Float64, mu: Float64, n: Int, cap: Int, reps: Int, mut misses: List[Int]
) -> Int:
    """One `replicate_mm1_flat` configuration: four exact values against four intervals.

    Returns 1 on a HARD failure (a refusal, or an interval that could not be formed). A metric
    whose interval simply does not contain the exact value is counted into `misses` and reported,
    not failed here — see the module docstring on why the miss COUNT is what gets gated.
    """
    var v = replicate_mm1_flat(lam, mu, n, cap, reps, QV_SEED, QV_LEVEL, QV_BATCH)
    if v.status != DE_OK:
        print("  FAIL replicate_mm1_flat refused:", de_status_name(v.status))
        return 1
    if not v.has_wait_ci or not v.has_system_ci or not v.has_number_ci or not v.has_util_ci:
        print("  FAIL an interval could not be formed; there is nothing to compare")
        return 1
    if v.n_reps_run != reps or v.n_reps_refused != 0:
        print("  FAIL", v.n_reps_refused, "replication(s) were refused")
        return 1
    if v.n_metrics_checked != 4:
        print("  FAIL only", v.n_metrics_checked, "of 4 metrics were checked")
        return 1
    print(
        "   lambda", lam, " mu", mu, " c", cap, " rho", v.closed_form_rho,
        " n", n, " reps", v.n_reps_run, " t*", v.t_critical,
        " MSER-5 discarded", v.warmup_jobs_used,
    )
    print("      metric        exact              CI lower           CI upper           covered")
    print(
        "      Wq        ", v.closed_form_wait, v.wait_ci_lower, v.wait_ci_upper,
        v.wait_covered, " err%", _pct(v.wait_mean, v.closed_form_wait),
    )
    print(
        "      W         ", v.closed_form_system, v.system_ci_lower, v.system_ci_upper,
        v.system_covered, " err%", _pct(v.system_mean, v.closed_form_system),
    )
    print(
        "      L         ", v.closed_form_number, v.number_ci_lower, v.number_ci_upper,
        v.number_covered, " err%", _pct(v.number_mean, v.closed_form_number),
    )
    print(
        "      rho       ", v.closed_form_rho, v.util_ci_lower, v.util_ci_upper,
        v.util_covered, " err%", _pct(v.util_mean, v.closed_form_rho),
    )
    misses[0] += 4 - v.n_metrics_covered
    misses[1] += 4
    if v.n_metrics_covered < 4:
        print(
            "      NOTE", 4 - v.n_metrics_covered, "of 4 intervals did not contain the exact",
            "value at this configuration",
        )
    return 0


@no_inline
def _bench_mm1(mut misses: List[Int]) -> Int:
    """Section 1 — M/M/1 at three utilisations. `L = rho/(1-rho)`, `W = 1/(mu-lambda)`."""
    print("[1] M/M/1 — exact steady state against the replication intervals")
    print("    Wq = rho/(mu-lambda)   W = 1/(mu-lambda)   L = rho/(1-rho)   util = rho")
    var f = 0
    f += _mmc_config(0.5, 1.0, 20000, 1, 20, misses)
    f += _mmc_config(0.8, 1.0, 20000, 1, 20, misses)
    f += _mmc_config(0.9, 1.0, 40000, 1, 20, misses)
    if f > 0:
        return f
    print("  PASS all three M/M/1 configurations produced four intervals each from 20 replications")
    return 0


@no_inline
def _bench_mmc(mut misses: List[Int]) -> Int:
    """Section 2 — M/M/c at c = 3 and c = 5, both at rho = 0.8."""
    print("[2] M/M/c — exact Erlang-C steady state against the replication intervals")
    print("    Wq = C(c,A)/(c*mu-lambda)   W = Wq + 1/mu   L = lambda*W")
    var f = 0
    f += _mmc_config(2.4, 1.0, 20000, 3, 20, misses)
    f += _mmc_config(4.0, 1.0, 20000, 5, 20, misses)
    if f > 0:
        return f
    print("  PASS both M/M/c configurations produced four intervals each from 20 replications")
    return 0


# ── section 3: Erlang B, the loss system ──────────────────────────────────────


@no_inline
def _erlang_b_config(
    lam: Float64, mu: Float64, cap: Int, n: Int, reps: Int, mut misses: List[Int]
) -> Int:
    """One M/M/c/c configuration: blocking probability and carried traffic against Erlang B."""
    var traffic = lam / mu
    var b_exact = queueing_erlang_b(traffic, cap)
    var carried_exact = traffic * (1.0 - b_exact)

    var blocking = List[Float64]()
    var busy = List[Float64]()
    var events_seen = 0
    var charge_seen = 0
    for r in range(1, reps + 1):
        var arr = qs_arrival_times(lam, n, QV_SEED, r)
        var svc = qs_service_times(mu, n, QV_SEED, r)
        if len(arr) != n or len(svc) != n:
            print("  FAIL the generator refused a replication's draws")
            return 1
        var run = _loss_serve(arr, svc, n, cap, 0)
        if run.status != DE_OK:
            print("  FAIL loss run refused:", de_status_name(run.status))
            return 1
        if not run.has_blocking or not run.has_busy:
            print("  FAIL a loss run produced no blocking fraction")
            return 1
        # The event count is an exact integer identity: every arrival is one event, and every
        # ACCEPTED arrival adds exactly one departure. A driver that lost or double-counted a
        # rejection would break this before it broke any interval.
        if run.events_processed != n + run.n_accepted:
            print("  FAIL events processed", run.events_processed, "!= n + accepted")
            return 1
        if run.n_accepted + run.n_blocked != n:
            print("  FAIL accepted + blocked != offered")
            return 1
        events_seen = run.events_processed
        charge_seen = run.work_charged
        blocking.append(run.blocking_fraction)
        busy.append(run.mean_busy_servers)

    var ci_b = replicate_ci_flat(blocking, reps, QV_LEVEL)
    var ci_busy = replicate_ci_flat(busy, reps, QV_LEVEL)
    if ci_b.status != DE_OK or not ci_b.has_ci or ci_busy.status != DE_OK or not ci_busy.has_ci:
        print("  FAIL an interval could not be formed for the loss configuration")
        return 1
    var b_cov = _covers(ci_b.ci_lower, ci_b.ci_upper, b_exact)
    var busy_cov = _covers(ci_busy.ci_lower, ci_busy.ci_upper, carried_exact)
    print(
        "   A =", traffic, " c", cap, " n", n, " reps", reps, " t*", ci_b.t_critical,
        " events/rep", events_seen, " charge", charge_seen,
    )
    print(
        "      B(A,c)    ", b_exact, ci_b.ci_lower, ci_b.ci_upper, b_cov,
        " err%", _pct(ci_b.mean, b_exact),
    )
    print(
        "      A(1-B)    ", carried_exact, ci_busy.ci_lower, ci_busy.ci_upper, busy_cov,
        " err%", _pct(ci_busy.mean, carried_exact),
    )
    misses[1] += 2
    if not b_cov:
        misses[0] += 1
        print("      NOTE the blocking interval does not contain the exact Erlang B value")
    if not busy_cov:
        misses[0] += 1
        print("      NOTE the carried-traffic interval does not contain A(1-B)")
    return 0


@no_inline
def _bench_erlang_b(mut misses: List[Int]) -> Int:
    """Section 3 — Erlang B on the M/M/c/c loss system, plus the two-kernel cross-check."""
    print("[3] Erlang B — M/M/c/c loss system (no waiting room), exact recursion")
    print("    B(A,n) = A*B(A,n-1) / (n + A*B(A,n-1))   carried traffic = A*(1-B)")
    # Both frozen kernels, reversed argument order, different recursions. Gated because a caller
    # who reaches for the wrong signature gets a plausible number rather than a type error.
    print("    frozen kernel cross-check (queueing.erlang_b vs telecommunications.erlang_b):")
    var kernels_agree = True
    var a_probe = List[Float64]()
    a_probe.append(0.5)
    a_probe.append(2.0)
    a_probe.append(4.0)
    a_probe.append(10.0)
    var c_probe = List[Int]()
    c_probe.append(1)
    c_probe.append(3)
    c_probe.append(5)
    c_probe.append(12)
    for i in range(len(a_probe)):
        var q = queueing_erlang_b(a_probe[i], c_probe[i])
        var t = telecom_erlang_b(c_probe[i], a_probe[i])
        var gap = fabs(q - t)
        # The judged quantity is the `queueing` value; the tolerance comes from its own magnitude
        # widened by one ulp per step of the recursion that built it, and from nothing else.
        var ok = de_agrees(q, t, 0.0, c_probe[i])
        if not ok:
            kernels_agree = False
        print("      A =", a_probe[i], " c", c_probe[i], " queueing", q, " telecom", t,
              " |gap|", gap, " agree", ok)
    if not kernels_agree:
        print(
            "  FAIL the two frozen Erlang B kernels disagree beyond their recursion's rounding —",
            "one of them is wrong and callers cannot tell which",
        )
        return 1
    print("      metric        exact              CI lower           CI upper           covered")
    var f = 0
    f += _erlang_b_config(0.5, 1.0, 1, 20000, 20, misses)
    f += _erlang_b_config(2.0, 1.0, 3, 20000, 20, misses)
    f += _erlang_b_config(4.0, 1.0, 5, 20000, 20, misses)
    if f > 0:
        return f
    print(
        "  PASS three loss configurations, blocking fraction and carried traffic each against the",
        "exact recursion, and the two frozen kernels agree to their recursion's rounding",
    )
    return 0


# ── section 4: Erlang C, the delay probability ────────────────────────────────


@no_inline
def _erlang_c_config(
    lam: Float64, mu: Float64, cap: Int, n: Int, reps: Int, mut misses: List[Int],
    mut little: List[Int], mut little_gap: List[Float64],
) -> Int:
    """One M/M/c configuration: the measured fraction of delayed arrivals against Erlang C.

    Also harvests each run's OWN Little's law verdict for section 6, because these runs are
    driven at `warmup_jobs = 0` and that is exactly the window over which the identity is exact.
    """
    var c_exact = mmc_erlang_c(lam, mu, cap)
    var pri = _ones(n)
    var delayed = List[Float64]()
    for r in range(1, reps + 1):
        var arr = qs_arrival_times(lam, n, QV_SEED, r)
        var svc = qs_service_times(mu, n, QV_SEED, r)
        if len(arr) != n or len(svc) != n:
            print("  FAIL the generator refused a replication's draws")
            return 1
        var run = resource_serve_flat(arr, svc, pri, n, cap, 0)
        if run.status != DE_OK:
            print("  FAIL resource run refused:", de_status_name(run.status))
            return 1
        var waited = 0
        for i in range(n):
            if run.wait[i] > 0.0:
                waited += 1
        delayed.append(Float64(waited) / Float64(n))
        # Little's law on the run's own output — see section 6.
        little[1] += 1
        if run.has_little_law_check and run.little_law_consistent:
            little[0] += 1
        if run.has_little_law_check and run.little_law_gap > little_gap[0]:
            little_gap[0] = run.little_law_gap
    var ci = replicate_ci_flat(delayed, reps, QV_LEVEL)
    if ci.status != DE_OK or not ci.has_ci:
        print("  FAIL the delay-probability interval could not be formed")
        return 1
    var cov = _covers(ci.ci_lower, ci.ci_upper, c_exact)
    print(
        "   A =", lam / mu, " c", cap, " n", n, " reps", reps, " t*", ci.t_critical,
    )
    print(
        "      C(c,A)    ", c_exact, ci.ci_lower, ci.ci_upper, cov,
        " err%", _pct(ci.mean, c_exact),
    )
    misses[1] += 1
    if not cov:
        misses[0] += 1
        print("      NOTE the delay-probability interval does not contain the exact Erlang C")
    return 0


@no_inline
def _bench_erlang_c(
    mut misses: List[Int], mut little: List[Int], mut little_gap: List[Float64]
) -> Int:
    """Section 4 — Erlang C measured as the fraction of arrivals with a strictly positive wait."""
    print("[4] Erlang C — P(an arrival is delayed) in M/M/c, measured as #(wait > 0) / n")
    print("    By PASTA the arrival average equals the time average P(all c servers busy) = C(c,A)")
    print("      metric        exact              CI lower           CI upper           covered")
    var f = 0
    f += _erlang_c_config(0.5, 1.0, 1, 20000, 20, misses, little, little_gap)
    f += _erlang_c_config(2.4, 1.0, 3, 20000, 20, misses, little, little_gap)
    f += _erlang_c_config(4.0, 1.0, 5, 20000, 20, misses, little, little_gap)
    if f > 0:
        return f
    print("  PASS three M/M/c configurations, delay probability against the exact Erlang C")
    return 0


# ── section 5: the Lindley recursion ──────────────────────────────────────────


@no_inline
def _lindley_config(lam: Float64, mu: Float64, n: Int, rep: Int) -> Int:
    """The waiting-time recursion against the engine's own per-customer waits.

    Absolute-time form gated BIT-EXACT on every customer; the canonical gap form gated against a
    tolerance built from the engine's own wait magnitude, with the largest deviation printed.
    """
    var gaps = qs_interarrivals(lam, n, QV_SEED, rep)
    var arr = qs_arrival_times(lam, n, QV_SEED, rep)
    var svc = qs_service_times(mu, n, QV_SEED, rep)
    if len(gaps) != n or len(arr) != n or len(svc) != n:
        print("  FAIL the generator refused the Lindley draws")
        return 1
    var pri = _ones(n)
    var run = resource_serve_flat(arr, svc, pri, n, 1, 0)
    if run.status != DE_OK:
        print("  FAIL the capacity-1 run refused:", de_status_name(run.status))
        return 1

    # Canonical gap form: W_1 = 0, W_{i+1} = max(0, W_i + S_i - A_{i+1}).
    var w_gap = List[Float64]()
    w_gap.append(0.0)
    for i in range(1, n):
        var v = w_gap[i - 1] + svc[i - 1] - gaps[i]
        w_gap.append(v if v > 0.0 else 0.0)

    # Absolute-time form: D_i = max(A_i, D_{i-1}) + S_i, W_i = max(0, D_{i-1} - A_i). This
    # performs exactly the additions the engine performs, so it must agree BIT FOR BIT.
    var w_abs = List[Float64]()
    var d_prev: Float64 = 0.0
    for i in range(n):
        var w: Float64 = 0.0
        var st = arr[i]
        if i > 0 and d_prev > arr[i]:
            w = d_prev - arr[i]
            st = d_prev
        w_abs.append(w)
        d_prev = st + svc[i]

    var bit_exact_abs = 0
    var bit_exact_gap = 0
    var max_gap_err: Float64 = 0.0
    var gap_within_tol = 0
    for i in range(n):
        if w_abs[i] == run.wait[i]:
            bit_exact_abs += 1
        if w_gap[i] == run.wait[i]:
            bit_exact_gap += 1
        var e = fabs(w_gap[i] - run.wait[i])
        if e > max_gap_err:
            max_gap_err = e
        # The magnitude that sets this difference is the CLOCK, not the wait — the engine forms
        # every wait as a difference of two instants of magnitude up to `horizon`, so a short wait
        # late in a long run has an absolute rounding floor of `eps * horizon`. `i + 1` names the
        # additions that built the instant. See the module docstring: this is the derived error
        # model for this one comparison, and getting it wrong was this file's first failure.
        if de_agrees(run.wait[i], w_gap[i], de_scaled_tol_additions(run.horizon, 0.0, i + 1), 0):
            gap_within_tol += 1
    # The same bound expressed as a count of clock ulps, which is the interpretable form: a
    # genuine disagreement between the two recursions is of order one wait unit, roughly 1e12
    # clock ulps, so this number separates rounding from a defect by twelve orders of magnitude.
    var clock_ulp: Float64 = 0.0
    if run.horizon > 0.0:
        clock_ulp = max_gap_err / (2.220446049250313e-16 * run.horizon)
    print(
        "   lambda", lam, " mu", mu, " rho", lam / mu, " n", n, " rep", rep,
        " horizon", run.horizon,
        " | absolute-time bit-exact", bit_exact_abs, "/", n,
        " | gap-form bit-exact", bit_exact_gap, "/", n,
        " within tol", gap_within_tol, "/", n, " max dev", max_gap_err,
        " =", clock_ulp, "clock ulps",
    )
    if bit_exact_abs != n:
        print(
            "  FAIL the absolute-time Lindley recursion does not reproduce the engine's waits",
            "bit for bit — the engine is not computing the waiting-time recursion",
        )
        return 1
    if gap_within_tol != n:
        print(
            "  FAIL the canonical gap-form Lindley recursion disagrees with the engine beyond",
            "the clock's own rounding floor",
        )
        return 1
    if not de_finite(clock_ulp) or clock_ulp > 256.0:
        print(
            "  FAIL the largest gap-form deviation is", clock_ulp, "ulps of the clock, outside the",
            "tree's 256-ulp base budget — that is a disagreement, not summation order",
        )
        return 1
    return 0


@no_inline
def _bench_lindley() -> Int:
    """Section 5 — the exact waiting-time recursion, per customer, including where rho >= 1."""
    print("[5] Lindley recursion — W_{n+1} = max(0, W_n + S_n - A_{n+1}), PER CUSTOMER")
    print("    Not statistical: a pathwise identity, so it holds at rho >= 1 where no steady")
    print("    state exists. Absolute-time form is gated BIT-EXACT on every customer.")
    var f = 0
    f += _lindley_config(0.5, 1.0, 5000, 1)
    f += _lindley_config(0.8, 1.0, 5000, 1)
    f += _lindley_config(0.95, 1.0, 5000, 2)
    f += _lindley_config(1.05, 1.0, 5000, 3)
    if f > 0:
        return f
    print(
        "  PASS every customer's waiting time equals the absolute-time Lindley recursion BIT FOR",
        "BIT at all four utilisations, including the unstable one, and the canonical gap form",
    )
    print("       agrees to within the clock's own rounding floor at every customer")
    return 0


# ── section 6: Little's law on the simulator's own output ──────────────────────


@no_inline
def _bench_little(little: List[Int], little_gap: List[Float64]) -> Int:
    """Section 6 — `L = lambda * W` on the simulated numbers, with no theory involved.

    Harvested from every run section 4 drove (all at `warmup_jobs = 0`, which is the only window
    over which the identity is exact — a truncated window has jobs contributing area with no
    sojourn term inside it, which is why `resource_serve_flat` reports the check as UNAVAILABLE
    there rather than answering it True).
    """
    print("[6] Little's law on the simulated output — internal consistency, not theory")
    print(
        "    L = lambda * W is EXACT over a complete window: the time integral of the number in",
    )
    print("    system equals the sum of sojourn times term for term, so only rounding separates them.")
    print("    runs checked", little[1], " consistent", little[0], " largest |gap|", little_gap[0])
    if little[1] == 0:
        print("  FAIL no run reported a Little's law verdict")
        return 1
    if little[0] != little[1]:
        print(
            "  FAIL", little[1] - little[0], "run(s) failed their own Little's law identity —",
            "the engine's area accounting and its sojourn accounting disagree",
        )
        return 1
    print(
        "  PASS all", little[1], "runs satisfied L = lambda * W exactly, to a tolerance of one",
        "ulp per addition that built either side and nothing more",
    )
    return 0


# ── section 7: the warm-up question, in both directions ───────────────────────


@no_inline
def _warmup_pair(lam: Float64, mu: Float64, n: Int, reps: Int) -> Int:
    """The SAME replications estimated twice: retaining everything, and discarding the transient.

    The truncated arm is `replicate_mm1_flat` itself — the shipped driver, with the truncation
    its MSER-5 pilot chose. The un-truncated arm re-drives `resource_serve_flat` on the identical
    coordinates (`replication_id = 1 .. reps`, same seed), so the two arms differ in the
    truncation and in nothing else. That pairing is what makes the comparison a statement about
    the truncation rather than about two samples.
    """
    var cf = qs_closed_form_flat(lam, mu, 1)
    if cf.status != DE_OK or not cf.exists:
        print("  FAIL no closed form at these rates")
        return 1
    var exact = cf.wait_in_queue

    var pri = _ones(n)
    var full = List[Float64]()
    for r in range(1, reps + 1):
        var arr = qs_arrival_times(lam, n, QV_SEED, r)
        var svc = qs_service_times(mu, n, QV_SEED, r)
        var run = resource_serve_flat(arr, svc, pri, n, 1, 0)
        if run.status != DE_OK or not run.has_mean_wait:
            print("  FAIL a no-discard replication refused")
            return 1
        full.append(run.mean_wait)
    var ci_full = replicate_ci_flat(full, reps, QV_LEVEL)
    if ci_full.status != DE_OK or not ci_full.has_ci:
        print("  FAIL the no-discard interval could not be formed")
        return 1

    var v = replicate_mm1_flat(lam, mu, n, 1, reps, QV_SEED, QV_LEVEL, QV_BATCH)
    if v.status != DE_OK or not v.has_wait_ci:
        print("  FAIL the truncated arm refused:", de_status_name(v.status))
        return 1

    var full_cov = _covers(ci_full.ci_lower, ci_full.ci_upper, exact)
    print(
        "   rho", lam / mu, " n", n, " reps", reps, " exact Wq", exact,
        " MSER-5 discarded", v.warmup_jobs_used, "of", n,
    )
    print(
        "      NO DISCARD   mean", ci_full.mean, " CI [", ci_full.ci_lower, ",",
        ci_full.ci_upper, "] covers", full_cov, " bias", ci_full.mean - exact,
        " |bias|/half-width", fabs(ci_full.mean - exact) / ci_full.half_width,
    )
    print(
        "      TRUNCATED    mean", v.wait_mean, " CI [", v.wait_ci_lower, ",",
        v.wait_ci_upper, "] covers", v.wait_covered, " bias", v.wait_mean - exact,
    )
    if v.warmup_jobs_used <= 0:
        print(
            "  FAIL MSER-5 discarded nothing at this configuration, so the two arms are the same",
            "run and the comparison is vacuous",
        )
        return 1
    if full_cov:
        print(
            "  FAIL the UN-TRUNCATED estimator covered the exact value here. Either the",
            "initialisation transient stopped biasing the estimate or the estimate stopped being",
            "computed — this section exists to show the bias is real and detectable.",
        )
        return 1
    if not v.wait_covered:
        print(
            "  FAIL discarding the MSER-5 transient did NOT bring the interval onto the exact",
            "value; the truncation is not doing the job it is charged for",
        )
        return 1
    if fabs(v.wait_mean - exact) >= fabs(ci_full.mean - exact):
        print("  FAIL truncation did not reduce the bias")
        return 1
    return 0


@no_inline
def _warmup_sweep(lam: Float64, mu: Float64, reps: Int, mut zero_d: List[Int]) -> Int:
    """The bias-versus-run-length table, and where MSER-5 stops truncating.

    Reported rather than gated: this is the FINDING in this file, and the numbers are what make
    it a finding instead of an assertion. `zero_d` counts run lengths at which MSER-5 discarded
    nothing while the un-truncated interval still excluded the exact value.
    """
    var cf = qs_closed_form_flat(lam, mu, 1)
    var exact = cf.wait_in_queue
    var sizes = List[Int]()
    sizes.append(100)
    sizes.append(150)
    sizes.append(200)
    sizes.append(400)
    sizes.append(1000)
    sizes.append(4000)
    print("      n      MSER-5 d   no-discard mean       bias        |bias|/hw   covers")
    for s in range(len(sizes)):
        var n = sizes[s]
        var pri = _ones(n)
        var pa = qs_arrival_times(lam, n, QV_SEED, 0)
        var ps = qs_service_times(mu, n, QV_SEED, 0)
        var pilot = resource_serve_flat(pa, ps, pri, n, 1, 0)
        if pilot.status != DE_OK:
            print("  FAIL the pilot refused at n =", n)
            return 1
        var mser = warmup_mser_flat(pilot.wait, n, QV_BATCH)
        var full = List[Float64]()
        for r in range(1, reps + 1):
            var arr = qs_arrival_times(lam, n, QV_SEED, r)
            var svc = qs_service_times(mu, n, QV_SEED, r)
            var run = resource_serve_flat(arr, svc, pri, n, 1, 0)
            if run.status != DE_OK or not run.has_mean_wait:
                print("  FAIL a sweep replication refused at n =", n)
                return 1
            full.append(run.mean_wait)
        var ci = replicate_ci_flat(full, reps, QV_LEVEL)
        if ci.status != DE_OK or not ci.has_ci:
            print("  FAIL a sweep interval could not be formed at n =", n)
            return 1
        var cov = _covers(ci.ci_lower, ci.ci_upper, exact)
        print(
            "     ", n, "    ", mser.n_discarded_obs, "   ", ci.mean, "  ",
            ci.mean - exact, "  ", fabs(ci.mean - exact) / ci.half_width, "  ", cov,
        )
        if mser.n_discarded_obs == 0 and not cov:
            zero_d[0] += 1
    return 0


@no_inline
def _bench_warmup(mut findings: List[Int]) -> Int:
    """Section 7 — does warm-up detection earn its place?"""
    print("[7] Warm-up: the same replications, estimated with and without the transient")
    print("    A simulation starts empty, so the first customers wait less than steady-state ones")
    print("    and the untruncated mean is biased LOW. That bias is shown, not assumed.")
    var f = 0
    f += _warmup_pair(0.8, 1.0, 100, 200)
    f += _warmup_pair(0.5, 1.0, 100, 400)
    if f > 0:
        return f
    print("")
    print("    Bias against run length at rho = 0.8, 200 replications, exact Wq = 4:")
    var zero_d = List[Int]()
    zero_d.append(0)
    var sweep_fail = _warmup_sweep(0.8, 1.0, 200, zero_d)
    if sweep_fail > 0:
        return sweep_fail
    findings[0] = zero_d[0]
    if zero_d[0] > 0:
        print(
            "    FINDING at", zero_d[0], "run length(s) MSER-5 discarded NOTHING while the",
            "un-truncated interval still excluded the exact value.",
        )
        print(
            "            MSER's score is the estimated standard error of the retained mean, which",
            "grows like 1/(m-d), so truncation only wins when the transient's share of the",
        )
        print(
            "            batch-mean spread beats the variance cost of a shorter sample. On a long",
            "noisy series d = 0 wins with bias still present. This is a warm-up DETECTOR",
        )
        print(
            "            limitation, not a mechanics defect — sections 5 and 6 prove the mechanics",
            "exactly — and it is reported, not gated.",
        )
    print(
        "  PASS the un-truncated estimator is biased away from the exact value at both short-run",
        "configurations, its interval EXCLUDES the exact value, and discarding the MSER-5",
    )
    print("       transient brings the interval back onto it with a strictly smaller bias")
    return 0


# ── section 8: the interval machinery itself ──────────────────────────────────


@no_inline
def _bench_t_quantile() -> Int:
    """Section 8 — the Student-t quantile against published two-sided 95% table values.

    Every interval in this file is `mean +/- t * se`, so a wrong `t` would make all 29 coverage
    verdicts meaningless in the same direction — too narrow and everything misses, too wide and
    everything covers. `scipy` is not importable in this environment, so the reference is the
    published table rather than another implementation, checked to the four decimal places the
    table publishes. That is a golden-vector check, not a dependency.
    """
    print("[8] The interval machinery: inference_t_quantile(0.975, df) vs published t tables")
    print("      df      computed              published    |gap|")
    var dfs = List[Float64]()
    var tab = List[Float64]()
    dfs.append(1.0); tab.append(12.7062)
    dfs.append(2.0); tab.append(4.3027)
    dfs.append(4.0); tab.append(2.7764)
    dfs.append(9.0); tab.append(2.2622)
    dfs.append(19.0); tab.append(2.0930)
    dfs.append(29.0); tab.append(2.0452)
    dfs.append(60.0); tab.append(2.0003)
    dfs.append(120.0); tab.append(1.9799)
    dfs.append(199.0); tab.append(1.9720)
    dfs.append(399.0); tab.append(1.9659)
    var worst: Float64 = 0.0
    var ok = True
    for i in range(len(dfs)):
        var got = inference_t_quantile(0.975, dfs[i])
        var gap = fabs(got - tab[i])
        if gap > worst:
            worst = gap
        # The table publishes four decimals, so half a unit in the last published place is the
        # strongest claim the reference supports. Not a tuned tolerance: it is the reference's
        # own precision.
        if not de_finite(got) or gap > 5.0e-5:
            ok = False
        print("     ", dfs[i], " ", got, " ", tab[i], " ", gap)
    print("      largest |gap| across ten degrees of freedom =", worst)
    if not ok:
        print(
            "  FAIL the t quantile disagrees with the published table beyond its published",
            "precision — every interval in this file is the wrong width",
        )
        return 1
    print(
        "  PASS the t quantile matches published two-sided 95% table values at all ten degrees",
        "of freedom, to the four decimals the table publishes",
    )
    return 0


# ── section 9: the negative controls ──────────────────────────────────────────


@no_inline
def _bench_negative_controls() -> Int:
    """Section 9 — six deliberately wrong inputs that the gates above MUST reject.

    A gate that cannot fail is not a gate. Every check in this file is exercised here against an
    input constructed to be wrong, and a control that does NOT trip is itself a hard failure —
    it means the corresponding gate is vacuous and has been passing for free.
    """
    print("[9] Negative controls — each gate is shown to reject a deliberately wrong input")
    var failures = 0

    # (1) The coverage test must reject a value outside the interval. Uses a REAL interval from a
    # real run, not a hand-written one, so it tests the comparison actually used above.
    var v = replicate_mm1_flat(0.8, 1.0, 20000, 1, 20, QV_SEED, QV_LEVEL, QV_BATCH)
    if v.status != DE_OK or not v.has_wait_ci:
        print("  FAIL the control run refused")
        return 1
    var true_cov = _covers(v.wait_ci_lower, v.wait_ci_upper, v.closed_form_wait)
    var wrong_cov = _covers(v.wait_ci_lower, v.wait_ci_upper, v.closed_form_wait * 1.25)
    print("      (1) coverage test: exact value inside =", true_cov,
          " | exact*1.25 inside =", wrong_cov)
    if wrong_cov or not true_cov:
        print("  FAIL control 1: the coverage test does not discriminate")
        failures += 1

    # (2) The interval must be TIGHT enough to reject a nearby-but-wrong model. Erlang B at the
    # wrong server count is the model error a loss-system study would actually make.
    var blocking = List[Float64]()
    for r in range(1, 21):
        var a2 = qs_arrival_times(2.0, 20000, QV_SEED, r)
        var s2 = qs_service_times(1.0, 20000, QV_SEED, r)
        var lr = _loss_serve(a2, s2, 20000, 3, 0)
        if lr.status != DE_OK or not lr.has_blocking:
            print("  FAIL control 2 run refused")
            return 1
        blocking.append(lr.blocking_fraction)
    var ci_b = replicate_ci_flat(blocking, 20, QV_LEVEL)
    var right = _covers(ci_b.ci_lower, ci_b.ci_upper, queueing_erlang_b(2.0, 3))
    var wrong_c = _covers(ci_b.ci_lower, ci_b.ci_upper, queueing_erlang_b(2.0, 4))
    print("      (2) Erlang B at c=3 inside =", right, " | Erlang B at c=4 inside =", wrong_c,
          " (B(2,3) =", queueing_erlang_b(2.0, 3), " B(2,4) =", queueing_erlang_b(2.0, 4), ")")
    if wrong_c or not right:
        print("  FAIL control 2: the blocking interval cannot tell c=3 from c=4")
        failures += 1

    # (3) A BROKEN Lindley recursion — the max(0, .) clamp removed, so waits go negative — must
    # NOT match the engine. If it does, the bit-exactness gate is comparing nothing.
    var n = 2000
    var gaps = qs_interarrivals(0.8, n, QV_SEED, 1)
    var la = qs_arrival_times(0.8, n, QV_SEED, 1)
    var ls = qs_service_times(1.0, n, QV_SEED, 1)
    var run = resource_serve_flat(la, ls, _ones(n), n, 1, 0)
    if run.status != DE_OK:
        print("  FAIL control 3 run refused")
        return 1
    var broken = List[Float64]()
    broken.append(0.0)
    for i in range(1, n):
        broken.append(broken[i - 1] + ls[i - 1] - gaps[i])
    var broken_matches = 0
    for i in range(n):
        if broken[i] == run.wait[i]:
            broken_matches += 1
    print("      (3) unclamped Lindley matches engine on", broken_matches, "/", n, "customers")
    if broken_matches == n:
        print("  FAIL control 3: an unclamped recursion matched the engine everywhere")
        failures += 1

    # (4) The other Lindley failure mode: ignore the predecessor's departure entirely, so every
    # wait is zero. A capacity-1 queue at rho = 0.8 has customers that wait, so this must differ.
    var zero_wait = 0
    for i in range(n):
        if run.wait[i] == 0.0:
            zero_wait += 1
    print("      (4) all-zero waits would match on", zero_wait, "/", n,
          "customers (", n - zero_wait, "genuinely waited)")
    if zero_wait == n:
        print("  FAIL control 4: no customer waited, so the recursion is untested")
        failures += 1

    # (5) Little's law's tolerance must not be vacuous. The gate allows one ulp per addition;
    # a relative perturbation of 1e-9 is four orders of magnitude above that and must be caught.
    var l_hat: Float64 = 0.0
    if run.has_time_avg_number:
        l_hat = run.time_avg_number
    var tol_rejects = not de_agrees(l_hat * (1.0 + 1.0e-9), l_hat, 0.0, 3 * n)
    var tol_accepts = de_agrees(l_hat, l_hat, 0.0, 3 * n)
    print("      (5) Little's law tolerance: rejects a 1e-9 relative perturbation =", tol_rejects,
          " | accepts the exact value =", tol_accepts)
    if not tol_rejects or not tol_accepts:
        print("  FAIL control 5: the Little's law tolerance is vacuous or self-rejecting")
        failures += 1

    # (6) The t-quantile check must reject a wrong critical value. 1.96 is the NORMAL quantile —
    # the specific mistake this file's intervals would make if the t were dropped — and at 19
    # degrees of freedom it is 6.4% too narrow.
    var t19 = inference_t_quantile(0.975, 19.0)
    var normal_gap = fabs(t19 - 1.9600)
    print("      (6) t(0.975, 19) =", t19, " vs the normal 1.96: |gap| =", normal_gap,
          " rejected =", normal_gap > 5.0e-5)
    if normal_gap <= 5.0e-5:
        print("  FAIL control 6: the table check cannot tell a t quantile from a normal one")
        failures += 1

    if failures > 0:
        return failures
    print(
        "  PASS all six negative controls tripped — every gate above rejects a deliberately",
        "wrong input, so none of them is passing for free",
    )
    return 0


def main() raises:
    var t0 = perf_counter_ns()
    print("\n=== bench_queueing_validation: the simulator against closed-form queueing theory ===")
    print("Seed", QV_SEED, " level", QV_LEVEL, " MSER batch", QV_BATCH,
          " event order", "time,priority,sequence/v1")
    print("Machine: Apple M4 Max, 16 cores (12 performance + 4 efficiency), 128 GB, macOS 26.5.2.")
    print("NO GATE IN THIS FILE IS A WALL-CLOCK NUMBER, so the verdict is load-independent; the")
    print("runner should still record the load average beside this log, because it decides how")
    print("long the run takes. Every input is seeded or closed-form: a re-run reproduces the log.")
    print("")

    var failures = 0
    # misses[0] = intervals that did not contain their exact value; misses[1] = intervals formed.
    var misses = List[Int]()
    misses.append(0)
    misses.append(0)
    var little = List[Int]()
    little.append(0)
    little.append(0)
    var little_gap = List[Float64]()
    little_gap.append(0.0)
    var findings = List[Int]()
    findings.append(0)

    failures += _bench_mm1(misses)
    print("")
    failures += _bench_mmc(misses)
    print("")
    failures += _bench_erlang_b(misses)
    print("")
    failures += _bench_erlang_c(misses, little, little_gap)
    print("")
    failures += _bench_lindley()
    print("")
    failures += _bench_little(little, little_gap)
    print("")
    failures += _bench_warmup(findings)
    print("")
    failures += _bench_t_quantile()
    print("")
    failures += _bench_negative_controls()
    print("")

    print("[C] Coverage summary across every closed-form reference")
    print(
        "    intervals formed", misses[1], " intervals containing their exact value",
        misses[1] - misses[0], " misses", misses[0], " threshold", QV_MAX_MISSES,
    )
    print(
        "    A 95% interval misses one time in twenty BY CONSTRUCTION, so the miss count is what",
        "is gated, not each verdict. P(6 or more misses of 29) = 0.0028 under independence.",
    )
    if misses[0] >= QV_MAX_MISSES:
        print(
            "  FAIL", misses[0], "of", misses[1], "intervals did not contain their exact value.",
            "That is more than statistics explains: THE SIMULATOR DISAGREES WITH THE ALGEBRA and",
        )
        print(
            "       the algebra is not the thing that is wrong. Do not widen an interval to make",
            "this pass — the interval is what the replications produced.",
        )
        failures += 1
    else:
        print("  PASS the miss count is inside what a 95% level explains")
    print("")

    if findings[0] > 0:
        print(
            "NOTE 1 reported FINDING (not a gate failure): MSER-5 selects a zero truncation at",
            findings[0], "run length(s) where the un-truncated estimate is still measurably",
        )
        print(
            "     biased. Section 7 has the table. The simulator's MECHANICS are proved exactly by",
            "the bit-exact Lindley identity and Little's law; this is an estimator limitation.",
        )
    var elapsed = Float64(Int(perf_counter_ns() - t0)) / 1.0e9
    print("Elapsed", elapsed, "s (informational only — nothing here is timed or gated on time)")
    if failures == 0:
        print("BENCH_GATE queueing_validation PASS")
    else:
        print("BENCH_GATE queueing_validation FAIL " + String(failures))
        # The exit code is the only signal a caller can act on: nothing greps for BENCH_GATE.
        raise Error("bench_queueing_validation: " + String(failures) + " gate failure(s)")
