"""
discrete_event.calendar — a totally-ordered event calendar. Zero Python imports.

The tie-breaking IS the determinism
-----------------------------------
A discrete-event simulation advances by popping the next event. If two events can compare
EQUAL, the pop order is decided by whatever the container happens to do, and the same seed
gives different answers on a different day, a different list length or a different compiler.
So the ordering here is a TOTAL order and nothing is left to the container:

    (time, priority, sequence)   lexicographic, all three ascending

`sequence` is a monotone counter assigned at push and never reused, so two entries can never
tie on all three keys and `de_key_less` is a strict total order on everything the calendar has
ever held. `de_event_order()` returns the identifier of that rule so a stored result can name
it, and `calendar_order_audit` lets a caller CHECK a sequence against it instead of trusting
this docstring.

`priority` is a rank with 0 most urgent, and it is deliberately the SECOND key, not the first:
a priority that outranked time would let an urgent event fire before events that already
happened, which is not a simulation.

Why not the frozen heap
-----------------------
`heap.mojo` is a real binary min-heap with true O(log n) push and pop, and it is called
elsewhere in this tree for exactly that. It cannot be used here: it stores `List[Float64]`
where the value IS the key, so it can carry neither the two integer tie-break keys nor the
`kind`/`entity` satellite an event needs. That is a shape limit, not a defect, and the frozen
kernel stays the right answer for a bare float priority queue. What this module adds is the
composite key and the satellite arrays — and `heap.is_min_heap` is still the cross-check: with
a lexicographic (time, priority, sequence) order, a parent that precedes its children also has
`parent_time <= child_time`, so the time array of a valid calendar must satisfy the FROZEN
heap predicate. The suite asserts exactly that, which is how this heap is checked against
something other than itself.

Why not `simulation.mojo`
-------------------------
`simulation.schedule_event` inserts before the first strictly-later event by a LINEAR scan and
then shifts every following entry, so building a calendar of `n` events is O(n^2) — measured in
`bench_discrete_event.mojo` against this module's O(n log n). It also has no priority field at
all, and its tie behaviour (FIFO among equal timestamps) is a consequence of the insertion
condition rather than a declared rule. It stays reachable and unchanged; this is an additive
namespace.

Internals are shared, not copied
--------------------------------
`_EventHeap` and its five sift/push/pop helpers are underscore-prefixed, which keeps them out
of the runtime contract (a heap of parallel satellite arrays is not a wire type) while letting
`discrete_event.resource` import the SAME implementation. Rule 3 applies inside a package: a
second heap in `resource.mojo` would be a second ordering rule, and the two would drift. The same
reasoning is why `benchmarks/mojo_benchmarks/bench_phold.mojo` reaches these names instead of
re-implementing a heap: a benchmark that measures its own copy is not measuring the product.

`_heap_replace_root` is the fifth helper and the newest. It performs a pop and a push as ONE sift
for the caller that has already read slot 0, which is the discrete-event fast path; see its own
docstring for the 1.58x-1.91x it is worth and for the bit-identical-pop-order guarantee the PHOLD
benchmark gates it against.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_discrete_event_calendar.mojo
benchmark: benchmarks/mojo_benchmarks/bench_discrete_event.mojo
docs: gitbook/engine/discrete-event-simulation.md
version_introduced: 2026.07.31
deprecation_state: active
@endcapability
"""
from discrete_event.contract import (
    DE_ERR_COUNT,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NON_FINITE,
    DE_ERR_PRIORITY_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_EVENTS,
    DE_MAX_PRIORITY,
    DE_OK,
    de_all_finite,
    de_heap_work,
    de_heap_work_fits,
)


# ── the ordering ──────────────────────────────────────────────────────────────


