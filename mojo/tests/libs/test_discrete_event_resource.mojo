"""test_discrete_event_resource.mojo — known-value tests for the capacity pool.

Hand-written. Every schedule below is a D/D/c queue with integer arrivals and durations, traced
by hand on paper, so every number asserted is an exact rational the reader can re-derive.

Case A — D/D/1, arrivals 0,1,2,3, service 2 each, one server
------------------------------------------------------------
    job 0: starts 0, departs 2, waits 0
    job 1: arrives 1, server busy until 2, starts 2, departs 4, waits 1
    job 2: arrives 2, starts 4, departs 6, waits 2
    job 3: arrives 3, starts 6, departs 8, waits 3

    mean wait   = (0+1+2+3)/4 = 1.5
    mean system = (2+3+4+5)/4 = 3.5
    horizon     = 8, window = [0, 8]
    sum sojourn = 14, so L = 14/8 = 1.75 and utilisation = 8/8 = 1.0
    Little's law: lambda = 4/8 = 0.5, 0.5 * 3.5 = 1.75 = L, EXACTLY

    max queue length = 2, and this is the one number that proves the coincident-event rule.
    At t = 2 a departure and an arrival share the instant. Departures fire first, so job 0
    leaves, job 1 (which had been waiting since t = 1) starts, and only then does job 2 arrive
    to an empty queue. The queue reaches 2 at t = 3, when jobs 2 and 3 are both waiting. Had
    the arrival fired first the queue would have read 2 at t = 2 as well — same waits, different
    reported maximum, which is why the rule is declared and not left to the container.

Case B — priority, one server, four simultaneous-ish arrivals
------------------------------------------------------------
    job 0: arrives 0, service 10, priority 0
    jobs 1, 2, 3: all arrive at 1, service 1 each, priorities 2, 1, 0

    Job 0 occupies the server until t = 10. All three others queue. At t = 10 the queue is
    served by RANK, not arrival order: job 3 (rank 0), then job 2 (rank 1), then job 1 (rank 2).

    job 3: starts 10, departs 11, waits 9
    job 2: starts 11, departs 12, waits 10
    job 1: starts 12, departs 13, waits 11

    mean wait = (0+11+10+9)/4 = 7.5;  sojourns 10,12,11,10 -> mean 10.75
    horizon 13, L = 43/13, utilisation 1.0, max queue 3

Case C — FIFO inside one rank
-----------------------------
    arrivals 0,1,1; service 10,1,1; priorities 0,1,1. Jobs 1 and 2 share rank 1, so the tie
    falls to arrival order: job 1 starts at 10 (waits 9), job 2 at 11 (waits 10). If the
    waiting queue tie-broke the other way the two waits would swap, which no other assertion
    here would notice.

Case D — two servers, three simultaneous arrivals
-------------------------------------------------
    arrivals 0,0,0; service 5 each; capacity 2. Jobs 0 and 1 start immediately, job 2 waits.
    At t = 5 both finish; the first departure processed frees a server and job 2 starts.

    waits 0,0,5 -> mean 5/3;  sojourns 5,5,10 -> mean 20/3
    horizon 10, L = 20/10 = 2.0
    busy area = 2 servers x 5 + 1 server x 5 = 15, so utilisation = 15/(2*10) = 0.75

Case E — the warm-up window, and why Little's law is then UNAVAILABLE
--------------------------------------------------------------------
    Case A again with `warmup_jobs = 2`. The window starts at `arrival[2] = 2` and ends at 8.
    Number in system by interval: [2,3) = 2, [3,4) = 3, [4,6) = 2, [6,8) = 1, so the area is
    2 + 3 + 4 + 2 = 11 and L = 11/6. Retained waits are 2 and 3 (mean 2.5); retained sojourns
    are 4 and 5 (mean 4.5).

    `has_little_law_check` must be FALSE here. Jobs 0 and 1 are still in the system at t = 2 and
    contribute area with no sojourn term inside the window, so the identity does not hold — and
    an unavailable check is reported unavailable rather than answered from a broken premise.
"""
from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NEGATIVE_DURATION,
    DE_ERR_NON_FINITE,
    DE_ERR_PRIORITY_RANGE,
    DE_ERR_TIME_BACKWARD,
    DE_ERR_WARMUP_RANGE,
    DE_MAX_JOBS,
    DE_MAX_PRIORITY,
    DE_MAX_SERVERS,
    DE_OK,
)
from discrete_event.resource import resource_serve_flat, resource_work_charge


