"""test_discrete_event_queue_sim.mojo — known-value tests for the seeded queue runs.

Hand-written. The closed forms are exact rationals derived from the textbook M/M/1 and M/M/c
formulas; the draws are asserted against the FROZEN generator directly, so nothing here is this
module agreeing with itself.

The closed forms, by hand
-------------------------
M/M/1 with lambda = 1, mu = 2:  rho = 1/2
    Wq = rho/(mu-lambda) = 0.5/1 = 0.5
    W  = 1/(mu-lambda)   = 1.0
    L  = rho/(1-rho)     = 1.0
    Lq = rho^2/(1-rho)   = 0.5

M/M/2 with lambda = 3, mu = 2:  A = lambda/mu = 1.5, rho = A/c = 0.75
    Erlang C = [A^2/2! * c/(c-A)] / [1 + A + A^2/2! * c/(c-A)]
             = [1.125 * 4] / [1 + 1.5 + 4.5] = 4.5/7 = 9/14
    Wq = C/(c*mu - lambda) = (9/14)/1 = 9/14
    W  = Wq + 1/mu = 9/14 + 7/14 = 16/14 = 8/7
    L  = lambda * W = 24/7
All five M/M/1 values are asserted as exact equalities; the M/M/2 values against the rationals
9/14, 8/7 and 24/7.

The frozen sentinel this driver exists to wrap
----------------------------------------------
`queueing.mm1_avg_system_time(2.0, 2.0)` returns `1e18` — a finite, serialisable number that
means "there is no answer". The suite asserts that the frozen kernel really does that AND that
`qs_closed_form_flat` reports `exists = False` with `0.0` in the value slots instead. If the
frozen behaviour ever changed, the first assertion fails and this wrapper's reason for existing
is re-examined rather than silently obsolete.

The draws come from the frozen generator, at the coordinates claimed
-------------------------------------------------------------------
`qs_interarrivals(2.0, 3, 7, 0)[i]` is asserted EQUAL, bit for bit, to
`rng_exponential(7, 0, 0, i, 0, de_stream_arrival(), 0, 2.0)`. That is what proves the
coordinates are what the docstring says: index as `dim0`, the named stream as `stream_id`, one
draw per customer. A test that only checked the mean would pass with the coordinates permuted.

Common random numbers, the property that makes a comparison valid
----------------------------------------------------------------
Two runs differing ONLY in arrival rate must report the same `total_service_time` to the last
bit, and two differing only in service rate the same `total_interarrival_time`. Both are
asserted with `==`, not a tolerance. The frozen `simulation.mm1_simulate` cannot satisfy either:
it advances one LCG alternately between the two sources, so changing one rate shifts every draw
of the other.

Also asserted: `Exponential(rate)` is `Exponential(1)/rate` exactly under inverse-CDF sampling,
because `-log(u)/rate` is the same `u` scaled. That pins the sampler to inverse transform rather
than to a rejection method whose draw consumption would depend on the trajectory.
"""
from determinism.counter_rng import rng_exponential
from queueing import mm1_avg_system_time

from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_RATE_RANGE,
    DE_ERR_SEED_RANGE,
    DE_MAX_JOBS,
    DE_MAX_SERVERS,
    DE_OK,
    de_stream_arrival,
    de_stream_service,
)
from discrete_event.queue_sim import (
    qs_arrival_times,
    qs_closed_form_flat,
    qs_interarrivals,
    qs_run_flat,
    qs_service_times,
)


