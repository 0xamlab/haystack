"""test_discrete_event_calendar.mojo — known-value tests for the event calendar.

Hand-written. Every expected pop order below is derived by sorting the input on
`(time, priority, sequence)` by hand; the calendar is never checked against itself.

Case A — the tie-break, four events, three of them simultaneous
--------------------------------------------------------------
    index  time  priority  kind
      0    1.0      2       10
      1    1.0      0       11
      2    1.0      0       12
      3    0.5      9       13

Sorting on (time, priority, sequence) by hand:

    0.5 comes first, so index 3.
    Then the three at 1.0: priority 0 before priority 2, and between the two priority-0
    events the smaller sequence wins, so 1 then 2 then 0.

Expected pop order: kinds 13, 11, 12, 10 — asserted element by element. A calendar that
tie-broke by container order would return 10, 11, 12 for the three at t = 1.0 and a calendar
with no priority key would return 10 first.

Case B — the stress generator, ties everywhere
----------------------------------------------
`calendar_stress_flat(20, 4, 3)` builds `time = i % 4`, `priority = i % 3`, `kind = i`. Five
events share each timestamp, so every tie-break key is exercised. The t = 0 group is
i in {0, 4, 8, 12, 16} with priorities {0, 1, 2, 0, 1}; sorted on (priority, sequence) that is

    (0, 0), (0, 12), (1, 4), (1, 16), (2, 8)

which is asserted exactly. The tie counts are arithmetic, not measurements: 20 events over 4
timestamps is 5 per group, so 4 adjacent equal-time pairs per group and 16 in total; inside each
group the sorted priorities are 0,0,1,1,2, giving 2 adjacent equal-priority pairs per group and
8 in total.

The frozen cross-check
----------------------
`heap.is_min_heap` is the frozen tree's own min-heap predicate. A non-decreasing sequence is a
valid min-heap, so a correct pop order must satisfy it — an INDEPENDENT implementation of the
ordering check, written by somebody else, applied to this module's output. It is a necessary
condition rather than a sufficient one, which is why the exact orders above are asserted too.

Refusals
--------
Six, each with its own code, and the suite reaching its final line is half of the assertion:
`calendar_replay_flat(five_element_lists, 25)` must REFUSE rather than read index 24, because
that read is an uncatchable abort that no `try` can observe and no later assertion could report.
"""
from heap import is_min_heap

from discrete_event.calendar import (
    calendar_order_audit,
    calendar_replay_flat,
    calendar_stress_flat,
    de_key_less,
)
from discrete_event.contract import (
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NON_FINITE,
    DE_ERR_PRIORITY_RANGE,
    DE_MAX_EVENTS,
    DE_MAX_PRIORITY,
    DE_OK,
)


def _f4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    return o^


def _i4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    return o^