def de_key_less(
    time_a: Float64, priority_a: Int, sequence_a: Int,
    time_b: Float64, priority_b: Int, sequence_b: Int,
) -> Bool:
    """True when event A pops before event B under `de_event_order()`.

    The whole ordering rule, in one place, exported so a caller can reproduce the calendar's
    decisions without re-running it. Lexicographic on `(time, priority, sequence)`: earlier
    time first, then lower priority rank (0 is most urgent), then lower insertion sequence
    (FIFO among otherwise identical events).

    Strict: `de_key_less(k, k)` is False for every key, and because `sequence` is never reused
    no two calendar entries share one, so exactly one of `less(a,b)` and `less(b,a)` holds for
    any two distinct entries. That is what makes the pop order a function of the input alone.

    `-0.0` and `0.0` compare EQUAL here and fall through to the priority key, which is the
    intended behaviour: they are the same instant, and letting the sign of a zero decide an
    event order would be an ordering no caller could predict.

    A non-finite `time` would break this into a non-order — every comparison against a NaN is
    False, so `less(a,b)` and `less(b,a)` would both be False for distinct entries. This
    function does not check for it, because it is a two-key comparison with no room for a
    status; the CALENDAR refuses a non-finite time at the door (`DE_ERR_NON_FINITE`) so no
    NaN ever reaches it.

    @capability de_key_less
    complexity: O(1)
    counts: none
    @endcapability
    """
    if time_a < time_b:
        return True
    if time_a > time_b:
        return False
    if priority_a < priority_b:
        return True
    if priority_a > priority_b:
        return False
    return sequence_a < sequence_b


# ── the heap (package-internal; see the module docstring) ──────────────────────


struct _EventHeap(Copyable, Movable):
    """A binary min-heap on `(time, priority, sequence)` with two satellite integers.

    Parallel arrays rather than a list of structs so that the hot comparison reads three
    contiguous slots. Every index used here is derived from `len(self.t)`, so no read can pass
    the end — which matters more than usual: a `List` read past the end is an uncatchable abort
    that ends the worker process, and a heap is nothing but index arithmetic.
    """

    var t: List[Float64]
    var pri: List[Int]
    var seq: List[Int]
    var kind: List[Int]
    var ent: List[Int]

    def __init__(out self):
        self.t = List[Float64]()
        self.pri = List[Int]()
        self.seq = List[Int]()
        self.kind = List[Int]()
        self.ent = List[Int]()


def _heap_size(h: _EventHeap) -> Int:
    return len(h.t)


def _heap_swap(mut h: _EventHeap, i: Int, j: Int):
    """Swap two heap slots. Callers only ever pass indices below `len(h.t)`."""
    var t = h.t[i]; h.t[i] = h.t[j]; h.t[j] = t
    var p = h.pri[i]; h.pri[i] = h.pri[j]; h.pri[j] = p
    var s = h.seq[i]; h.seq[i] = h.seq[j]; h.seq[j] = s
    var k = h.kind[i]; h.kind[i] = h.kind[j]; h.kind[j] = k
    var e = h.ent[i]; h.ent[i] = h.ent[j]; h.ent[j] = e


def _heap_sift_up(mut h: _EventHeap, start: Int):
    var pos = start
    while pos > 0:
        var parent = (pos - 1) // 2
        if de_key_less(
            h.t[pos], h.pri[pos], h.seq[pos], h.t[parent], h.pri[parent], h.seq[parent]
        ):
            _heap_swap(h, pos, parent)
            pos = parent
        else:
            break


def _heap_sift_down(mut h: _EventHeap, start: Int):
    var n = _heap_size(h)
    var pos = start
    while True:
        var left = 2 * pos + 1
        if left >= n:
            break
        var best = left
        var right = left + 1
        if right < n and de_key_less(
            h.t[right], h.pri[right], h.seq[right], h.t[left], h.pri[left], h.seq[left]
        ):
            best = right
        if de_key_less(
            h.t[best], h.pri[best], h.seq[best], h.t[pos], h.pri[pos], h.seq[pos]
        ):
            _heap_swap(h, pos, best)
            pos = best
        else:
            break