def _f(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    return o^


def _i(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    return o^


def _f3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c)
    return o^


def _i3(a: Int, b: Int, c: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a); o.append(b); o.append(c)
    return o^


def main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.resource] known-value suite")

    # ── case A ────────────────────────────────────────────────────────────────
    var arr_a = _f(0.0, 1.0, 2.0, 3.0)
    var svc_a = _f(2.0, 2.0, 2.0, 2.0)
    var pri_a = _i(0, 0, 0, 0)
    var a = resource_serve_flat(arr_a, svc_a, pri_a, 4, 1, 0)
    var ok_a = a.status == DE_OK and a.n_served == 4 and a.events_processed == 8
    ok_a = ok_a and a.wait[0] == 0.0 and a.wait[1] == 1.0
    ok_a = ok_a and a.wait[2] == 2.0 and a.wait[3] == 3.0
    ok_a = ok_a and a.start[1] == 2.0 and a.start[3] == 6.0
    ok_a = ok_a and a.depart[0] == 2.0 and a.depart[3] == 8.0
    ok_a = ok_a and a.horizon == 8.0 and a.observed_from == 0.0 and a.observed_span == 8.0
    ok_a = ok_a and a.has_mean_wait and a.mean_wait == 1.5
    ok_a = ok_a and a.has_mean_system and a.mean_system == 3.5
    ok_a = ok_a and a.has_time_avg_number and a.time_avg_number == 1.75
    ok_a = ok_a and a.has_utilization and a.utilization == 1.0
    if ok_a:
        passed += 1
        print("  ✅ D/D/1: waits 0,1,2,3; means 1.5 and 3.5; L = 14/8 = 1.75; utilisation 1.0")
    else:
        failed += 1
        print(
            "  ❌ D/D/1 schedule wrong:", a.wait[1], a.wait[2], a.wait[3], a.mean_wait,
            a.mean_system, a.time_avg_number, a.utilization,
        )

    if a.has_little_law_check and a.little_law_consistent and a.little_law_gap == 0.0:
        passed += 1
        print("  ✅ Little's law is EXACT over the full window: gap is exactly 0.0")
    else:
        failed += 1
        print(
            "  ❌ Little's law check failed:", a.has_little_law_check, a.little_law_consistent,
            a.little_law_gap,
        )

    if a.max_queue_length == 2:
        passed += 1
        print("  ✅ max queue 2 — departures resolve before arrivals at a shared timestamp")
    else:
        failed += 1
        print("  ❌ coincident-event rule changed: max queue", a.max_queue_length)

    # 2 events per job: calendar 2*8*levels(8) = 64, waiting 2*4*levels(4) = 24, total 88.
    if a.work_charged == 88 and resource_work_charge(4) == 88 and resource_work_charge(0) == 0:
        passed += 1
        print("  ✅ charged 64 calendar + 24 waiting-queue operations = 88, both heaps counted")
    else:
        failed += 1
        print("  ❌ work charge wrong:", a.work_charged, resource_work_charge(4))

    # ── case B: priority order ────────────────────────────────────────────────
    var arr_b = _f(0.0, 1.0, 1.0, 1.0)
    var svc_b = _f(10.0, 1.0, 1.0, 1.0)
    var pri_b = _i(0, 2, 1, 0)
    var b = resource_serve_flat(arr_b, svc_b, pri_b, 4, 1, 0)
    var ok_b = b.status == DE_OK
    ok_b = ok_b and b.start[3] == 10.0 and b.start[2] == 11.0 and b.start[1] == 12.0
    ok_b = ok_b and b.wait[3] == 9.0 and b.wait[2] == 10.0 and b.wait[1] == 11.0
    ok_b = ok_b and b.wait[0] == 0.0
    ok_b = ok_b and b.horizon == 13.0 and b.max_queue_length == 3
    ok_b = ok_b and b.has_mean_wait and b.mean_wait == 7.5
    ok_b = ok_b and b.has_mean_system and b.mean_system == 10.75
    ok_b = ok_b and b.has_time_avg_number and b.time_avg_number == 43.0 / 13.0
    ok_b = ok_b and b.has_little_law_check and b.little_law_consistent
    if ok_b:
        passed += 1
        print(
            "  ✅ priority: rank 0 served first (wait 9), then rank 1 (10), then rank 2 (11);",
            "L = 43/13",
        )
    else:
        failed += 1
        print(
            "  ❌ priority order wrong:", b.wait[1], b.wait[2], b.wait[3], b.mean_wait,
            b.time_avg_number,
        )

    # ── case C: FIFO inside a rank ────────────────────────────────────────────
    var c = resource_serve_flat(
        _f3(0.0, 1.0, 1.0), _f3(10.0, 1.0, 1.0), _i3(0, 1, 1), 3, 1, 0
    )
    if c.status == DE_OK and c.wait[1] == 9.0 and c.wait[2] == 10.0 and c.start[1] == 10.0:
        passed += 1
        print("  ✅ equal ranks break FIFO by arrival order: job 1 at t=10, job 2 at t=11")
    else:
        failed += 1
        print("  ❌ FIFO within a rank broken:", c.wait[1], c.wait[2])

    # ── case D: two servers ───────────────────────────────────────────────────
    var d = resource_serve_flat(
        _f3(0.0, 0.0, 0.0), _f3(5.0, 5.0, 5.0), _i3(0, 0, 0), 3, 2, 0
    )
    var ok_d = d.status == DE_OK and d.capacity == 2
    ok_d = ok_d and d.wait[0] == 0.0 and d.wait[1] == 0.0 and d.wait[2] == 5.0
    ok_d = ok_d and d.horizon == 10.0 and d.max_queue_length == 1
    ok_d = ok_d and d.has_mean_wait and d.mean_wait == 5.0 / 3.0
    ok_d = ok_d and d.has_mean_system and d.mean_system == 20.0 / 3.0
    ok_d = ok_d and d.has_time_avg_number and d.time_avg_number == 2.0
    ok_d = ok_d and d.has_utilization and d.utilization == 0.75
    ok_d = ok_d and d.has_little_law_check and d.little_law_consistent
    if ok_d:
        passed += 1
        print("  ✅ two servers: waits 0,0,5; L = 2.0; utilisation = 15/(2*10) = 0.75")
    else:
        failed += 1
        print(
            "  ❌ multi-server run wrong:", d.wait[2], d.mean_wait, d.time_avg_number,
            d.utilization,
        )

    # ── case E: the warm-up window ────────────────────────────────────────────
    var e = resource_serve_flat(arr_a, svc_a, pri_a, 4, 1, 2)
    var ok_e = e.status == DE_OK and e.n_discarded == 2 and e.n_retained == 2
    ok_e = ok_e and e.observed_from == 2.0 and e.observed_span == 6.0
    ok_e = ok_e and e.has_mean_wait and e.mean_wait == 2.5
    ok_e = ok_e and e.has_mean_system and e.mean_system == 4.5
    ok_e = ok_e and e.has_time_avg_number and e.time_avg_number == 11.0 / 6.0
    ok_e = ok_e and e.has_utilization and e.utilization == 1.0
    # The per-job arrays still cover EVERY job, not only the retained ones.
    ok_e = ok_e and len(e.wait) == 4 and e.wait[0] == 0.0 and e.wait[3] == 3.0
    if ok_e:
        passed += 1
        print(
            "  ✅ warm-up window [2,8]: 2 discarded, means 2.5 and 4.5, L = 11/6, all four",
            "per-job rows still returned",
        )
    else:
        failed += 1
        print(
            "  ❌ truncated window wrong:", e.observed_from, e.observed_span, e.mean_wait,
            e.mean_system, e.time_avg_number,
        )

    if not e.has_little_law_check and not e.little_law_consistent and e.little_law_gap == 0.0:
        passed += 1
        print(
            "  ✅ Little's law is reported UNAVAILABLE on a truncated window, not answered",
            "from a broken premise",
        )
    else:
        failed += 1
        print(
            "  ❌ a truncated window still claimed a Little's law verdict:",
            e.has_little_law_check, e.little_law_consistent,
        )

    # ── refusals ──────────────────────────────────────────────────────────────
    var over = resource_serve_flat(arr_a, svc_a, pri_a, 25, 1, 0)
    var empty_call = resource_serve_flat(arr_a, svc_a, pri_a, 0, 1, 0)
    var big = resource_serve_flat(arr_a, svc_a, pri_a, DE_MAX_JOBS + 1, 1, 0)
    var cap0 = resource_serve_flat(arr_a, svc_a, pri_a, 4, 0, 0)
    var cap_big = resource_serve_flat(arr_a, svc_a, pri_a, 4, DE_MAX_SERVERS + 1, 0)
    var warm_neg = resource_serve_flat(arr_a, svc_a, pri_a, 4, 1, -1)
    var warm_all = resource_serve_flat(arr_a, svc_a, pri_a, 4, 1, 4)
    var neg_svc = resource_serve_flat(arr_a, _f(2.0, -1.0, 2.0, 2.0), pri_a, 4, 1, 0)
    var back = resource_serve_flat(_f(0.0, 5.0, 2.0, 3.0), svc_a, pri_a, 4, 1, 0)
    var neg_arr = resource_serve_flat(_f(-1.0, 1.0, 2.0, 3.0), svc_a, pri_a, 4, 1, 0)
    var nan_arr = resource_serve_flat(_f(0.0, 0.0 / 0.0, 2.0, 3.0), svc_a, pri_a, 4, 1, 0)
    var neg_pri = resource_serve_flat(arr_a, svc_a, _i(0, -1, 0, 0), 4, 1, 0)
    var top_pri = resource_serve_flat(arr_a, svc_a, _i(0, DE_MAX_PRIORITY, 0, 0), 4, 1, 0)
    var inf_svc = resource_serve_flat(arr_a, _f(1e308, 1e308, 1e308, 1e308), pri_a, 4, 1, 0)

    var refusals = over.status == DE_ERR_COUNT
    refusals = refusals and empty_call.status == DE_ERR_EMPTY
    refusals = refusals and big.status == DE_ERR_COUNT
    refusals = refusals and cap0.status == DE_ERR_CAPACITY
    refusals = refusals and cap_big.status == DE_ERR_CAPACITY
    refusals = refusals and warm_neg.status == DE_ERR_WARMUP_RANGE
    refusals = refusals and warm_all.status == DE_ERR_WARMUP_RANGE
    refusals = refusals and neg_svc.status == DE_ERR_NEGATIVE_DURATION
    refusals = refusals and back.status == DE_ERR_TIME_BACKWARD
    refusals = refusals and neg_arr.status == DE_ERR_TIME_BACKWARD
    refusals = refusals and nan_arr.status == DE_ERR_NON_FINITE
    refusals = refusals and neg_pri.status == DE_ERR_PRIORITY_RANGE
    refusals = refusals and top_pri.status == DE_ERR_PRIORITY_RANGE
    refusals = refusals and inf_svc.status == DE_ERR_NON_FINITE
    refusals = refusals and len(over.wait) == 0 and len(warm_neg.wait) == 0
    if refusals:
        passed += 1
        print(
            "  ✅ fourteen refusals: over-count, empty, ceiling, both capacity bounds, BOTH",
            "warm-up directions, negative service, backward and negative arrivals, NaN,",
            "both priority bounds, and a departure that overflows to infinity",
        )
    else:
        failed += 1
        print(
            "  ❌ refusal codes wrong:", over.status, empty_call.status, big.status, cap0.status,
            cap_big.status, warm_neg.status, warm_all.status, neg_svc.status, back.status,
            neg_arr.status, nan_arr.status, neg_pri.status, top_pri.status, inf_svc.status,
        )

    # DE_MAX_PRIORITY - 1 is the documented top of the accepted range, because the calendar
    # carries 1 + job_priority. The boundary is asserted from BOTH sides.
    var edge = resource_serve_flat(
        arr_a, svc_a, _i(0, DE_MAX_PRIORITY - 1, 0, 0), 4, 1, 0
    )
    if edge.status == DE_OK:
        passed += 1
        print("  ✅ priority DE_MAX_PRIORITY-1 is accepted; DE_MAX_PRIORITY is not")
    else:
        failed += 1
        print("  ❌ the documented top priority was refused:", edge.status)

    # Zero-duration service is legal — an instantaneous job is not an error — and the run must
    # still be internally consistent.
    var zero = resource_serve_flat(arr_a, _f(0.0, 0.0, 0.0, 0.0), pri_a, 4, 1, 0)
    if zero.status == DE_OK and zero.has_mean_wait and zero.mean_wait == 0.0 \
            and zero.has_utilization and zero.utilization == 0.0:
        passed += 1
        print("  ✅ zero-duration service is legal: no waits, zero utilisation, still DE_OK")
    else:
        failed += 1
        print("  ❌ zero-duration service mishandled:", zero.status, zero.mean_wait,
              zero.utilization)

    print("  [discrete_event.resource] Passed:", passed, "Failed:", failed)