fn main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.queue_sim] known-value suite")

    # ── the exact M/M/1 steady state ──────────────────────────────────────────
    var cf = qs_closed_form_flat(1.0, 2.0, 1)
    var ok_cf = cf.status == DE_OK and cf.exists and cf.capacity == 1
    ok_cf = ok_cf and cf.rho == 0.5
    ok_cf = ok_cf and cf.wait_in_queue == 0.5
    ok_cf = ok_cf and cf.time_in_system == 1.0
    ok_cf = ok_cf and cf.number_in_system == 1.0
    ok_cf = ok_cf and cf.number_in_queue == 0.5
    ok_cf = ok_cf and cf.has_prob_wait and cf.prob_wait == 0.5
    if ok_cf:
        passed += 1
        print("  ✅ M/M/1 (1,2): rho 0.5, Wq 0.5, W 1.0, L 1.0, Lq 0.5 — all exact")
    else:
        failed += 1
        print(
            "  ❌ M/M/1 closed form wrong:", cf.rho, cf.wait_in_queue, cf.time_in_system,
            cf.number_in_system, cf.number_in_queue,
        )

    # ── the exact M/M/2 steady state ──────────────────────────────────────────
    var cfc = qs_closed_form_flat(3.0, 2.0, 2)
    var ok_c = cfc.status == DE_OK and cfc.exists and cfc.rho == 0.75
    ok_c = ok_c and cfc.wait_in_queue == 9.0 / 14.0
    ok_c = ok_c and cfc.time_in_system == 8.0 / 7.0
    ok_c = ok_c and cfc.number_in_system == 24.0 / 7.0
    ok_c = ok_c and cfc.has_prob_wait and cfc.prob_wait == 9.0 / 14.0
    if ok_c:
        passed += 1
        print("  ✅ M/M/2 (3,2): rho 0.75, Erlang C = 9/14, Wq = 9/14, W = 8/7, L = 24/7")
    else:
        failed += 1
        print(
            "  ❌ M/M/2 closed form wrong:", cfc.rho, cfc.wait_in_queue, cfc.time_in_system,
            cfc.number_in_system, cfc.prob_wait,
        )

    # ── the frozen sentinel, demonstrated then replaced by an absence ─────────
    if mm1_avg_system_time(2.0, 2.0) == 1e18:
        passed += 1
        print("  ✅ demonstrated: the frozen queueing kernel answers 1e18 for an unstable queue")
    else:
        failed += 1
        print("  ❌ the frozen sentinel changed:", mm1_avg_system_time(2.0, 2.0))

    var cfu = qs_closed_form_flat(2.0, 2.0, 1)
    var ok_u = cfu.status == DE_OK and not cfu.exists and cfu.rho == 1.0
    ok_u = ok_u and cfu.wait_in_queue == 0.0 and cfu.time_in_system == 0.0
    ok_u = ok_u and cfu.number_in_system == 0.0 and not cfu.has_prob_wait
    if ok_u:
        passed += 1
        print("  ✅ rho = 1 reports exists=False with representable zeros, never the 1e18")
    else:
        failed += 1
        print("  ❌ unstable closed form leaked a value:", cfu.exists, cfu.time_in_system)

    # ── the draws, against the frozen generator at the claimed coordinates ────
    var gaps = qs_interarrivals(2.0, 3, 7, 0)
    var svc = qs_service_times(5.0, 3, 7, 0)
    var arr_stream = UInt64(de_stream_arrival())
    var svc_stream = UInt64(de_stream_service())
    var coords_ok = len(gaps) == 3 and len(svc) == 3
    for i in range(3):
        var expect_gap = rng_exponential(
            UInt64(7), 0, 0, UInt64(i), 0, arr_stream, 0, 2.0
        )
        var expect_svc = rng_exponential(
            UInt64(7), 0, 0, UInt64(i), 0, svc_stream, 0, 5.0
        )
        if gaps[i] != expect_gap or svc[i] != expect_svc:
            coords_ok = False
    if coords_ok:
        passed += 1
        print(
            "  ✅ every draw equals the FROZEN rng_exponential at (seed, replication, index,",
            "named stream) — bit for bit",
        )
    else:
        failed += 1
        print("  ❌ the draw coordinates are not the declared ones")

    # Inverse-CDF scaling: -log(u)/rate, so rate 2 halves rate 1 exactly.
    var unit = qs_interarrivals(1.0, 4, 11, 3)
    var half = qs_interarrivals(2.0, 4, 11, 3)
    var scale_ok = len(unit) == 4 and len(half) == 4
    for i in range(4):
        if half[i] * 2.0 != unit[i]:
            scale_ok = False
    if scale_ok:
        passed += 1
        print("  ✅ inverse-transform sampling: rate 2 is exactly rate 1 halved, same u")
    else:
        failed += 1
        print("  ❌ the sampler is not inverse-CDF on a shared uniform")

    # Arrival instants are the running sum, non-decreasing.
    var instants = qs_arrival_times(2.0, 3, 7, 0)
    var sum_ok = len(instants) == 3
    sum_ok = sum_ok and instants[0] == gaps[0]
    sum_ok = sum_ok and instants[1] == gaps[0] + gaps[1]
    sum_ok = sum_ok and instants[2] == gaps[0] + gaps[1] + gaps[2]
    if sum_ok:
        passed += 1
        print("  ✅ arrival instants are the running sum of the gaps, in order")
    else:
        failed += 1
        print("  ❌ arrival instants are not the gap prefix sums")

    # Different replication and different seed must both move the draws.
    var rep1 = qs_interarrivals(2.0, 3, 7, 1)
    var seed8 = qs_interarrivals(2.0, 3, 8, 0)
    if len(rep1) == 3 and len(seed8) == 3 and rep1[0] != gaps[0] and seed8[0] != gaps[0]:
        passed += 1
        print("  ✅ a different replication and a different seed each change the draws")
    else:
        failed += 1
        print("  ❌ replication or seed is not reaching the generator")

    # ── common random numbers ─────────────────────────────────────────────────
    var base = qs_run_flat(1.0, 2.0, 2000, 1, 7, 0, 0)
    var other_arrival = qs_run_flat(1.5, 2.0, 2000, 1, 7, 0, 0)
    var other_service = qs_run_flat(1.0, 3.0, 2000, 1, 7, 0, 0)
    var crn_ok = base.status == DE_OK and other_arrival.status == DE_OK
    crn_ok = crn_ok and other_service.status == DE_OK
    crn_ok = crn_ok and base.total_service_time == other_arrival.total_service_time
    crn_ok = crn_ok and base.total_interarrival_time == other_service.total_interarrival_time
    # ...and the streams really are different, so the two totals are not the same number.
    crn_ok = crn_ok and base.total_service_time != base.total_interarrival_time
    crn_ok = crn_ok and base.total_service_time != other_service.total_service_time
    if crn_ok:
        passed += 1
        print(
            "  ✅ changing the arrival rate leaves every service draw untouched, and vice versa",
            "— asserted with == on the totals",
        )
    else:
        failed += 1
        print(
            "  ❌ the two random sources are coupled:", base.total_service_time,
            other_arrival.total_service_time, base.total_interarrival_time,
            other_service.total_interarrival_time,
        )

    # ── determinism ───────────────────────────────────────────────────────────
    var repeat = qs_run_flat(1.0, 2.0, 2000, 1, 7, 0, 0)
    var det_ok = repeat.mean_wait == base.mean_wait
    det_ok = det_ok and repeat.mean_system == base.mean_system
    det_ok = det_ok and repeat.time_avg_number == base.time_avg_number
    det_ok = det_ok and repeat.utilization == base.utilization
    det_ok = det_ok and repeat.horizon == base.horizon
    det_ok = det_ok and repeat.total_service_time == base.total_service_time
    det_ok = det_ok and repeat.events_processed == base.events_processed
    if det_ok:
        passed += 1
        print("  ✅ the same seed reproduces every reported number bit-for-bit")
    else:
        failed += 1
        print("  ❌ two identical runs disagreed")

    # ── the run carries the closed form and stays internally consistent ───────
    var run_ok = base.n_customers == 2000 and base.capacity == 1
    run_ok = run_ok and base.events_processed == 4000
    run_ok = run_ok and base.has_closed_form
    run_ok = run_ok and base.closed_form_rho == 0.5 and base.closed_form_wait == 0.5
    run_ok = run_ok and base.closed_form_system == 1.0 and base.closed_form_number == 1.0
    run_ok = run_ok and base.has_little_law_check and base.little_law_consistent
    run_ok = run_ok and base.has_mean_wait and base.has_mean_system
    run_ok = run_ok and base.mean_system > base.mean_wait
    run_ok = run_ok and base.has_utilization and base.utilization > 0.0
    run_ok = run_ok and base.utilization < 1.0
    if run_ok:
        passed += 1
        print(
            "  ✅ 2000 customers = exactly 4000 events; the run carries the exact answer and",
            "its own Little's law check holds",
        )
    else:
        failed += 1
        print(
            "  ❌ run internally inconsistent:", base.events_processed, base.has_closed_form,
            base.little_law_consistent, base.mean_wait, base.mean_system, base.utilization,
        )

    # An unstable run is still a run; only the closed form is absent.
    var unstable = qs_run_flat(3.0, 2.0, 500, 1, 7, 0, 0)
    if unstable.status == DE_OK and not unstable.has_closed_form \
            and unstable.closed_form_system == 0.0 and unstable.has_mean_wait \
            and unstable.mean_wait > 0.0:
        passed += 1
        print(
            "  ✅ rho > 1 still simulates and still reports estimates; only the steady state",
            "is absent",
        )
    else:
        failed += 1
        print(
            "  ❌ an unstable run was mishandled:", unstable.status, unstable.has_closed_form,
            unstable.mean_wait,
        )

    # ── refusals ──────────────────────────────────────────────────────────────
    var nan = 0.0 / 0.0
    var gen_refusals = len(qs_interarrivals(0.0, 3, 7, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(-1.0, 3, 7, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(nan, 3, 7, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(1.0, 0, 7, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(1.0, DE_MAX_JOBS + 1, 7, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(1.0, 3, -1, 0)) == 0
    gen_refusals = gen_refusals and len(qs_interarrivals(1.0, 3, 7, -1)) == 0
    gen_refusals = gen_refusals and len(qs_service_times(1.0, 3, -1, 0)) == 0
    gen_refusals = gen_refusals and len(qs_arrival_times(0.0, 3, 7, 0)) == 0
    if gen_refusals:
        passed += 1
        print(
            "  ✅ the generators return an EMPTY list for a zero, negative, NaN or over-ceiling",
            "request and for a negative seed or replication",
        )
    else:
        failed += 1
        print("  ❌ a generator answered a request it should have refused")

    var run_refusals = qs_run_flat(0.0, 2.0, 100, 1, 7, 0, 0).status == DE_ERR_RATE_RANGE
    run_refusals = run_refusals and qs_run_flat(1.0, nan, 100, 1, 7, 0, 0).status == DE_ERR_RATE_RANGE
    run_refusals = run_refusals and qs_run_flat(1.0, 2.0, 0, 1, 7, 0, 0).status == DE_ERR_EMPTY
    run_refusals = run_refusals and qs_run_flat(
        1.0, 2.0, DE_MAX_JOBS + 1, 1, 7, 0, 0
    ).status == DE_ERR_DIMENSION_TOO_LARGE
    run_refusals = run_refusals and qs_run_flat(1.0, 2.0, 100, 1, -1, 0, 0).status == DE_ERR_SEED_RANGE
    run_refusals = run_refusals and qs_run_flat(1.0, 2.0, 100, 0, 7, 0, 0).status == DE_ERR_CAPACITY
    run_refusals = run_refusals and qs_run_flat(
        1.0, 2.0, 100, DE_MAX_SERVERS + 1, 7, 0, 0
    ).status == DE_ERR_CAPACITY
    if run_refusals:
        passed += 1
        print("  ✅ seven run refusals, each carrying the specific defect code")
    else:
        failed += 1
        print("  ❌ a run refusal used the wrong code")

    # A refusal forwarded from the resource engine keeps the engine's code, not a generic one.
    if qs_run_flat(1.0, 2.0, 100, 1, 7, 0, 100).status == 416:
        passed += 1
        print("  ✅ a warm-up range defect is forwarded from the engine as DE_ERR_WARMUP_RANGE")
    else:
        failed += 1
        print("  ❌ an engine refusal was flattened:", qs_run_flat(1.0, 2.0, 100, 1, 7, 0, 100).status)

    print("  [discrete_event.queue_sim] Passed:", passed, "Failed:", failed)