def _heap_push(
    mut h: _EventHeap, time: Float64, priority: Int, sequence: Int, kind: Int, entity: Int
):
    """Append then sift up — one heap depth of comparisons, which is what the work budget
    charges for."""
    h.t.append(time)
    h.pri.append(priority)
    h.seq.append(sequence)
    h.kind.append(kind)
    h.ent.append(entity)
    _heap_sift_up(h, _heap_size(h) - 1)


def _heap_drop_root(mut h: _EventHeap):
    """Remove the minimum. The caller reads slot 0 BEFORE calling this.

    Split that way on purpose: returning five values would need a struct, and a struct declared
    for an internal pop would then be tempting to put in a public signature — where a struct
    owned by another module is silently dropped from the contract.
    """
    var n = _heap_size(h)
    if n == 0:
        return
    if n == 1:
        _ = h.t.pop()
        _ = h.pri.pop()
        _ = h.seq.pop()
        _ = h.kind.pop()
        _ = h.ent.pop()
        return
    _heap_swap(h, 0, n - 1)
    _ = h.t.pop()
    _ = h.pri.pop()
    _ = h.seq.pop()
    _ = h.kind.pop()
    _ = h.ent.pop()
    _heap_sift_down(h, 0)


def _heap_replace_root(
    mut h: _EventHeap, time: Float64, priority: Int, sequence: Int, kind: Int, entity: Int
):
    """Overwrite the minimum with a new entry, in ONE sift. The caller reads slot 0 first.

    This is the discrete-event fast path — "process the imminent event, schedule the next one" —
    and it is a single operation rather than a pop followed by a push. The difference is not
    cosmetic. `_heap_drop_root` then `_heap_push` costs a sift-down, five `List.pop`s, five
    `List.append`s and a sift-up; this costs one sift-down. Measured on the PHOLD driver in
    `benchmarks/mojo_benchmarks/bench_phold.mojo`, interleaved A/B on the same heap and the same
    seed, the pair costs 1.58x to 1.91x more per event across pending populations from 128 to
    262,144 — and the two produce a BIT-IDENTICAL pop order, which that benchmark gates.

    There is no precondition on `time`. The root has no parent, so sifting down alone restores the
    heap property for ANY new key: a key smaller than both children simply stays where it is. That
    is worth stating because the obvious guess — that the new event must be no earlier than the one
    just popped — would be an unnecessary restriction, and a caller who believed it would reach for
    the slower pair whenever it could not prove it.

    Written in the HOLE style rather than with `_heap_swap`: the new entry is not stored until its
    final slot is known, so a descent of `d` levels does `d` single writes per array instead of `d`
    swaps (each of which is two reads and two writes per array). The comparison is the same
    `de_key_less` the rest of the calendar uses, so there is still exactly one ordering rule in this
    package.

    An empty heap is a push, not a crash: `_heap_size(h) == 0` means there was no root to replace,
    and appending is the only interpretation that leaves the entry in the calendar. Every index
    below is derived from `_heap_size(h)`, so no read can pass the end — which matters more than
    usual, because a `List` read past the end is an uncatchable abort that ends the worker process.
    """
    var n = _heap_size(h)
    if n == 0:
        _heap_push(h, time, priority, sequence, kind, entity)
        return
    var pos = 0
    while True:
        var left = 2 * pos + 1
        if left >= n:
            break
        var best = left
        var right = left + 1
        if right < n and de_key_less(
            h.t[right], h.pri[right], h.seq[right], h.t[left], h.pri[left], h.seq[left]
        ):
            best = right
        if not de_key_less(h.t[best], h.pri[best], h.seq[best], time, priority, sequence):
            break
        h.t[pos] = h.t[best]
        h.pri[pos] = h.pri[best]
        h.seq[pos] = h.seq[best]
        h.kind[pos] = h.kind[best]
        h.ent[pos] = h.ent[best]
        pos = best
    h.t[pos] = time
    h.pri[pos] = priority
    h.seq[pos] = sequence
    h.kind[pos] = kind
    h.ent[pos] = entity