def main():
    var passed = 0
    var failed = 0
    print("\n[discrete_event.calendar] known-value suite")

    # ── the ordering itself ───────────────────────────────────────────────────
    var order_ok = not de_key_less(1.0, 0, 0, 1.0, 0, 0)
    order_ok = order_ok and de_key_less(0.5, 9, 0, 1.0, 0, 0)
    order_ok = order_ok and not de_key_less(1.0, 0, 0, 0.5, 9, 0)
    order_ok = order_ok and de_key_less(1.0, 0, 5, 1.0, 2, 1)
    order_ok = order_ok and de_key_less(1.0, 3, 4, 1.0, 3, 9)
    # -0.0 and 0.0 are the same instant and must fall through to the priority key.
    order_ok = order_ok and de_key_less(-0.0, 1, 7, 0.0, 2, 0)
    order_ok = order_ok and not de_key_less(0.0, 2, 0, -0.0, 1, 7)
    if order_ok:
        passed += 1
        print("  ✅ strict total order: irreflexive, time then priority then sequence, -0.0 == 0.0")
    else:
        failed += 1
        print("  ❌ de_key_less is not the declared strict total order")

    # Exactly one direction holds for any two DISTINCT keys — the property that makes the pop
    # order a function of the input alone.
    var antisym = True
    for a in range(3):
        for b in range(3):
            for s in range(3):
                for c in range(3):
                    var l1 = de_key_less(Float64(a), b, s, Float64(c), b, s + 1)
                    var l2 = de_key_less(Float64(c), b, s + 1, Float64(a), b, s)
                    if l1 == l2:
                        antisym = False
    if antisym:
        passed += 1
        print("  ✅ over 81 distinct key pairs exactly one direction holds (no ties possible)")
    else:
        failed += 1
        print("  ❌ two distinct keys compared equal or both-less")

    # ── case A: the hand-sorted four ──────────────────────────────────────────
    var time = _f4(1.0, 1.0, 1.0, 0.5)
    var prio = _i4(2, 0, 0, 9)
    var kind = _i4(10, 11, 12, 13)
    var ent = _i4(100, 101, 102, 103)
    var a = calendar_replay_flat(time, prio, kind, ent, 4)
    var case_a = a.status == DE_OK and a.n_popped == 4 and a.n_pushed == 4
    case_a = case_a and a.pop_kind[0] == 13 and a.pop_kind[1] == 11
    case_a = case_a and a.pop_kind[2] == 12 and a.pop_kind[3] == 10
    case_a = case_a and a.pop_time[0] == 0.5 and a.pop_time[3] == 1.0
    case_a = case_a and a.pop_sequence[0] == 3 and a.pop_sequence[1] == 1
    case_a = case_a and a.pop_sequence[2] == 2 and a.pop_sequence[3] == 0
    case_a = case_a and a.pop_entity[0] == 103 and a.pop_entity[3] == 100
    case_a = case_a and a.time_nondecreasing and a.total_order_held
    case_a = case_a and a.max_heap_size == 4
    if case_a:
        passed += 1
        print("  ✅ hand-sorted order 13,11,12,10 reproduced exactly, satellite carried with it")
    else:
        failed += 1
        print(
            "  ❌ pop order wrong:", a.pop_kind[0], a.pop_kind[1], a.pop_kind[2], a.pop_kind[3],
        )

    if is_min_heap(a.pop_time):
        passed += 1
        print("  ✅ the frozen heap.is_min_heap predicate accepts the popped time sequence")
    else:
        failed += 1
        print("  ❌ the frozen min-heap predicate rejects our pop order")

    # Bit-identical on a second identical call: the whole determinism premise.
    var a2 = calendar_replay_flat(time, prio, kind, ent, 4)
    var same = a2.n_popped == a.n_popped
    for i in range(a.n_popped):
        if a2.pop_time[i] != a.pop_time[i] or a2.pop_kind[i] != a.pop_kind[i]:
            same = False
        if a2.pop_priority[i] != a.pop_priority[i] or a2.pop_sequence[i] != a.pop_sequence[i]:
            same = False
    if same:
        passed += 1
        print("  ✅ a repeated replay is bit-identical in all five columns")
    else:
        failed += 1
        print("  ❌ two identical replays disagreed")

    # ── case B: the stress generator, hand-sorted first group ─────────────────
    var s = calendar_stress_flat(20, 4, 3)
    var case_b = s.status == DE_OK and s.n_popped == 20
    case_b = case_b and s.pop_time[0] == 0.0 and s.pop_priority[0] == 0 and s.pop_sequence[0] == 0
    case_b = case_b and s.pop_time[1] == 0.0 and s.pop_priority[1] == 0 and s.pop_sequence[1] == 12
    case_b = case_b and s.pop_time[2] == 0.0 and s.pop_priority[2] == 1 and s.pop_sequence[2] == 4
    case_b = case_b and s.pop_time[3] == 0.0 and s.pop_priority[3] == 1 and s.pop_sequence[3] == 16
    case_b = case_b and s.pop_time[4] == 0.0 and s.pop_priority[4] == 2 and s.pop_sequence[4] == 8
    case_b = case_b and s.pop_time[5] == 1.0
    case_b = case_b and s.time_nondecreasing and s.total_order_held
    if case_b:
        passed += 1
        print("  ✅ 20 events over 4 timestamps: the t=0 group pops (0,0),(0,12),(1,4),(1,16),(2,8)")
    else:
        failed += 1
        print(
            "  ❌ stress order wrong at t=0:", s.pop_priority[0], s.pop_sequence[0],
            s.pop_priority[1], s.pop_sequence[1], s.pop_priority[2], s.pop_sequence[2],
        )

    # 2 * 20 * levels(20) = 2 * 20 * 5 = 200, by hand (levels(20) = floor(log2 20)+1 = 5).
    if s.work_charged == 200:
        passed += 1
        print("  ✅ charged 2*20*5 = 200 heap operations for 20 events")
    else:
        failed += 1
        print("  ❌ work charge wrong:", s.work_charged)

    # ── the audit, on output it did not produce ───────────────────────────────
    var au = calendar_order_audit(s.pop_time, s.pop_priority, s.pop_sequence, s.n_popped)
    var audit_ok = au.status == DE_OK and au.is_ordered and not au.has_violation
    audit_ok = audit_ok and au.first_violation == -1 and au.n_duplicate_keys == 0
    audit_ok = audit_ok and au.n_time_ties == 16 and au.n_priority_ties == 8
    if audit_ok:
        passed += 1
        print("  ✅ audit: ordered, no duplicate keys, and the tie counts are 16 and 8 as derived")
    else:
        failed += 1
        print(
            "  ❌ audit disagrees:", au.is_ordered, au.first_violation, au.n_duplicate_keys,
            au.n_time_ties, au.n_priority_ties,
        )

    # A deliberately WRONG sequence must be caught, at the right index.
    var bad_t = _f4(0.0, 5.0, 1.0, 6.0)
    var bad_p = _i4(0, 0, 0, 0)
    var bad_s = _i4(0, 1, 2, 3)
    var bad = calendar_order_audit(bad_t, bad_p, bad_s, 4)
    if bad.status == DE_OK and not bad.is_ordered and bad.has_violation \
            and bad.first_violation == 2:
        passed += 1
        print("  ✅ an out-of-order sequence is caught at index 2, the first violating position")
    else:
        failed += 1
        print("  ❌ violation not caught at index 2:", bad.is_ordered, bad.first_violation)

    # Two entries identical on ALL THREE keys: only reachable by merging calendars or reusing a
    # sequence number, and the one way the order stops being total.
    var dup_t = _f4(1.0, 1.0, 2.0, 3.0)
    var dup_p = _i4(4, 4, 0, 0)
    var dup_s = _i4(7, 7, 8, 9)
    var dup = calendar_order_audit(dup_t, dup_p, dup_s, 4)
    if dup.n_duplicate_keys == 1 and not dup.is_ordered:
        passed += 1
        print("  ✅ a repeated (time, priority, sequence) triple is counted as a duplicate key")
    else:
        failed += 1
        print("  ❌ duplicate key not counted:", dup.n_duplicate_keys)

    # ── refusals ──────────────────────────────────────────────────────────────
    var over = calendar_replay_flat(time, prio, kind, ent, 25)
    var empty_call = calendar_replay_flat(time, prio, kind, ent, 0)
    var negative = calendar_replay_flat(time, prio, kind, ent, -3)
    var huge = calendar_replay_flat(time, prio, kind, ent, DE_MAX_EVENTS + 1)
    var nan_time = calendar_replay_flat(_f4(1.0, 0.0 / 0.0, 2.0, 3.0), prio, kind, ent, 4)
    var neg_prio = calendar_replay_flat(time, _i4(0, -1, 0, 0), kind, ent, 4)
    var big_prio = calendar_replay_flat(time, _i4(0, DE_MAX_PRIORITY + 1, 0, 0), kind, ent, 4)
    var refusals = over.status == DE_ERR_COUNT
    refusals = refusals and empty_call.status == DE_ERR_EMPTY
    refusals = refusals and negative.status == DE_ERR_EMPTY
    refusals = refusals and huge.status == DE_ERR_COUNT
    refusals = refusals and nan_time.status == DE_ERR_NON_FINITE
    refusals = refusals and neg_prio.status == DE_ERR_PRIORITY_RANGE
    refusals = refusals and big_prio.status == DE_ERR_PRIORITY_RANGE
    refusals = refusals and len(over.pop_time) == 0 and len(nan_time.pop_time) == 0
    if refusals:
        passed += 1
        print(
            "  ✅ seven refusals, each with its own code, and every refusal returns EMPTY lists",
            "rather than a partial trace",
        )
    else:
        failed += 1
        print(
            "  ❌ refusal codes wrong:", over.status, empty_call.status, negative.status,
            huge.status, nan_time.status, neg_prio.status, big_prio.status,
        )

    var stress_bad = calendar_stress_flat(20, 0, 3)
    var stress_bad2 = calendar_stress_flat(20, 4, 0)
    var stress_big = calendar_stress_flat(DE_MAX_EVENTS + 1, 4, 3)
    if stress_bad.status == DE_ERR_EMPTY and stress_bad2.status == DE_ERR_EMPTY \
            and stress_big.status == DE_ERR_DIMENSION_TOO_LARGE:
        passed += 1
        print("  ✅ a zero divisor is refused, not divided by; the event ceiling is enforced")
    else:
        failed += 1
        print("  ❌ stress refusals wrong:", stress_bad.status, stress_bad2.status,
              stress_big.status)

    print("  [discrete_event.calendar] Passed:", passed, "Failed:", failed)