# ── results ───────────────────────────────────────────────────────────────────


@fieldwise_init
struct CalendarTrace(Copyable, Movable):
    """What a calendar popped, in the order it popped it, plus the order's own audit.

    `time_nondecreasing` and `total_order_held` are computed from the OUTPUT rather than
    assumed from the algorithm. They are the two properties a caller depends on, and a heap is
    index arithmetic — the kind of code that is wrong in a way no reader notices. Reporting
    them costs one pass and turns "the heap is correct" into a value.

    Every list has `n_popped` entries and they are index-aligned. On any refusal the lists are
    EMPTY and `status` names the defect: a partial trace would read as a complete simulation.
    """

    var status: Int
    var n_pushed: Int
    var n_popped: Int
    var max_heap_size: Int
    var work_charged: Int
    var time_nondecreasing: Bool
    var total_order_held: Bool
    var pop_time: List[Float64]
    var pop_priority: List[Int]
    var pop_sequence: List[Int]
    var pop_kind: List[Int]
    var pop_entity: List[Int]


def _trace_refusal(code: Int) -> CalendarTrace:
    """A refusal carries no numbers at all — not zeros that look like a run of length zero."""
    return CalendarTrace(
        code, 0, 0, 0, 0, False, False,
        List[Float64](), List[Int](), List[Int](), List[Int](), List[Int](),
    )


@fieldwise_init
struct OrderAudit(Copyable, Movable):
    """Whether a claimed event sequence obeys `de_event_order()`.

    `first_violation` is -1 when there is none. `n_duplicate_keys` counts adjacent pairs equal
    on ALL THREE keys, which cannot happen inside one calendar (sequence is unique) and
    therefore means the caller merged two calendars or reused a sequence number — the one way
    the order stops being total, and worth its own count rather than being folded into
    `is_ordered`.
    """

    var status: Int
    var n_checked: Int
    var is_ordered: Bool
    var has_violation: Bool
    var first_violation: Int
    var n_duplicate_keys: Int
    var n_time_ties: Int
    var n_priority_ties: Int


def _audit_refusal(code: Int) -> OrderAudit:
    return OrderAudit(code, 0, False, False, -1, 0, 0, 0)


# ── drivers ───────────────────────────────────────────────────────────────────


def calendar_replay_flat(
    time: List[Float64], priority: List[Int], kind: List[Int], entity: List[Int],
    n_events: Int,
) -> CalendarTrace:
    """Push the first `n_events` entries, pop them all, and report the order they came out in.

    The four input lists are index-aligned columns of one event table. `sequence` is not an
    input: it is assigned as the push index `0..n_events-1`, which is what makes the order total
    and is why two identical `(time, priority)` rows come out in the order the caller listed
    them. A caller who wants a different tie order must express it in `priority`.

    Refusals, each with its own code, and NONE of them reachable as a wrong answer:

      * `n_events` above any of the four list lengths -> `DE_ERR_COUNT`. Checked before the
        first read. This is the relation that matters most: the generated A-Z suite calls every
        contract function with FIVE-element lists and `5` for every `Int`, and a driver that
        trusted a larger count would abort the worker on a five-element list the first time the
        suite ran.
      * `n_events <= 0` -> `DE_ERR_EMPTY`. A calendar of nothing has no pop order; an empty
        trace with `DE_OK` would read as one.
      * `n_events` above `DE_MAX_EVENTS` -> `DE_ERR_DIMENSION_TOO_LARGE`.
      * push+pop work above `DE_MAX_WORK` -> `DE_ERR_WORK_BUDGET`. Bounding the event count
        alone is not bounding the work: each operation costs a heap depth, and the depth is a
        factor of the product being charged.
      * a non-finite time -> `DE_ERR_NON_FINITE`. Every comparison against a NaN is False, so
        one NaN turns the strict order into a non-order and the heap silently stops being a
        heap. It is refused at the door so `de_key_less` never sees one.
      * a priority outside `[0, DE_MAX_PRIORITY]` -> `DE_ERR_PRIORITY_RANGE`. A negative rank
        is refused rather than read as "extremely urgent"; `kind` and `entity` are opaque
        satellite and are not range-checked because nothing indexes with them.

    @capability calendar_replay_flat
    complexity: O(n_events log n_events)
    counts:
    - n_events <= len(time, priority, kind, entity) [kernel_validated]
    @endcapability
    """
    if n_events > len(time) or n_events > len(priority):
        return _trace_refusal(DE_ERR_COUNT)
    if n_events > len(kind) or n_events > len(entity):
        return _trace_refusal(DE_ERR_COUNT)
    if n_events <= 0:
        return _trace_refusal(DE_ERR_EMPTY)
    if n_events > DE_MAX_EVENTS:
        return _trace_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if not de_heap_work_fits(n_events):
        return _trace_refusal(DE_ERR_WORK_BUDGET)
    if not de_all_finite(time, n_events):
        return _trace_refusal(DE_ERR_NON_FINITE)
    for i in range(n_events):
        if priority[i] < 0 or priority[i] > DE_MAX_PRIORITY:
            return _trace_refusal(DE_ERR_PRIORITY_RANGE)

    var h = _EventHeap()
    var peak = 0
    for i in range(n_events):
        _heap_push(h, time[i], priority[i], i, kind[i], entity[i])
        if _heap_size(h) > peak:
            peak = _heap_size(h)

    var out_t = List[Float64]()
    var out_p = List[Int]()
    var out_s = List[Int]()
    var out_k = List[Int]()
    var out_e = List[Int]()
    var monotone = True
    var ordered = True
    while _heap_size(h) > 0:
        var t = h.t[0]
        var p = h.pri[0]
        var s = h.seq[0]
        var k = h.kind[0]
        var e = h.ent[0]
        _heap_drop_root(h)
        if len(out_t) > 0:
            var last = len(out_t) - 1
            if t < out_t[last]:
                monotone = False
            if not de_key_less(out_t[last], out_p[last], out_s[last], t, p, s):
                ordered = False
        out_t.append(t)
        out_p.append(p)
        out_s.append(s)
        out_k.append(k)
        out_e.append(e)

    return CalendarTrace(
        DE_OK, n_events, len(out_t), peak, de_heap_work(n_events), monotone, ordered,
        out_t^, out_p^, out_s^, out_k^, out_e^,
    )


def calendar_order_audit(
    time: List[Float64], priority: List[Int], sequence: List[Int], n: Int
) -> OrderAudit:
    """Check that the first `n` entries are in `de_event_order()`, and say where they are not.

    The point of exporting this separately from `calendar_replay_flat` is that a caller can
    audit a sequence THIS PACKAGE DID NOT PRODUCE — a trace read back from storage, a merge of
    two runs, or the output of another simulator being compared against. A certificate is only
    worth what its weakest checked condition is worth, so this checks all three keys and counts
    the two kinds of tie separately rather than reporting one boolean.

    `n_time_ties` and `n_priority_ties` are diagnostics, not defects: ties on time are normal
    and are exactly what the second and third keys exist to resolve. `n_duplicate_keys` IS a
    defect and is counted apart from them.

    A non-finite time is refused rather than audited: a comparison against a NaN is False in
    both directions, so an audit would report "ordered" for a pair that has no order.

    @capability calendar_order_audit
    complexity: O(n)
    counts:
    - n <= len(time, priority, sequence) [kernel_validated]
    @endcapability
    """
    if n > len(time) or n > len(priority) or n > len(sequence):
        return _audit_refusal(DE_ERR_COUNT)
    if n <= 0:
        return _audit_refusal(DE_ERR_EMPTY)
    if n > DE_MAX_EVENTS:
        return _audit_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if not de_all_finite(time, n):
        return _audit_refusal(DE_ERR_NON_FINITE)

    var ordered = True
    var first = -1
    var dups = 0
    var time_ties = 0
    var pri_ties = 0
    for i in range(1, n):
        var before = de_key_less(
            time[i - 1], priority[i - 1], sequence[i - 1], time[i], priority[i], sequence[i]
        )
        var after = de_key_less(
            time[i], priority[i], sequence[i], time[i - 1], priority[i - 1], sequence[i - 1]
        )
        if not before and not after:
            dups += 1
        if not before:
            if ordered:
                first = i
            ordered = False
        if time[i] == time[i - 1]:
            time_ties += 1
            if priority[i] == priority[i - 1]:
                pri_ties += 1
    return OrderAudit(DE_OK, n, ordered, not ordered, first, dups, time_ties, pri_ties)


def calendar_stress_flat(n_events: Int, distinct_times: Int, n_priorities: Int) -> CalendarTrace:
    """Build `n_events` events that COLLIDE on purpose, then replay them.

    `time = i % distinct_times`, `priority = i % n_priorities`, `kind = entity = i`. With
    `distinct_times` far below `n_events` every timestamp carries many events and every
    tie-break key is exercised, which is the case a calendar gets wrong: a container-order
    tie-break passes a test where all timestamps are distinct and fails here.

    Generated rather than taken as lists so the tie-breaking can be measured at a scale no
    caller would send over the wire, and so the benchmark has a single knob. The expected pop
    order is `(i % distinct_times, i % n_priorities, i)` sorted ascending — computable by hand,
    which is what its suite does.

    `distinct_times` and `n_priorities` are DIVISORS, never subscripts, so a value of zero is
    refused (`DE_ERR_EMPTY`) rather than dividing. Both are bounded by the ceilings the kernel
    tests, `DE_MAX_EVENTS` and `DE_MAX_PRIORITY` in `discrete_event.contract`; neither is the
    length of any parameter, which is why they are declared as dimensions.

    @capability calendar_stress_flat
    complexity: O(n_events log n_events)
    counts:
    - dim n_events [kernel_validated]
    - dim distinct_times [kernel_validated]
    - dim n_priorities [kernel_validated]
    @endcapability
    """
    if n_events <= 0 or distinct_times <= 0 or n_priorities <= 0:
        return _trace_refusal(DE_ERR_EMPTY)
    if n_events > DE_MAX_EVENTS or distinct_times > DE_MAX_EVENTS:
        return _trace_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if n_priorities > DE_MAX_PRIORITY:
        return _trace_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if not de_heap_work_fits(n_events):
        return _trace_refusal(DE_ERR_WORK_BUDGET)

    var h = _EventHeap()
    for i in range(n_events):
        _heap_push(h, Float64(i % distinct_times), i % n_priorities, i, i, i)

    var out_t = List[Float64]()
    var out_p = List[Int]()
    var out_s = List[Int]()
    var out_k = List[Int]()
    var out_e = List[Int]()
    var monotone = True
    var ordered = True
    while _heap_size(h) > 0:
        var t = h.t[0]
        var p = h.pri[0]
        var s = h.seq[0]
        var k = h.kind[0]
        var e = h.ent[0]
        _heap_drop_root(h)
        if len(out_t) > 0:
            var last = len(out_t) - 1
            if t < out_t[last]:
                monotone = False
            if not de_key_less(out_t[last], out_p[last], out_s[last], t, p, s):
                ordered = False
        out_t.append(t)
        out_p.append(p)
        out_s.append(s)
        out_k.append(k)
        out_e.append(e)

    return CalendarTrace(
        DE_OK, n_events, len(out_t), n_events, de_heap_work(n_events), monotone, ordered,
        out_t^, out_p^, out_s^, out_k^, out_e^,
    )
