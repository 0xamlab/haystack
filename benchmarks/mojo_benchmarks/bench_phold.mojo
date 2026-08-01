"""bench_phold.mojo — PHOLD, the standard PDES speed benchmark, on our event calendar.

What PHOLD is, and what this file implements
--------------------------------------------
PHOLD is the canonical parallel-discrete-event-simulation benchmark, reported in the PDES
literature for three decades (ROSS, WARPED, muesik). The model is deliberately trivial so that
the number it produces measures the SIMULATOR and not the model:

  * `n_lps` logical processes, each holding `init_per_lp` initial events;
  * processing one event schedules EXACTLY ONE new event, so the pending-event population is
    invariant for the whole run;
  * the destination is the same LP with probability `1 - p_remote`, and a DIFFERENT,
    uniformly-chosen LP with probability `p_remote`;
  * the new event's timestamp is `now + lookahead + Exponential(exp_mean)`.

The metric is EVENTS PER SECOND, which is implementation-independent and is what every paper in
the field quotes.

Every one of those parameters is a named argument of `phold_run` and every one is printed in the
output, because a "PHOLD" with a different event-generation rule is not PHOLD. Two deviations
from ROSS's `phold.c` are recorded here rather than left for a reader to discover:

  1. ROSS draws its remote destination with `tw_rand_integer(0, ttl_lps - 1)`, uniform over ALL
     LPs including the source, so its effective fraction of events that actually leave the LP is
     `p_remote * (n_lps - 1) / n_lps`. This file draws uniformly over the `n_lps - 1` OTHER LPs,
     so `p_remote` IS the fraction that leaves. The difference is `1/n_lps` — 12.5% at the 8 LPs
     of ROSS's own documentation example, 0.1% at 1024 — and section 1 gates the realised
     fraction against `p_remote` tightly enough that the choice is observable rather than
     assumed.
  2. ROSS runs to a simulated END TIME and reports however many events that took. This file runs
     a FIXED EVENT COUNT and reports the simulated end time it reached. Fixed work is what makes
     the `p_remote` sweep an equal-work comparison — at fixed end time, changing `p_remote`
     changes the event count, and then a rate difference and a workload difference are
     indistinguishable.

Draw consumption matches ROSS exactly: one uniform for the remote decision, a second uniform for
the destination ONLY on the remote branch, and one exponential for the increment. Two draws for a
local event, three for a remote one. That is safe here in a way it is not for a stateful stream
generator: every draw's coordinates are explicit (`dim0` = the global event index, one named
stream per role), so a conditionally-skipped draw shifts nothing.

Where the calendar comes from
-----------------------------
`_EventHeap` and its three helpers are imported from `discrete_event.calendar` — the SAME heap
`discrete_event.resource` runs on, not a copy. That is the whole point of the exercise: a
re-implementation here would measure a benchmark-local heap and report the number as the
product's. The import reaches an underscore-prefixed name on purpose; the underscore keeps a heap
of parallel satellite arrays out of the wire contract, and `resource.mojo` already imports
exactly these four names for exactly this reason.

There is no public push-during-pop driver to use instead. `calendar_replay_flat` and
`calendar_stress_flat` both push all `n` events and then pop all `n`, which cannot express "process
an event, schedule one new event"; they also materialise a five-array trace of every popped event,
so a ns/event figure from either includes 80 bytes/event of allocation. `PholdRun` returns
counters only.

What is GATED, and what is only MEASURED
----------------------------------------
This file follows `bench_discrete_event.mojo`: the hard gates are integer identities and
correctness invariants that give the same verdict at any load, and wall-clock breaches are
ADVISORY. The evidence for that split is in that file's docstring — two runs five minutes apart
on this machine at load ~440, no code change, growth exponent 1.11 then 1.99, the second one
"detecting" a linear scan in a tree whose heap had not been touched.

There is ONE exception, and the task this file answers demands it: the SHAPE gate in section 3 is
a wall-clock gate. Events/sec must not COLLAPSE as the LP count grows, because a calendar that
degrades with LP count has the wrong data structure. It is placed where contention cannot reach
it:

    logarithmic cost predicts   levels(262144)/levels(128) = 19/8    = 2.4x
    MEASURED, quiet-ish machine, K = 5 launches                2.35x - 3.30x
    MEASURED, during a contention spike (load 36 -> 52 mid-run)       4.84x
    worst contention inflation documented on this machine              4.1x
    the two together, worst case                                      ~9.7x
    THE GATE                                                          12.0x
    a sorted-array calendar (O(pending)), same sweep, MEASURED     1447x-2860x

So the gate sits above anything contention has produced here and 120x below the defect it exists
to catch, and both ends of that range are measured rather than predicted. The 4.84x line is the
most useful one: it is a real spike, on a real run, that inflated every absolute rate about 2.5x
and still did not come close to firing the gate. An advisory fires at 4x for
a human to look at. The scratch-copy run is quoted at the bottom of this docstring.

The hard gates, none of which involve a clock:

1. *Event conservation.* Exactly `n_events` events are processed, and the pending population is
   INVARIANT: `heap_min == heap_max == n_lps * init_per_lp` at every step. That is PHOLD's
   defining structural property and a calendar that lost or duplicated an event fails it.
2. *The order held.* Every popped event obeys `de_event_order()` against its predecessor, and
   timestamps never decrease. Computed from the output, not assumed from the algorithm.
3. *The live calendar satisfies the FROZEN min-heap predicate.* `heap.is_min_heap` is called on
   the calendar's own time array at the end of a run. Note what this does and does not prove: a
   fully-sorted array also satisfies it, so this is an independent correctness cross-check of the
   push-during-pop usage against a kernel outside this package — it is not the evidence for
   O(log n), which is section 6's measurement.
4. *The generator is wired correctly, checked statistically.* The realised remote fraction must
   sit inside 5 binomial standard errors of `p_remote`, and the realised mean increment inside 5
   standard errors of `lookahead + exp_mean`. Both are deterministic given the seed, so they are
   machine-independent. The second one catches the rate/mean inversion that
   `rng_exponential(..., rate)` invites: passing 0.9 where 1/0.9 belongs shifts the mean by 23%
   and 5 standard errors is 0.0044.
5. *Every remote event actually left its LP,* and every destination is a legal LP index. This
   checks the `k < src ? k : k + 1` mapping that makes `p_remote` mean what gate 4 measures.
6. *The event stream is reproducible against this file's own history.* Two runs of one config in
   one process produce bit-identical digests; a different seed produces a different digest (which
   is what catches a benchmark that ignores its seed); and two small configs are gated against
   digests RECORDED IN THIS FILE. A simulation benchmark whose event stream changes between runs
   cannot be compared against its own history, so the digest is an FNV-1a fold over the exact
   bits of every popped timestamp and its destination LP. Changing the driver, the parameters or
   the generator legitimately changes these values, and they must then be re-recorded
   deliberately — which is the point.
7. *The declared work charge equals the declared model,* `2 * n_events * de_heap_levels(pending)`,
   and fits `DE_MAX_WORK`.
8. *The two calendar operations produce the same event stream.* Section 9 runs the event loop
   through `_heap_replace_root` and through `_heap_drop_root` + `_heap_push` and requires identical
   digests, identical simulated clocks, identical remote counts and identical populations at every
   size. The faster operation is the default, so this is the gate that stops a speedup from being a
   wrong answer.

Reading the output
------------------
    FAIL       a hard gate broke, or the shape gate did. Deterministic except for the shape gate.
    ADVISORY   a wall-clock threshold was passed. Informational. Check the load average, which is
               printed by the harness that runs this file.
    PASS       that section's gates held.

The last line is `BENCH_GATE phold PASS` or `BENCH_GATE phold FAIL <n>`, and a hard failure also
RAISES so the process exits non-zero — nothing in this repository greps for the `BENCH_GATE`
string, so the exit code is the only signal a caller can act on.

Cold, warm and hot
------------------
Section 1 reports all three at the reference configuration, measured with `perf_counter_ns`
INSIDE the process: cold is the first call in a fresh process, warm the second, hot the minimum
over nine more. Never `mojo run` wall time — that is dominated by compilation (a fifteen-line
probe costs 7.7 s of it, and this file's own build is most of its ~20 s). A cold reading happens
once per process, so K cold readings need K process launches; the machine-parseable
`PHOLD_COLD_NS` line exists for exactly that harness, and K must be stated wherever the number is
quoted.

Section 1 is FIRST among the timed sections on purpose: any earlier call to `phold_run` would pay
the driver's first-call compilation and the cold reading would no longer be cold.

On this machine the three temperatures are barely separable. K = 5 launches, 2026-07-31, Apple
M4 Max (12 performance + 4 efficiency cores, 128 GB, macOS 26.5.2), one-minute load average 23-33
at each launch:

    cold   2.01, 2.35, 2.29, 2.61, 2.90  M events/sec     median 2.35M
    hot    2.39, 2.83, 2.83, 3.24, 3.18  M events/sec     median 2.83M

The two ranges nearly overlap, and the WITHIN-launch spread of the nine hot repetitions was 1.09x,
1.20x, 1.25x, 1.28x and 3.11x. So run-to-run contention on this machine is of the same order as
the cold/hot difference, and the first-call compilation cost amortised over a million events is
close to invisible. On an earlier K = 5 set taken at load 40-130 one launch measured cold FASTER
than the minimum of nine later repetitions; section 1 has an advisory for exactly that, because it
is a contention reading and not a cold-start speedup. No absolute figure from this file should be
quoted to more precision than the hot spread printed beside it.

Demonstrating that the shape gate fails — MEASURED, not asserted
---------------------------------------------------------------
Recorded here because the demonstration is a scratch copy that is not kept in the repository. The
injected defect is a SORTED-ARRAY calendar: insert by linear scan then shift, pop by taking the
front and shifting everything down — the shape of `simulation.schedule_event`, which this package's
calendar exists to replace. It was chosen over an unsorted-list calendar because it is
SEMANTICALLY IDENTICAL to the heap: same total order, same pop sequence, same digest, and an
ascending array satisfies `heap.is_min_heap` trivially. So every correctness gate in this file
still passes on it and only the shape gate can catch it, which is the sharpest possible
demonstration of what the shape gate is for.

Event counts were reduced 512x (reference 4096 events, sweep 2048 per point) so that an
O(pending) calendar terminates; the ratio the gate reads is independent of the event count. Two
runs, 2026-07-31, load average 39:

    [1] PASS   4096 events at 16384 pending: 5,279 events/sec (the heap does 2.4M-3.2M)
    [2] PASS   every fidelity gate held, including BOTH recorded golden digests unchanged —
               which is the point: the defect is invisible to every correctness check in the file
    [3] FAIL   ns/event across the sweep, pending 128 -> 262144:
                   1,662 -> 4,754,561 ns/event      spread 2859.7x
               and on the earlier untrimmed run of the same scratch copy, 2,318 -> 3,354,528
               ns/event, spread 1446.6x
        BENCH_GATE phold FAIL 1
        Unhandled exception caught during execution: bench_phold: 1 gate failure(s)
        exit code 1

Below the 2048x the pending ratio predicts in one run and above it in the other, because the
smallest sizes are dominated by fixed per-event cost rather than by the scan and the largest by
memory traffic. Either way the gate is at 12x, so the margin is two orders of magnitude, and the
gate was restored immediately afterwards — the scratch copy lives only in /tmp.

What this file measured, 2026-07-31, so a later run has something to disagree with
----------------------------------------------------------------------------------
Apple M4 Max, 12 performance + 4 efficiency cores, 128 GB, macOS 26.5.2. One core. Sequential
protocol: no rollback, no GVT, no antimessages. One-minute load average 23-33. K = 5 launches.
Every figure is a LOWER bound — this machine has run at load 400+ today.

    reference config (1024 LPs, 16/LP, 16384 pending, p_remote 0.10, lookahead 0.1, mean 0.90):
        hot 2.39M - 3.24M events/sec, median 2.83M; 1,048,576 events per run
    ROSS-documentation-matched config (8 LPs, 1/LP, 8 pending, p_remote 0.25, lookahead 1.0):
        hot 5.41M - 6.61M events/sec, median 5.99M = 2.30x the documented ROSS 7.0.1 sequential
        2,600,585 events/sec, whose hardware is not stated and whose own config is 87.5% ties
    LP sweep, pending 128 -> 262,144 (2048x), 262,144 events per point:
        4.45M -> 1.67M events/sec; best/worst spread 2.35x - 3.30x against a 2.375x logarithmic
        prediction and a 12x gate
    p_remote 0.10 -> 1.00 at 1024 LPs: 1.06x - 1.18x spread. Flat, which is correct for a
        sequential protocol, and is why this number must never be read as a Time Warp result
    scheduling cost: ns/event = a + b * de_heap_levels(pending), b measured 24.6 - 34.8 ns per
        heap level across five launches; the O(pending) model's coefficient moves 750x - 990x
        across the same sweep and is rejected
    generator: 28.2 - 61.1 ns per 64-bit Philox-4x64-10 word (median 32.5), 11% - 29% of an event
    calendar operation A/B: replace-root is 1.54x - 1.80x faster than pop-then-push at every size,
        with bit-identical event streams
"""
from std.memory import bitcast
from std.time import perf_counter_ns

from heap import is_min_heap

from determinism.counter_rng import philox_word, rng_exponential, rng_uniform
from determinism.streams import stream_id
from discrete_event.calendar import (
    _EventHeap,
    _heap_drop_root,
    _heap_push,
    _heap_replace_root,
    _heap_size,
    de_key_less,
)
from discrete_event.contract import (
    DE_ERR_CAPACITY,
    DE_ERR_DIMENSION_TOO_LARGE,
    DE_ERR_EMPTY,
    DE_ERR_NON_FINITE,
    DE_ERR_RATE_RANGE,
    DE_ERR_WORK_BUDGET,
    DE_MAX_EVENTS,
    DE_MAX_WORK,
    DE_OK,
    de_finite,
    de_heap_levels,
    de_product_fits,
    de_status_name,
)

# An event KIND, not a status code. PHOLD has exactly one kind of event, which is why it measures
# the calendar rather than a model.
comptime PHOLD_EVENT: Int = 0

# Every event carries the same calendar priority, so ties on time fall through to the insertion
# sequence. With continuous exponential increments exact timestamp ties are a measure-zero event,
# which is the NON-degenerate case: ROSS's own documentation example runs with the exponential
# mean set to 0.0, making every increment exactly the lookahead, and reports 699,993 ties out of
# 799,992 events — 87.5%. A tie-heavy integer-timestamp workload is the easiest case any calendar
# ever sees, and no figure from it is comparable to one from this file.
comptime PHOLD_RANK: Int = 0

# FNV-1a, 64-bit. The offset basis and prime, spelled out because the digest is a golden value.
comptime FNV_OFFSET: UInt64 = 14695981039346656037
comptime FNV_PRIME: UInt64 = 1099511628211

# `dim0` occupies bits 32..63 of the Philox counter word `c1`, so any coordinate placed there must
# stay below 2^32. The global event index goes there, which caps a single call at ~4.29e9 events —
# three orders of magnitude above anything `DE_MAX_WORK` permits.
comptime PHOLD_MAX_COORD: Int = 4294967295


# ── the reference configuration ───────────────────────────────────────────────
# Parameter-identical, where a single core can be, to the Sequoia runs in Barnes, Carothers,
# Jefferson and LaPre, "Warp Speed: Executing Time Warp on 1,966,080 Cores", SIGSIM-PADS 2013
# (DOI 10.1145/2486092.2486134): 16 events per LP, 10% remote, lookahead 0.1, exponential mean
# 0.90. Their LP count was 251,658,240 across 1,966,080 cores; ours is 1024 on one core. The
# per-LP configuration is the part that is comparable and it is matched exactly.
comptime REF_LPS: Int = 1024
comptime REF_INIT: Int = 16
comptime REF_P_REMOTE: Float64 = 0.10
comptime REF_LOOKAHEAD: Float64 = 0.1
comptime REF_EXP_MEAN: Float64 = 0.90
comptime REF_SEED: UInt64 = 20260731
comptime REF_EVENTS: Int = 1 << 20

# Golden digests, recorded from this file's own first green run on 2026-07-31 and gated in
# section 1. They pin the EVENT STREAM, not a timing: an FNV-1a fold over the exact bits of every
# popped timestamp and its destination LP. A change to the driver, to the parameters or to
# `determinism.counter_rng` legitimately changes them, and they must then be re-recorded
# deliberately — which is what makes "compared against its own history" a check rather than a
# hope. Two configs so that both the local-only and the mixed paths are pinned.
comptime GOLDEN_A_DIGEST: UInt64 = 10200233210619852612
comptime GOLDEN_B_DIGEST: UInt64 = 15643879954897263383


@fieldwise_init
struct PholdRun(Copyable, Movable):
    """One PHOLD run: counters and invariants only, no per-event arrays, UNLESS `capture_trace`
    was requested.

    Deliberately allocation-free apart from the calendar itself, on the default path.
    `calendar_replay_flat` returns a five-array trace of every popped event, which is the right
    shape for auditing an order and the wrong shape for an event rate: 80 bytes per event of
    `List` growth lands inside the timed region and any ns/event derived from it is allocation
    cost plus calendar cost. That is exactly why PHOLD needed its OWN trace mode rather than
    reusing that driver: `calendar_replay_flat` pushes every event and then pops every event, which
    cannot express "process one event, schedule exactly one new one" — PHOLD's defining loop.
    Nothing here grows per event UNLESS the caller asked for a trace, and the four `trace_*`
    fields are the ONLY per-event state added: at `capture_trace=False` they are constructed empty
    and never appended to, so the counters-only fast path and its published ns/event figures are
    unchanged.

    `setup_ns` and `loop_ns` are measured separately because they answer different questions.
    Priming the calendar with `pending` initial events is O(pending log pending) and happens once;
    the event rate is `n_events / loop_ns` and must not be diluted by it. At `n_events == pending`
    the priming would otherwise be half the measured work.

    Trace fields, populated only when `capture_trace=True`, one entry per PROCESSED event in the
    order it was processed (`trace_event_id[i] == i` always — it is the loop's own `processed`
    index, recorded rather than recomputed, so there is no second source of truth for it):

      * `trace_time[i]`    — the popped event's simulated timestamp (`now` at that iteration).
      * `trace_source[i]`  — the LP the event was popped from (`src`).
      * `trace_dest[i]`    — the LP the rescheduled event was sent to (`dest`); `dest != src` iff
                             the event was one of the run's `n_remote` remote events.
      * `trace_event_id[i]`— the global processed-event index, `0 .. n_events - 1`.
    """

    var status: Int
    var n_lps: Int
    var init_per_lp: Int
    var pending: Int
    var n_events: Int
    var n_remote: Int
    var n_remote_distinct: Int
    var n_bad_dest: Int
    var heap_min: Int
    var heap_max: Int
    var n_draws: Int
    var order_held: Bool
    var time_monotone: Bool
    var heap_valid: Bool
    var start_time: Float64
    var end_time: Float64
    var sum_increment: Float64
    var digest: UInt64
    var work_charged: Int
    var setup_ns: Int
    var loop_ns: Int
    var trace_time: List[Float64]
    var trace_source: List[Int]
    var trace_dest: List[Int]
    var trace_event_id: List[Int]


fn _phold_refusal(code: Int) -> PholdRun:
    """A refusal carries no counters — not zeros that read as a run of length zero. Nor a trace:
    an empty `List`, the same "absent" shape `capture_trace=False` produces on a real run."""
    return PholdRun(
        code, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        False, False, False,
        0.0, 0.0, 0.0,
        0, 0, 0, 0,
        List[Float64](), List[Int](), List[Int](), List[Int](),
    )


fn phold_work_charge(n_events: Int, pending: Int) -> Int:
    """Charged operations for a PHOLD run, or -1 when the charge does not fit `DE_MAX_WORK`.

    PHOLD needs its OWN charge model and cannot borrow `de_heap_work`. That function charges
    `2 * n * de_heap_levels(n)` for pushing and popping `n` entries, which assumes the calendar
    GROWS to `n`. A PHOLD calendar never grows at all: the population is `pending` from the first
    event to the last, and the run processes `n_events` of them, where `n_events` is typically
    orders of magnitude larger. So the depth factor comes from `pending` and the count from
    `n_events`, and they are different numbers.

    Each event costs one pop (sift down at most one depth) and one push (sift up at most one
    depth), hence `2 * n_events * de_heap_levels(pending)`.

    Formed by DIVISION through `de_product_fits`, never by multiplying and comparing: a wrapping
    64-bit multiply is not a bound.
    """
    if n_events <= 0 or pending <= 0:
        return 0
    var levels = de_heap_levels(pending)
    if not de_product_fits(2 * n_events, levels, DE_MAX_WORK):
        return -1
    return 2 * n_events * levels


fn _dest_of(u: Float64, source: Int, n_lps: Int) -> Int:
    """Map a uniform on [0,1) to an LP that is NOT `source`, uniformly over the other `n_lps - 1`.

    `k = floor(u * (n_lps - 1))` indexes the others in order, and `k < source ? k : k + 1` skips
    the source. The clamp guards a `u` that rounds to the top of its range; `rng_uniform` is
    left-closed right-open so it cannot happen, and an index one past the end of an LP range is
    cheaper to prevent than to debug.
    """
    var k = Int(u * Float64(n_lps - 1))
    if k < 0:
        k = 0
    if k > n_lps - 2:
        k = n_lps - 2
    if k < source:
        return k
    return k + 1


@no_inline
fn phold_run(
    n_lps: Int,
    init_per_lp: Int,
    n_events: Int,
    p_remote: Float64,
    lookahead: Float64,
    exp_mean: Float64,
    seed: UInt64,
    replication: UInt64,
    use_replace_root: Bool = True,
    capture_trace: Bool = False,
) -> PholdRun:
    """Run PHOLD for exactly `n_events` events on `discrete_event.calendar`'s heap.

    Parameters, all of which the caller must state and this file prints:

      * `n_lps` — logical processes. Only the destination bookkeeping uses it; there is no
        per-LP state, because PHOLD's point is that the model is nothing.
      * `init_per_lp` — initial events per LP. `pending = n_lps * init_per_lp` is then the
        calendar population for the entire run.
      * `n_events` — events processed. The run stops on this count, not on a simulated end time.
      * `p_remote` — probability that the scheduled event goes to a DIFFERENT LP.
      * `lookahead` — the constant floor added to every timestamp increment.
      * `exp_mean` — mean of the exponential part. `rng_exponential` takes a RATE, so it is
        called with `1 / exp_mean`; the realised mean increment is gated in section 1 precisely
        because that inversion is easy to get backwards and impossible to see in an event rate.
      * `seed`, `replication` — the generator coordinates. Replications are COORDINATES here, as
        everywhere in this tree, never re-seeds.
      * `use_replace_root` — which calendar operation the event loop uses. True calls
        `_heap_replace_root` (one sift); False calls `_heap_drop_root` then `_heap_push` (two sifts
        plus ten `List` resizes). Both paths are kept, and section 9 measures them interleaved and
        HARD-GATES that they produce identical digests and identical simulated clocks, so the
        faster path's correctness is a published measurement rather than a claim in a comment. The
        flag is read once per event into a branch that is perfectly predicted, and the slower arm
        pays the same branch, so the A/B is fair.
      * `capture_trace` — default False, the counters-only fast path this file publishes every
        figure from. True additionally records `(time, source, dest, event_id)` for every
        processed event into the four `trace_*` fields of `PholdRun`. It changes nothing about
        the SIMULATION: the same draws are consumed in the same order either way, so a
        `capture_trace=True` run and a `capture_trace=False` run at the same seed and replication
        must agree on every counter, invariant and digest bit for bit — section 10 gates exactly
        that, then re-derives the counter path's own numbers FROM the trace alone as a second,
        independent check that the two views of one run agree.

    Refusals use `discrete_event`'s status vocabulary rather than inventing a second one, because
    this driver validates the same things its drivers do:

      * `n_lps`, `init_per_lp` or `n_events` below 1 -> `DE_ERR_EMPTY`.
      * `p_remote > 0` with `n_lps < 2` -> `DE_ERR_CAPACITY`. There is no other LP to send to, so
        the request asks for something that does not exist rather than for zero of it.
      * `pending` above `DE_MAX_EVENTS`, or a coordinate above 2^32 -> `DE_ERR_DIMENSION_TOO_LARGE`.
      * `p_remote` outside [0,1], a negative or non-finite `lookahead`, or `exp_mean <= 0` ->
        `DE_ERR_RATE_RANGE`.
      * charge above `DE_MAX_WORK` -> `DE_ERR_WORK_BUDGET`.
      * a timestamp that overflows to non-finite mid-run -> `DE_ERR_NON_FINITE`, discarding the
        whole run. One non-finite time makes every comparison against it False, the strict order
        stops being an order and the heap silently stops being a heap, so there is no salvageable
        prefix.
    """
    if n_lps < 1 or init_per_lp < 1 or n_events < 1:
        return _phold_refusal(DE_ERR_EMPTY)
    if p_remote > 0.0 and n_lps < 2:
        return _phold_refusal(DE_ERR_CAPACITY)
    if not de_product_fits(n_lps, init_per_lp, DE_MAX_EVENTS):
        return _phold_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    var pending = n_lps * init_per_lp
    if pending > PHOLD_MAX_COORD or n_events > PHOLD_MAX_COORD:
        return _phold_refusal(DE_ERR_DIMENSION_TOO_LARGE)
    if p_remote < 0.0 or p_remote > 1.0 or not de_finite(p_remote):
        return _phold_refusal(DE_ERR_RATE_RANGE)
    if lookahead < 0.0 or not de_finite(lookahead):
        return _phold_refusal(DE_ERR_RATE_RANGE)
    if exp_mean <= 0.0 or not de_finite(exp_mean):
        return _phold_refusal(DE_ERR_RATE_RANGE)
    var charge = phold_work_charge(n_events, pending)
    if charge < 0:
        return _phold_refusal(DE_ERR_WORK_BUDGET)

    # Three named streams, one per role, derived by NAME through the frozen `stream_id` hash — an
    # integer picked by hand collides with whoever picked it first and the two streams silently
    # stop being independent with nothing failing. Hoisted out of the loop: `stream_id` hashes a
    # String, and calling it per event would make this a benchmark of FNV-1a.
    var s_remote = UInt64(stream_id("discrete_event.phold.remote"))
    var s_dest = UInt64(stream_id("discrete_event.phold.destination"))
    var s_incr = UInt64(stream_id("discrete_event.phold.increment"))
    var s_init = UInt64(stream_id("discrete_event.phold.initial"))
    var rate = 1.0 / exp_mean

    # ── prime the calendar ────────────────────────────────────────────────────
    # ROSS's `phold_init` schedules every start event to the LP ITSELF at
    # `lookahead + Exponential(mean)`, and this matches that. A separate stream keeps the priming
    # draws from ever sharing coordinates with the run's increment draws.
    var t_setup = perf_counter_ns()
    var cal = _EventHeap()
    var seq = 0
    var draws = 0
    for lp in range(n_lps):
        for j in range(init_per_lp):
            var t0 = lookahead + rng_exponential(
                seed, 0, replication, UInt64(lp * init_per_lp + j), 0, s_init, 0, rate
            )
            draws += 1
            if not de_finite(t0):
                return _phold_refusal(DE_ERR_NON_FINITE)
            _heap_push(cal, t0, PHOLD_RANK, seq, PHOLD_EVENT, lp)
            seq += 1
    var setup_ns = Int(perf_counter_ns() - t_setup)

    # ── the event loop ────────────────────────────────────────────────────────
    var processed = 0
    var n_remote = 0
    var n_remote_distinct = 0
    var n_bad_dest = 0
    var heap_min = pending
    var heap_max = pending
    var monotone = True
    var ordered = True
    var have_last = False
    var last_t: Float64 = 0.0
    var last_p = 0
    var last_s = 0
    var start_time: Float64 = 0.0
    var sum_increment: Float64 = 0.0
    var digest = FNV_OFFSET
    var non_finite = False

    # Trace arrays stay empty and unallocated-into on the default path: `capture_trace` is read
    # once per event below, into a branch that predicts perfectly once warm, and nothing is
    # appended to these four `List`s unless it is True. That is what keeps the counters-only path
    # allocation-free apart from the calendar itself, exactly as `PholdRun`'s docstring states.
    var trace_time = List[Float64]()
    var trace_source = List[Int]()
    var trace_dest = List[Int]()
    var trace_event_id = List[Int]()

    var t_loop = perf_counter_ns()
    while processed < n_events:
        var size_before = _heap_size(cal)
        if size_before < heap_min:
            heap_min = size_before
        if size_before > heap_max:
            heap_max = size_before

        var now = cal.t[0]
        var pri = cal.pri[0]
        var sq = cal.seq[0]
        var src = cal.ent[0]
        if not use_replace_root:
            _heap_drop_root(cal)

        if have_last:
            if now < last_t:
                monotone = False
            if not de_key_less(last_t, last_p, last_s, now, pri, sq):
                ordered = False
        else:
            start_time = now
            have_last = True
        last_t = now
        last_p = pri
        last_s = sq

        digest = (digest ^ bitcast[DType.uint64](now)) * FNV_PRIME
        digest = (digest ^ UInt64(src)) * FNV_PRIME

        var e = UInt64(processed)
        processed += 1

        # Draw consumption matches ROSS's `phold_event_handler`: the remote coin always, the
        # destination only when the coin says remote, the increment always.
        var dest = src
        if rng_uniform(seed, 0, replication, e, 0, s_remote, 0) < p_remote:
            n_remote += 1
            dest = _dest_of(
                rng_uniform(seed, 0, replication, e, 0, s_dest, 0), src, n_lps
            )
            draws += 2
            if dest != src:
                n_remote_distinct += 1
        else:
            draws += 1
        if dest < 0 or dest >= n_lps:
            n_bad_dest += 1

        if capture_trace:
            trace_time.append(now)
            trace_source.append(src)
            trace_dest.append(dest)
            trace_event_id.append(Int(e))

        var dt = lookahead + rng_exponential(
            seed, 0, replication, e, 0, s_incr, 0, rate
        )
        draws += 1
        sum_increment += dt
        var when = now + dt
        if not de_finite(when):
            non_finite = True
            break
        if use_replace_root:
            _heap_replace_root(cal, when, PHOLD_RANK, seq, PHOLD_EVENT, dest)
        else:
            _heap_push(cal, when, PHOLD_RANK, seq, PHOLD_EVENT, dest)
        seq += 1
    var loop_ns = Int(perf_counter_ns() - t_loop)

    if non_finite:
        return _phold_refusal(DE_ERR_NON_FINITE)

    # The frozen min-heap predicate, on the live calendar's own time array. Independent of this
    # package: a lexicographic (time, priority, sequence) parent that precedes its children also
    # has parent_time <= child_time, so a valid calendar must satisfy `heap.is_min_heap`.
    var valid = is_min_heap(cal.t)

    return PholdRun(
        DE_OK, n_lps, init_per_lp, pending, processed,
        n_remote, n_remote_distinct, n_bad_dest,
        heap_min, heap_max, draws,
        ordered, monotone, valid,
        start_time, last_t, sum_increment, digest, charge,
        setup_ns, loop_ns,
        trace_time^, trace_source^, trace_dest^, trace_event_id^,
    )


# ── helpers ───────────────────────────────────────────────────────────────────


fn _rate(n_events: Int, ns: Int) -> Float64:
    """Events per second from an event count and a nanosecond duration."""
    if ns <= 0:
        return 0.0
    return Float64(n_events) * 1.0e9 / Float64(ns)


fn _ratio(lo: Float64, hi: Float64) -> Float64:
    if lo <= 0.0:
        return 0.0
    return hi / lo


fn _sqrt_newton(x: Float64) -> Float64:
    """Square root by Newton iteration, so this file needs nothing from `std.math` but `log`.

    Used only to size the statistical bands in section 1, where a relative error far below 1e-12
    is irrelevant to a 5-standard-error gate.
    """
    if x <= 0.0:
        return 0.0
    var g = x
    if g < 1.0:
        g = 1.0
    for _ in range(60):
        g = 0.5 * (g + x / g)
    return g


fn _abs(x: Float64) -> Float64:
    return x if x >= 0.0 else -x


@no_inline
fn _phold_once(
    n_lps: Int, init_per_lp: Int, n_events: Int, p_remote: Float64
) -> List[Float64]:
    """ONE timed run, returning [loop_ns, status, n_events, pending, setup_ns, invariants_held].

    One run per call rather than a min-over-reps loop, so that the CALLER controls the order in
    which sizes are measured. Every sweep in this file is INTERLEAVED — an outer pass over
    repetitions, an inner pass over sizes — instead of finishing all repetitions of one size
    before starting the next. That directly targets the failure documented in
    `bench_discrete_event.mojo`: a load spike part-way through a size-major sweep lands entirely on
    the sizes measured after it, and a genuinely flat per-unit cost then measures as steeply
    growing. Interleaved, a spike lands on every size, and the minimum over passes is a minimum
    over the SAME set of contention windows for all of them. It does not make wall clock safe to
    gate on; it removes the one artefact that reliably fakes a shape.

    Wrapped in `@no_inline` and called from loops whose bounds are runtime values read out of a
    `List`, for the reason `bench_discrete_event.mojo` records: `for _ in range(3)` around a
    driver call has a compile-time bound, the driver is instantiated once per unrolled iteration,
    and with one such loop per size per section that file STOPPED BUILDING — `mojo build` ran past
    ten minutes on eight CPU-minutes without ever running the program.

    Every invariant section 2 gates is re-checked here at every size and folded into slot 5, so a
    sweep point that ran fast by being wrong cannot report a rate.
    """
    var r = phold_run(
        n_lps, init_per_lp, n_events, p_remote, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
    )
    var ok = 1.0 if (
        r.status == DE_OK
        and r.order_held
        and r.time_monotone
        and r.heap_valid
        and r.heap_min == r.pending
        and r.heap_max == r.pending
        and r.n_events == n_events
        and r.n_bad_dest == 0
        and r.n_remote_distinct == r.n_remote
    ) else 0.0
    var out = List[Float64]()
    out.append(Float64(r.loop_ns))
    out.append(Float64(r.status))
    out.append(Float64(r.n_events))
    out.append(Float64(r.pending))
    out.append(Float64(r.setup_ns))
    out.append(ok)
    return out^


# ── sections ──────────────────────────────────────────────────────────────────


@no_inline
fn _bench_cold_warm_hot(mut cold_out: List[Float64], mut adv: List[Int]) -> Int:
    """Section 1 — the headline rate, and the FIRST timed call in the process.

    Any earlier `phold_run` would pay the driver's first-call compilation and the cold reading
    would not be cold. Cold is one reading per process by definition; the harness launches this
    file K times and reports K of them.
    """
    print("[1] Event rate at the reference configuration: cold, warm, hot")
    print(
        "     n_lps", REF_LPS, " init/LP", REF_INIT, " pending", REF_LPS * REF_INIT,
        " p_remote", REF_P_REMOTE, " lookahead", REF_LOOKAHEAD,
        " exp_mean", REF_EXP_MEAN,
    )
    print("     events", REF_EVENTS, " seed", REF_SEED, " increment = 0.1 + Exp(mean 0.9)")
    var cfg = List[Int]()
    cfg.append(9)
    var reps = cfg[0]

    var cold = phold_run(
        REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
    )
    var warm = phold_run(
        REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
    )
    var best = 0
    var worst = 0
    var have = False
    var setup = 0
    for _ in range(reps):
        var r = phold_run(
            REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN,
            REF_SEED, 0
        )
        setup = r.setup_ns
        if not have or r.loop_ns < best:
            best = r.loop_ns
        if not have or r.loop_ns > worst:
            worst = r.loop_ns
        have = True

    if cold.status != DE_OK or warm.status != DE_OK:
        print("  FAIL the reference configuration was refused:", de_status_name(cold.status))
        return 1
    print("            events/sec        ns/event      ms")
    print(
        "     cold ", _rate(cold.n_events, cold.loop_ns),
        Float64(cold.loop_ns) / Float64(cold.n_events), Float64(cold.loop_ns) / 1.0e6,
    )
    print(
        "     warm ", _rate(warm.n_events, warm.loop_ns),
        Float64(warm.loop_ns) / Float64(warm.n_events), Float64(warm.loop_ns) / 1.0e6,
    )
    print(
        "     hot  ", _rate(cold.n_events, best),
        Float64(best) / Float64(cold.n_events), Float64(best) / 1.0e6,
        " (min of", reps, "after cold+warm)",
    )
    print(
        "     calendar priming (", cold.pending, "initial events ) =",
        Float64(setup) / 1.0e6, "ms, excluded from every rate above",
    )
    print("     draws consumed", cold.n_draws, " =", Float64(cold.n_draws) / Float64(cold.n_events), "per event")
    print("     simulated clock reached", cold.end_time, " from", cold.start_time)
    # Machine-parseable, for the K-launch cold harness.
    print("PHOLD_COLD_NS", cold.loop_ns, "EVENTS", cold.n_events, "PENDING", cold.pending)
    print("PHOLD_HOT_NS", best, "EVENTS", cold.n_events)
    cold_out.append(Float64(cold.loop_ns))
    cold_out.append(Float64(best))
    cold_out.append(Float64(cold.n_events))
    var cw = _ratio(Float64(best), Float64(cold.loop_ns))
    var spread = _ratio(Float64(best), Float64(worst))
    print("     cold/hot =", cw, "x   warm/hot =", _ratio(Float64(best), Float64(warm.loop_ns)), "x")
    print(
        "     the", reps, "hot repetitions themselves spanned", spread,
        "x (slowest/fastest) — read every absolute figure in this file against that",
    )
    if cw > 3.0:
        print("  ADVISORY cold exceeded hot by", cw, "x — first-call compilation plus contention")
        adv[0] += 1
    if cw < 1.0:
        print(
            "  ADVISORY cold measured FASTER than the minimum of", reps, "later repetitions (",
            cw, "x ). That is not a cold-start speedup; it means run-to-run contention on this",
        )
        print(
            "           machine exceeds the first-call compilation cost amortised over",
            REF_EVENTS, "events, so cold/warm/hot separation is below the noise floor here.",
        )
        adv[0] += 1
    if spread > 1.5:
        print(
            "  ADVISORY the hot repetitions alone spanned", spread,
            "x — no single absolute rate from this run is reproducible to better than that",
        )
        adv[0] += 1
    print("  PASS the reference configuration ran and reported a rate at all three temperatures")
    return 0


@no_inline
fn _bench_fidelity(mut adv: List[Int]) -> Int:
    """Section 2 — is this actually PHOLD, and is the generator wired correctly?

    Every gate here is an integer identity, a bit-exact digest or a statistical band that is a
    deterministic function of the seed. None of them can be moved by the machine's load.
    """
    print("[2] Fidelity and determinism — hard gates only, no clock")
    var r = phold_run(
        REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
    )
    if r.status != DE_OK:
        print("  FAIL refused:", de_status_name(r.status))
        return 1

    var fails = 0

    # 1. Event conservation and the invariant population.
    print(
        "     events processed", r.n_events, " pending population min", r.heap_min,
        "max", r.heap_max, " expected", r.pending,
    )
    if r.n_events != REF_EVENTS or r.heap_min != r.pending or r.heap_max != r.pending:
        print(
            "  FAIL the pending-event population was not invariant — PHOLD schedules exactly one",
            "event per event processed, so the calendar must never grow or shrink",
        )
        fails += 1

    # 2 and 3. The order, and the frozen heap predicate.
    print(
        "     total order held", r.order_held, " time non-decreasing", r.time_monotone,
        " frozen heap.is_min_heap on the live calendar", r.heap_valid,
    )
    if not r.order_held or not r.time_monotone or not r.heap_valid:
        print("  FAIL the calendar did not maintain a totally-ordered, time-monotone pop order")
        fails += 1

    # 4. The generator, checked statistically. Both bands are 5 standard errors, and both are
    # deterministic given the seed.
    var frac = Float64(r.n_remote) / Float64(r.n_events)
    var se_p = _sqrt_newton(REF_P_REMOTE * (1.0 - REF_P_REMOTE) / Float64(r.n_events))
    print(
        "     remote fraction realised", frac, " target", REF_P_REMOTE,
        " |dev| =", _abs(frac - REF_P_REMOTE), " 5 s.e. =", 5.0 * se_p,
    )
    if _abs(frac - REF_P_REMOTE) > 5.0 * se_p:
        print("  FAIL the realised remote fraction is outside 5 binomial standard errors")
        fails += 1
    var mean_incr = r.sum_increment / Float64(r.n_events)
    var target_incr = REF_LOOKAHEAD + REF_EXP_MEAN
    # sd of the increment is the sd of its exponential part, which is its mean.
    var se_i = REF_EXP_MEAN / _sqrt_newton(Float64(r.n_events))
    print(
        "     mean increment realised", mean_incr, " target", target_incr,
        " |dev| =", _abs(mean_incr - target_incr), " 5 s.e. =", 5.0 * se_i,
    )
    if _abs(mean_incr - target_incr) > 5.0 * se_i:
        print(
            "  FAIL the realised mean timestamp increment is outside 5 standard errors — the",
            "likeliest cause is a rate/mean inversion in the exponential draw",
        )
        fails += 1

    # 5. The destination mapping.
    print(
        "     remote events that actually left their LP", r.n_remote_distinct, "of", r.n_remote,
        " destinations out of range", r.n_bad_dest,
    )
    if r.n_remote_distinct != r.n_remote or r.n_bad_dest != 0:
        print("  FAIL a remote event stayed on its own LP, or a destination was not a legal LP")
        fails += 1

    # 6. Reproducibility, in three parts.
    var again = phold_run(
        REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
    )
    var other = phold_run(
        REF_LPS, REF_INIT, REF_EVENTS, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN,
        REF_SEED + 1, 0
    )
    print("     digest", r.digest, " re-run", again.digest, " different seed", other.digest)
    if r.digest != again.digest or r.end_time != again.end_time:
        print("  FAIL two runs of one configuration did not produce the same event stream")
        fails += 1
    if r.digest == other.digest:
        print("  FAIL a different seed produced the same event stream — the seed is not wired in")
        fails += 1

    # Two small configs pinned against digests recorded in this file.
    var ga = phold_run(64, 4, 4096, 0.0, 0.1, 0.9, UInt64(20260731), 0)
    var gb = phold_run(64, 4, 4096, 0.25, 0.1, 0.9, UInt64(20260731), 0)
    print("     golden A (64 LPs, 4/LP, 4096 events, p_remote 0.00) digest", ga.digest)
    print("     golden B (64 LPs, 4/LP, 4096 events, p_remote 0.25) digest", gb.digest)
    if ga.digest != GOLDEN_A_DIGEST or gb.digest != GOLDEN_B_DIGEST:
        print(
            "  FAIL the event stream no longer matches the digests recorded in this file. That is",
            "not automatically a defect — a deliberate change to the driver, the parameters or",
            "the generator changes it — but it must be re-recorded on purpose, never widened.",
        )
        fails += 1
    if ga.digest == gb.digest:
        print("  FAIL p_remote 0.00 and 0.25 produced the same event stream")
        fails += 1

    # 7. The charge model.
    var declared = phold_work_charge(r.n_events, r.pending)
    print(
        "     work charged", r.work_charged, " declared 2 * n_events * levels(pending) =",
        2 * r.n_events * de_heap_levels(r.pending), " DE_MAX_WORK", DE_MAX_WORK,
    )
    if r.work_charged != declared or declared != 2 * r.n_events * de_heap_levels(r.pending):
        print("  FAIL the reported work charge does not equal the declared model")
        fails += 1
    if phold_work_charge(1024, 16) != 2 * 1024 * 5:
        print("  FAIL the hand-checked charge anchor no longer holds")
        fails += 1

    if fails > 0:
        return fails
    print(
        "  PASS event conservation, invariant population, total order, the frozen heap predicate,",
        "the remote fraction and mean increment inside 5 s.e., the destination mapping, bit-exact",
        "reproducibility against two recorded digests, and the charge identity",
    )
    return 0


@no_inline
fn _bench_lp_sweep(mut pend: List[Float64], mut nsper: List[Float64], mut adv: List[Int]) -> Int:
    """Section 3 — events/sec against LP count. THE SHAPE GATE.

    `init_per_lp` is held at the reference 16 and the event count is held fixed, so the only thing
    that changes across the sweep is the pending-event population `pending = 16 * n_lps`, which is
    exactly the quantity a calendar's cost is supposed to depend on logarithmically.

    Equal work at every point: every row processes the same number of events. A sweep that held
    the simulated end time fixed instead would change the event count with the LP count and a rate
    difference could not be separated from a workload difference.

    INTERLEAVED, for the reason given on `_phold_once`: one untimed warm-up pass over every size,
    then `reps` timed passes that visit all seven sizes in order, keeping a running minimum per
    size. A load spike therefore lands on all seven rather than on the tail of the sweep.
    """
    print("[3] Events/sec against LP count — pending population = 16 x n_lps  [SHAPE GATE]")
    var cfg = List[Int]()
    cfg.append(3)
    var reps = cfg[0]
    var events = List[Int]()
    events.append(1 << 18)
    var n_events = events[0]
    var sizes = List[Int]()
    sizes.append(8)
    sizes.append(32)
    sizes.append(128)
    sizes.append(512)
    sizes.append(2048)
    sizes.append(8192)
    sizes.append(16384)
    print(
        "     ", n_events, "events per point,", reps,
        "interleaved timed passes over all", len(sizes), "sizes, minimum per size",
    )
    print("     n_lps    pending  levels    events/sec     ns/event    prime ms")
    var ok = True
    var best_ns = List[Float64]()
    var prime_ns = List[Float64]()
    var pend_of = List[Float64]()
    for i in range(len(sizes)):
        var w = _phold_once(sizes[i], REF_INIT, n_events, REF_P_REMOTE)
        if w[1] != Float64(DE_OK) or w[5] != 1.0:
            ok = False
        best_ns.append(-1.0)
        prime_ns.append(w[4])
        pend_of.append(w[3])
    for _ in range(reps):
        for i in range(len(sizes)):
            var m = _phold_once(sizes[i], REF_INIT, n_events, REF_P_REMOTE)
            if m[1] != Float64(DE_OK) or m[2] != Float64(n_events) or m[5] != 1.0:
                ok = False
            if best_ns[i] < 0.0 or m[0] < best_ns[i]:
                best_ns[i] = m[0]
            prime_ns[i] = m[4]
            pend_of[i] = m[3]
    var rates = List[Float64]()
    for i in range(len(sizes)):
        var per = best_ns[i] / Float64(n_events)
        rates.append(_rate(n_events, Int(best_ns[i])))
        pend.append(pend_of[i])
        nsper.append(per)
        print(
            "     ", sizes[i], Int(pend_of[i]), de_heap_levels(Int(pend_of[i])),
            _rate(n_events, Int(best_ns[i])), per, prime_ns[i] / 1.0e6,
        )
    if not ok:
        print("  FAIL a sweep point failed an invariant — see section 2's gates for which")
        return 1

    var best = rates[0]
    var worst = rates[0]
    for i in range(len(rates)):
        if rates[i] > best:
            best = rates[i]
        if rates[i] < worst:
            worst = rates[i]
    var collapse = _ratio(worst, best)
    var pend_ratio = pend[len(pend) - 1] / pend[0]
    var level_ratio = Float64(de_heap_levels(Int(pend[len(pend) - 1]))) / Float64(
        de_heap_levels(Int(pend[0]))
    )
    print(
        "     pending grew", pend_ratio, "x   heap depth grew", level_ratio,
        "x   best/worst events-per-sec spread =", collapse, "x",
    )
    print(
        "     an O(pending) calendar would spread by about", pend_ratio,
        "x here; the gate is 12x and a logarithmic calendar predicts", level_ratio, "x",
    )
    if collapse > 12.0:
        print(
            "  FAIL events/sec COLLAPSED as the LP count grew:", collapse,
            "x spread across a", pend_ratio, "x growth in the pending population.",
        )
        print(
            "       12x is above anything contention has produced on this machine (the worst",
            "documented inflation is 4.05x on a 2.4x logarithmic baseline = 9.7x) and 170x below",
        )
        print(
            "       the ~2048x an O(pending) calendar gives on this sweep, so this is a data",
            "structure finding, not a load artefact. Optimise the calendar, not the gate.",
        )
        return 1
    if collapse > 4.0:
        print("  ADVISORY events/sec spread", collapse, "x exceeds the 4x advisory band")
        print("           not a gate failure — check the load average before believing it")
        adv[0] += 1
    print(
        "  PASS events/sec did not collapse: a", pend_ratio,
        "x growth in the pending population cost", collapse, "x in rate, inside the 12x gate",
    )
    return 0


@no_inline
fn _bench_remote_sweep(mut adv: List[Int]) -> Int:
    """Section 4 — events/sec against `p_remote`, the shape of Warp Speed's Figure 3.

    That paper's CCNI Blue Gene/Q figure reports peak event rate falling monotonically as the
    remote fraction rises: roughly 8e9 at 10%, 5e9 at 25%, 3e9 at 50%, 2e9 at 100% events/sec on
    32,768 cores. On ONE core there is no message passing, no rollback and no GVT, so `p_remote`
    changes almost nothing about the work: it costs one extra uniform draw per remote event and
    nothing else. A flat line here is therefore the CORRECT result and is the evidence that our
    figure is a sequential-protocol figure that must never be compared to a Time Warp one.

    Interleaved over the four remote fractions for the reason given on `_phold_once`.
    """
    print("[4] Events/sec against p_remote at the reference 1024 LPs (Warp Speed Figure 3 shape)")
    var cfg = List[Int]()
    cfg.append(3)
    var reps = cfg[0]
    var events = List[Int]()
    events.append(1 << 18)
    var n_events = events[0]
    var ps = List[Float64]()
    ps.append(0.10)
    ps.append(0.25)
    ps.append(0.50)
    ps.append(1.00)
    print(
        "     ", n_events, "events per point,", reps, "interleaved timed passes over all",
        len(ps), "remote fractions",
    )
    print("     p_remote   events/sec     ns/event    remote frac    draws/event")
    var ok = True
    var best_ns = List[Float64]()
    for i in range(len(ps)):
        var w = _phold_once(REF_LPS, REF_INIT, n_events, ps[i])
        if w[1] != Float64(DE_OK) or w[5] != 1.0:
            ok = False
        best_ns.append(-1.0)
    for _ in range(reps):
        for i in range(len(ps)):
            var m = _phold_once(REF_LPS, REF_INIT, n_events, ps[i])
            if m[1] != Float64(DE_OK) or m[5] != 1.0:
                ok = False
            if best_ns[i] < 0.0 or m[0] < best_ns[i]:
                best_ns[i] = m[0]
    var rates = List[Float64]()
    for i in range(len(ps)):
        var p = ps[i]
        var r = phold_run(
            REF_LPS, REF_INIT, n_events, p, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0
        )
        var frac = Float64(r.n_remote) / Float64(r.n_events)
        rates.append(_rate(n_events, Int(best_ns[i])))
        print(
            "     ", p, _rate(n_events, Int(best_ns[i])), best_ns[i] / Float64(n_events),
            frac, Float64(r.n_draws) / Float64(r.n_events),
        )
        var se = _sqrt_newton(p * (1.0 - p) / Float64(n_events))
        if p < 1.0 and _abs(frac - p) > 5.0 * se:
            print("  FAIL realised remote fraction", frac, "is outside 5 s.e. of", p)
            ok = False
        if p == 1.0 and r.n_remote != r.n_events:
            print("  FAIL p_remote = 1 did not send every event to a different LP")
            ok = False
    if not ok:
        return 1
    var lo = rates[0]
    var hi = rates[0]
    for i in range(len(rates)):
        if rates[i] < lo:
            lo = rates[i]
        if rates[i] > hi:
            hi = rates[i]
    var spread = _ratio(lo, hi)
    print("     rate spread across a 10x change in remote fraction =", spread, "x")
    if spread > 2.0:
        print("  ADVISORY p_remote changed the sequential event rate by", spread, "x")
        print("           expected to be near 1x — one extra uniform draw per remote event")
        adv[0] += 1
    print(
        "  PASS the realised remote fraction matched p_remote at every point, and p_remote = 1",
        "sent every single event to a different LP",
    )
    return 0


@no_inline
fn _bench_pending_control(mut adv: List[Int]) -> Int:
    """Section 5 — is the cost a function of the PENDING COUNT, or of the LP count?

    Two configurations reach the same pending population by different routes: 1024 LPs holding 16
    events each, and 16,384 LPs holding 1 event each. If the calendar is what costs, the two must
    measure the same ns/event. If they differ, something scales with the LP count — which in this
    driver would have to be the destination arithmetic, since there is no per-LP state at all.

    This is the control that makes section 6's log-fit meaningful: without it, a rise in ns/event
    across section 3's sweep could be the LP count rather than the calendar depth.

    Interleaved A/B/A/B rather than all-of-A-then-all-of-B, which is the only comparison shape the
    precedent in `bench_discrete_event.mojo` leaves defensible on this machine: the two arms must
    be measured inside the same contention window.
    """
    print("[5] Same pending population, two routes — does the LP count cost anything?")
    var cfg = List[Int]()
    cfg.append(3)
    var reps = cfg[0]
    var events = List[Int]()
    events.append(1 << 18)
    var n_events = events[0]
    var wa = _phold_once(1024, 16, n_events, REF_P_REMOTE)
    var wb = _phold_once(16384, 1, n_events, REF_P_REMOTE)
    var a_ns: Float64 = -1.0
    var b_ns: Float64 = -1.0
    var ok = wa[5] == 1.0 and wb[5] == 1.0
    for _ in range(reps):
        var a = _phold_once(1024, 16, n_events, REF_P_REMOTE)
        var b = _phold_once(16384, 1, n_events, REF_P_REMOTE)
        if a[1] != Float64(DE_OK) or b[1] != Float64(DE_OK) or a[5] != 1.0 or b[5] != 1.0:
            ok = False
        if a[3] != b[3]:
            ok = False
        if a_ns < 0.0 or a[0] < a_ns:
            a_ns = a[0]
        if b_ns < 0.0 or b[0] < b_ns:
            b_ns = b[0]
    if not ok:
        print("  FAIL a control configuration was refused, failed an invariant, or the two")
        print("       configurations did not reach the same pending population")
        return 1
    print("     ", n_events, "events per point,", reps, "interleaved A/B passes")
    print("     n_lps  init/LP   pending    events/sec    ns/event")
    print("      1024      16 ", Int(wa[3]), _rate(n_events, Int(a_ns)), a_ns / Float64(n_events))
    print("     16384       1 ", Int(wb[3]), _rate(n_events, Int(b_ns)), b_ns / Float64(n_events))
    var d = _ratio(a_ns / Float64(n_events), b_ns / Float64(n_events))
    if d < 1.0:
        d = 1.0 / d
    print("     ns/event ratio =", d, "x  (1.0 would mean the cost is the pending count alone)")
    if d > 1.5:
        print("  ADVISORY the two routes to the same pending population differ by", d, "x")
        print("           wall clock; a 16x difference in LP count changes only the destination")
        print("           arithmetic, so a large gap here is worth reading the loop for")
        adv[0] += 1
    print("  PASS both routes reached the same pending population and both held every invariant")
    return 0


@no_inline
fn _bench_log_fit(pend: List[Float64], nsper: List[Float64], mut adv: List[Int]) -> Int:
    """Section 6 — IS event scheduling O(log n) in the pending count? Measured, not assumed.

    Reuses section 3's measurements rather than re-timing them, so the two sections cannot
    disagree about the same numbers.

    Two competing models are fitted to the same data and printed side by side:

        logarithmic   ns/event = a + b * de_heap_levels(pending)      b constant
        linear        ns/event = c * pending                          c constant

    Whichever model is right, its coefficient is constant across the sweep, so the DIAGNOSTIC is
    the spread of each coefficient rather than a fitted quality score. A heap makes `b` roughly
    constant and `c` fall by three orders of magnitude; an O(pending) calendar does the reverse.
    Both are printed and the reader can see which one held.

    `b` is also reported as an incremental per-level cost between consecutive sweep points, which
    is where the two large sizes' memory-bandwidth inflation shows up as a rising `b` rather than
    hiding inside a single fitted number. This is a wall-clock measurement and is ADVISORY: the
    documented failure mode on this machine is exactly a flat per-unit cost measuring as steeply
    growing when the working set exceeds cache.
    """
    print("[6] Is event scheduling O(log pending)? Two models on section 3's own measurements")
    if len(pend) < 4 or len(nsper) != len(pend):
        print("  FAIL section 3 did not report a measurement at every size")
        return 1
    print("     pending  levels   ns/event   ns per level   ns/event/pending   working set KB")
    var n = len(pend)
    var sx: Float64 = 0.0
    var sy: Float64 = 0.0
    var sxx: Float64 = 0.0
    var sxy: Float64 = 0.0
    var c_lo: Float64 = 0.0
    var c_hi: Float64 = 0.0
    for i in range(n):
        var lv = Float64(de_heap_levels(Int(pend[i])))
        var y = nsper[i]
        sx += lv
        sy += y
        sxx += lv * lv
        sxy += lv * y
        var c = y / pend[i]
        if i == 0:
            c_lo = c
            c_hi = c
        if c < c_lo:
            c_lo = c
        if c > c_hi:
            c_hi = c
        # Five parallel 8-byte arrays per calendar entry.
        var kb = pend[i] * 40.0 / 1024.0
        print("     ", Int(pend[i]), Int(lv), y, y / lv, c, kb)
    var denom = Float64(n) * sxx - sx * sx
    var slope: Float64 = 0.0
    var intercept: Float64 = 0.0
    if denom != 0.0:
        slope = (Float64(n) * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / Float64(n)
    print(
        "     least squares on levels:  ns/event =", intercept, "+", slope, "* levels(pending)",
    )
    print("     incremental ns per added heap level, consecutive sweep points:")
    var inc_lo: Float64 = 0.0
    var inc_hi: Float64 = 0.0
    var have = False
    for i in range(1, n):
        var dl = Float64(de_heap_levels(Int(pend[i])) - de_heap_levels(Int(pend[i - 1])))
        if dl <= 0.0:
            continue
        var inc = (nsper[i] - nsper[i - 1]) / dl
        if not have:
            inc_lo = inc
            inc_hi = inc
            have = True
        if inc < inc_lo:
            inc_lo = inc
        if inc > inc_hi:
            inc_hi = inc
        print(
            "       ", Int(pend[i - 1]), "->", Int(pend[i]), " +", dl, "levels  =",
            inc, "ns/level",
        )
    var lin_spread = _ratio(c_lo, c_hi)
    print(
        "     linear model coefficient ns/event/pending spanned", c_lo, "to", c_hi,
        " =", lin_spread, "x  (a constant here would mean O(pending))",
    )
    print(
        "     VERDICT the logarithmic model is the one whose coefficient stays bounded; the linear",
        "model's coefficient moved", lin_spread, "x across the sweep, so cost is not O(pending).",
    )
    if have and inc_lo < 0.0:
        print(
            "  ADVISORY at least one consecutive pair got FASTER as the heap got deeper (",
            inc_lo, "ns/level ) — that is measurement noise, not a speedup",
        )
        adv[0] += 1
    if lin_spread < 10.0:
        print(
            "  FAIL the per-pending-entry cost stayed within", lin_spread,
            "x across the sweep, which is the signature of an O(pending) calendar",
        )
        return 1
    print(
        "  PASS the O(pending) model is rejected by its own coefficient moving", lin_spread,
        "x, and the fitted per-level cost is", slope, "ns",
    )
    return 0


@no_inline
fn _bench_generator_cost(nsper: List[Float64], mut adv: List[Int]) -> Int:
    """Section 7 — how much of an event is the GENERATOR rather than the calendar?

    This is the caveat that has to travel with any comparison of our event rate to a published
    one. `determinism.counter_rng.philox_word` is Philox-4x64 with TEN rounds — the safety-margin
    variant Salmon et al. recommend in the Random123 paper (SC11) — with the 64x64 high product
    written out as four 32-bit multiplies. ROSS draws from L'Ecuyer's combined multiple-recursive
    `RngStream`, which is a few multiplies and modulo reductions per draw. Those are not the same
    generator and a per-event figure that hides the difference is not a comparison.

    Measured directly: the frozen kernel's own throughput, and the share of a PHOLD event it
    accounts for at the reference configuration's 2.1 draws per event.

    The accumulator is PRINTED so the loop cannot be dead-code-eliminated, and the coordinates
    walk `dim0` exactly as the event loop does so the measurement is the same access pattern and
    not a hoisted constant.
    """
    print("[7] Generator share — Philox-4x64-10 is not the generator ROSS measures with")
    var cfg = List[Int]()
    cfg.append(1 << 22)
    var n_draws = cfg[0]
    var s = UInt64(stream_id("discrete_event.phold.increment"))
    var acc: UInt64 = 0
    # Untimed warm-up, for the reason given on `_phold_once`.
    for i in range(4096):
        acc = acc ^ philox_word(REF_SEED, 0, 0, UInt64(i), 0, s, 0)
    var t0 = perf_counter_ns()
    for i in range(n_draws):
        acc = acc ^ philox_word(REF_SEED, 0, 0, UInt64(i), 0, s, 0)
    var dt = Int(perf_counter_ns() - t0)
    var ns_per_draw = Float64(dt) / Float64(n_draws)
    print("     draws", n_draws, " accumulator", acc, " (printed so the loop cannot be elided)")
    print(
        "     ", ns_per_draw, "ns per 64-bit word =", 1.0e9 / ns_per_draw / 1.0e6,
        "M words/sec, one full 10-round block per word",
    )
    if len(nsper) < 4:
        print("  FAIL section 3 did not report a per-event cost to compare against")
        return 1
    # The reference p_remote is 0.10, so draws per event = 2 + 0.10 = 2.1.
    var draws_per_event = 2.0 + REF_P_REMOTE
    var gen_ns = draws_per_event * ns_per_draw
    # Section 3's sweep does not contain the reference configuration's 1024 LPs; it brackets it
    # with 512 LPs (8192 pending) and 2048 LPs (32768 pending). The 32768 row is used and NAMED,
    # rather than quietly labelled "the reference", because a share is a ratio and the denominator
    # has to be the row it was actually taken from.
    var ref_idx = len(nsper) - 3
    var ref_pending = 32768
    var ref_ns = nsper[ref_idx]
    print(
        "     an event at", ref_pending, "pending draws", draws_per_event, "words =", gen_ns,
        "ns of generator against", ref_ns, "ns measured per event at that same size",
    )
    var share = 0.0
    if ref_ns > 0.0:
        share = 100.0 * gen_ns / ref_ns
    print("     generator share of one event at", ref_pending, "pending =", share, "%")
    print(
        "     so the calendar's own share is about", ref_ns - gen_ns,
        "ns/event, and an event rate quoted against ROSS is bounded by BOTH.",
    )
    if share > 50.0:
        print(
            "  ADVISORY more than half of a PHOLD event is the generator, so this file's event",
            "rate is a generator measurement as much as a calendar measurement. The frozen",
            "kernel returns ONE word per call while Philox-4x64 computes FOUR per block, so a",
            "`philox_block4` in determinism/ would cut this share directly. Frozen tree:",
            "reported as a finding, not changed here.",
        )
        adv[0] += 1
    print("  PASS the generator's own throughput was measured on the same coordinates")
    return 0


@no_inline
fn _bench_published_anchor(mut adv: List[Int]) -> Int:
    """Section 8 — the published figures this rate may and may not be compared against.

    Printed into the log rather than left in a report, because the single easiest way to make a
    PDES event rate dishonest is to quote it next to a number measured on different hardware, a
    different core count or a different synchronisation protocol.

    ANCHOR 1, sequential, and the only single-core figure located. ROSS project documentation,
    "Running the Simulator", https://ross-org.github.io/setup/running-sim.html — ROSS 7.0.1,
    `./phold --synch=1` (sequential protocol, 1 PE), 799,992 net events in 0.3076 s =
    2,600,585.1 events/sec. Three caveats travel with it and none of them are optional:
      (a) the CPU model, core count and clock are NOT STATED anywhere on that page;
      (b) it is project documentation, not a peer-reviewed measurement;
      (c) the configuration is DEGENERATE — `Mean 0.000000`, so every timestamp increment is
          exactly the lookahead 1.0, every timestamp is an integer, and the same output block
          reports 699,993 event ties out of 799,992 events (87.5%). A tie-heavy integer-timestamp
          workload is the easiest case any calendar ever sees.
    This section runs the closest configuration this file will run: ROSS's 8 LPs, 1 start event
    per LP, 25% remote and lookahead 1.0, matched exactly, with the exponential mean at 0.9
    instead of 0.0. That one deliberate difference is what makes it a real exponential PHOLD, and
    it makes our point strictly HARDER than theirs, not easier.

    ANCHOR 2, parallel and peer-reviewed, quoted only to say what it is not comparable to. Barnes,
    Carothers, Jefferson, LaPre, "Warp Speed: Executing Time Warp on 1,966,080 Cores",
    SIGSIM-PADS 2013, DOI 10.1145/2486092.2486134: 504 billion events/sec on 1,966,080 cores of
    LLNL Sequoia (IBM Blue Gene/Q, PowerPC A2, 16 cores/node), 32,984,968,283,642 net events in
    65.4 s, 251,658,240 LPs, 16 events/LP, 10% remote, lookahead 0.1, exponential mean 0.90.
    Dividing that out gives 256,348 events/sec/core — and that per-core figure is NOT a peer for
    ours either: it carries Time Warp's rollback, GVT and antimessage overhead that a sequential
    protocol never pays, on a 1.6 GHz core. It is a floor, not a comparison. The reference
    configuration in this file matches that paper's per-LP parameters exactly.
    """
    print("[8] The published anchors, and what may be compared to what")
    var cfg = List[Int]()
    cfg.append(7)
    var reps = cfg[0]
    var events = List[Int]()
    events.append(1 << 20)
    var n_events = events[0]
    # ROSS's documented sequential config: 8 LPs, 1 start event each, 25% remote, lookahead 1.0.
    # Exponential mean 0.9 instead of their 0.0 — see the docstring; theirs is 87.5% ties.
    var w = phold_run(8, 1, n_events, 0.25, 1.0, 0.9, REF_SEED, 0)
    if w.status != DE_OK:
        print("  FAIL the ROSS-matched configuration was refused:", de_status_name(w.status))
        return 1
    var best = 0
    var have = False
    for _ in range(reps):
        var r = phold_run(8, 1, n_events, 0.25, 1.0, 0.9, REF_SEED, 0)
        if r.status != DE_OK or r.n_events != n_events:
            print("  FAIL the ROSS-matched configuration did not complete")
            return 1
        if not have or r.loop_ns < best:
            best = r.loop_ns
            have = True
    var ours = _rate(n_events, best)
    print(
        "     ROSS-matched config: 8 LPs, 1 start event/LP, p_remote 0.25, lookahead 1.0,",
        "exponential mean 0.9 (theirs is 0.0 = 87.5% ties)",
    )
    print("       ours, hot, min of", reps, "at", n_events, "events =", ours, "events/sec")
    print("       ROSS 7.0.1 --synch=1 documented                  = 2600585.1 events/sec")
    print(
        "       ratio ours/theirs =", ours / 2600585.1,
        "  their hardware is NOT STATED; ours is one core of an Apple M4 Max under load",
    )
    print(
        "     Warp Speed (SIGSIM-PADS 2013) 5.04e11 events/sec on 1,966,080 Blue Gene/Q cores",
        "= 256348 events/sec/core, WITH Time Warp rollback/GVT overhead. Not a peer of a",
    )
    print(
        "       sequential single-core figure in either direction — quoted so that nobody",
        "divides it and calls the quotient a comparison.",
    )
    if ours < 2600585.1:
        print(
            "  FINDING our sequential PHOLD rate is BELOW the documented ROSS sequential figure",
            "by", 2600585.1 / ours, "x on this configuration. Reported here rather than in a",
        )
        print(
            "          footnote. It is a code target, not a number to bury: section 7 attributes",
            "only", 11, "% of an event to the generator, so the calendar is where it lives.",
        )
        adv[0] += 1
    else:
        print("  NOTE our sequential rate is above the documented ROSS sequential figure here.")
    print(
        "  PASS both anchors printed with their hardware, core count and protocol, and our",
        "closest-matched configuration measured beside them",
    )
    return 0


@no_inline
fn _bench_calendar_operation(mut adv: List[Int]) -> Int:
    """Section 9 — the two calendar operations, interleaved, with correctness gated not assumed.

    `_heap_replace_root` was added to `discrete_event.calendar` because of the measurement in this
    section. It performs a pop and a push as ONE sift for a caller that has already read slot 0 —
    the discrete-event fast path — against `_heap_drop_root` followed by `_heap_push`, which is two
    sifts plus five `List.pop`s and five `List.append`s.

    A faster calendar operation that changed the event stream would be a wrong answer that looked
    like a speedup, so the HARD gate here is not the timing at all: at every size the two paths
    must produce the SAME DIGEST, the same simulated end time, the same remote count and the same
    pending population. The digest is an FNV-1a fold over the exact bits of every popped timestamp
    and its destination, so identical digests mean identical event streams, event for event.

    Interleaved A/B/A/B for the reason given on `_phold_once`: the two arms have to be measured
    inside the same contention window or the ratio is a load reading.

    This is what "optimise the code, never the benchmark" looks like when it is written down: the
    number the file reports at the top is the fast path's, the slow path stays in the file, and the
    ratio between them is published every run so a regression in either is visible.
    """
    print("[9] Calendar operation A/B — replace-root vs pop-then-push, same heap, same seed")
    var cfg = List[Int]()
    cfg.append(3)
    var reps = cfg[0]
    var events = List[Int]()
    events.append(1 << 18)
    var n_events = events[0]
    var sizes = List[Int]()
    sizes.append(8)
    sizes.append(1024)
    sizes.append(16384)
    print(
        "     ", n_events, "events per point,", reps,
        "interleaved A/B passes, minimum per arm",
    )
    print("     n_lps   pending   pop+push ns/ev   replace ns/ev   speedup   identical stream?")
    var fails = 0
    for i in range(len(sizes)):
        var n = sizes[i]
        var wa = phold_run(
            n, REF_INIT, 4096, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0, False
        )
        var wb = phold_run(
            n, REF_INIT, 4096, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0, True
        )
        var identical = wa.digest == wb.digest and wa.end_time == wb.end_time
        var a_ns: Float64 = -1.0
        var b_ns: Float64 = -1.0
        for _ in range(reps):
            var a = phold_run(
                n, REF_INIT, n_events, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0,
                False
            )
            var b = phold_run(
                n, REF_INIT, n_events, REF_P_REMOTE, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, 0,
                True
            )
            if a.status != DE_OK or b.status != DE_OK:
                fails += 1
            if a.digest != b.digest or a.end_time != b.end_time:
                identical = False
            if a.n_remote != b.n_remote or a.pending != b.pending or a.n_events != b.n_events:
                identical = False
            if not b.order_held or not b.time_monotone or not b.heap_valid:
                identical = False
            if a_ns < 0.0 or Float64(a.loop_ns) < a_ns:
                a_ns = Float64(a.loop_ns)
            if b_ns < 0.0 or Float64(b.loop_ns) < b_ns:
                b_ns = Float64(b.loop_ns)
        var pa = a_ns / Float64(n_events)
        var pb = b_ns / Float64(n_events)
        print(
            "     ", n, n * REF_INIT, pa, pb, _ratio(pb, pa), "yes" if identical else "NO",
        )
        if not identical:
            fails += 1
    if fails > 0:
        print(
            "  FAIL the two calendar operations did not produce the same event stream. The faster",
            "one is then a wrong answer that looks like a speedup, and must not be the default.",
        )
        return fails
    print(
        "  PASS both operations produced bit-identical event streams at every size — same digest,",
        "same simulated clock, same remote count — and the replace-root path is the default",
    )
    return 0


@no_inline
fn _bench_trace_mode(mut adv: List[Int]) -> Int:
    """Section 10 — `capture_trace`: the opt-in event trace, and its two proofs.

    Prior finding: this driver returned counters and invariants only, with no way to see WHICH
    events produced them — the wrong shape for validating a future PHOLD-vs-ROSS or PHOLD-vs-any-
    other-simulator comparison event by event. `phold_run(..., capture_trace=True)` now also fills
    `PholdRun.trace_time/trace_source/trace_dest/trace_event_id`, one entry per processed event,
    default False everywhere else in this file so every gate above this section is unaffected.

    Two proofs, not one, because "it runs" is not "it is correct":

    (a) BIT-IDENTICAL AGGREGATES. The same config and seed, once with `capture_trace=False` and
        once `True`, must agree on every counter, invariant and the digest — recording a trace is
        additional bookkeeping, not a different simulation. Only the trace arrays differ in
        length, from 0 to `n_events`.
    (b) THE TRACE ALONE REPRODUCES THE COUNTERS. `n_remote_distinct`, `n_bad_dest`,
        `time_monotone` and the digest itself are each re-derived purely from
        `(trace_time, trace_source, trace_dest, trace_event_id)` — the SAME FNV-1a fold the loop
        runs inline, run again here over the recorded arrays — and must equal the loop's own
        counters. That is the actual "trace reproduces the aggregates" consistency check: if the
        trace ever silently dropped or reordered an event, this would be the gate that caught it,
        because the counters come from the live loop and the re-derivation comes only from what
        was recorded.

    Plus a small hand-checkable trace: 3 LPs, 1 initial event each, 6 processed events, every
    event forced remote so every row is visibly a cross-LP hop, printed row by row.
    """
    print("[10] Trace mode — per-event capture, opt-in, and its two proofs")
    var fails = 0

    # (a) same config and seed, counters-only vs traced.
    var n_lps = 16
    var init_per_lp = 4
    var n_events = 2000
    var p_remote = 0.3
    var rep: UInt64 = 7

    var counters_only = phold_run(
        n_lps, init_per_lp, n_events, p_remote, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, rep,
        True, False,
    )
    var traced = phold_run(
        n_lps, init_per_lp, n_events, p_remote, REF_LOOKAHEAD, REF_EXP_MEAN, REF_SEED, rep,
        True, True,
    )

    var agree = counters_only.status == traced.status
    agree = agree and counters_only.pending == traced.pending
    agree = agree and counters_only.n_events == traced.n_events
    agree = agree and counters_only.n_remote == traced.n_remote
    agree = agree and counters_only.n_remote_distinct == traced.n_remote_distinct
    agree = agree and counters_only.n_bad_dest == traced.n_bad_dest
    agree = agree and counters_only.heap_min == traced.heap_min
    agree = agree and counters_only.heap_max == traced.heap_max
    agree = agree and counters_only.n_draws == traced.n_draws
    agree = agree and counters_only.order_held == traced.order_held
    agree = agree and counters_only.time_monotone == traced.time_monotone
    agree = agree and counters_only.heap_valid == traced.heap_valid
    agree = agree and counters_only.start_time == traced.start_time
    agree = agree and counters_only.end_time == traced.end_time
    agree = agree and counters_only.sum_increment == traced.sum_increment
    agree = agree and counters_only.digest == traced.digest
    agree = agree and counters_only.work_charged == traced.work_charged
    print(
        "     counters-only vs traced, same seed/replication: digest", counters_only.digest,
        "vs", traced.digest, " n_remote", counters_only.n_remote, "vs", traced.n_remote,
    )
    if agree and len(counters_only.trace_time) == 0 and len(traced.trace_time) == n_events:
        print(
            "  PASS capturing a trace changed nothing about the simulated result — every shared",
            "counter, invariant and the digest are bit-identical — and only the traced run grew",
            "the four trace arrays, to exactly n_events entries",
        )
    else:
        fails += 1
        print(
            "  FAIL trace capture changed the simulated result, or grew an array on the wrong",
            "arm:", agree, len(counters_only.trace_time), len(traced.trace_time),
        )

    # (b) derive the same aggregates from the trace alone.
    var d2 = FNV_OFFSET
    var remote_from_trace = 0
    var bad_from_trace = 0
    var mono_from_trace = True
    var ids_sequential = True
    for i in range(len(traced.trace_time)):
        d2 = (d2 ^ bitcast[DType.uint64](traced.trace_time[i])) * FNV_PRIME
        d2 = (d2 ^ UInt64(traced.trace_source[i])) * FNV_PRIME
        if traced.trace_dest[i] != traced.trace_source[i]:
            remote_from_trace += 1
        if traced.trace_dest[i] < 0 or traced.trace_dest[i] >= n_lps:
            bad_from_trace += 1
        if i > 0 and traced.trace_time[i] < traced.trace_time[i - 1]:
            mono_from_trace = False
        if traced.trace_event_id[i] != i:
            ids_sequential = False
    var start_from_trace = -1.0
    var end_from_trace = -1.0
    if len(traced.trace_time) > 0:
        start_from_trace = traced.trace_time[0]
        end_from_trace = traced.trace_time[len(traced.trace_time) - 1]

    var derived_ok = d2 == traced.digest
    derived_ok = derived_ok and remote_from_trace == traced.n_remote_distinct
    derived_ok = derived_ok and bad_from_trace == traced.n_bad_dest
    derived_ok = derived_ok and mono_from_trace == traced.time_monotone
    derived_ok = derived_ok and ids_sequential
    derived_ok = derived_ok and start_from_trace == traced.start_time
    derived_ok = derived_ok and end_from_trace == traced.end_time
    print(
        "     from the trace alone: digest", d2, " remote-by-dest!=src", remote_from_trace,
        " bad-dest", bad_from_trace, " time monotone", mono_from_trace, " ids sequential",
        ids_sequential,
    )
    if derived_ok:
        print(
            "  PASS every aggregate re-derived FROM the trace — the digest fold, the remote",
            "count, the bad-destination count, time monotonicity and the 0..n-1 event ids —",
            "matches the counter the live loop kept, for the same run",
        )
    else:
        fails += 1
        print(
            "  FAIL an aggregate derived from the trace did not match the counter the loop kept:",
            d2 == traced.digest, remote_from_trace == traced.n_remote_distinct,
            bad_from_trace == traced.n_bad_dest, mono_from_trace == traced.time_monotone,
        )

    # (c) a small, hand-checkable trace: 3 LPs, one initial event each, 6 processed events, every
    # event forced remote so every row's destination is visibly a different LP from its source.
    var small = phold_run(3, 1, 6, 1.0, 0.1, 1.0, REF_SEED, 0, True, True)
    print("     small trace: 3 LPs, 1 event/LP, 6 processed events, p_remote = 1.0")
    print("       event_id  time                    src  dest")
    var small_ok = small.status == DE_OK and len(small.trace_time) == 6
    for i in range(len(small.trace_time)):
        print(
            "      ", small.trace_event_id[i], " ", small.trace_time[i], " ",
            small.trace_source[i], " ", small.trace_dest[i],
        )
        small_ok = small_ok and small.trace_event_id[i] == i
        small_ok = small_ok and small.trace_source[i] >= 0 and small.trace_source[i] < 3
        small_ok = small_ok and small.trace_dest[i] >= 0 and small.trace_dest[i] < 3
        small_ok = small_ok and small.trace_dest[i] != small.trace_source[i]
        if i > 0:
            small_ok = small_ok and small.trace_time[i] >= small.trace_time[i - 1]
    if small_ok:
        print(
            "  PASS six rows, every destination a legal LP different from its source (p_remote",
            "= 1.0 forces that), timestamps non-decreasing, event ids exactly 0..5 in order",
        )
    else:
        fails += 1
        print("  FAIL the small hand-checkable trace violated a structural invariant")

    if fails > 0:
        return fails
    return 0


fn main() raises:
    print("\n=== bench_phold: PHOLD, the standard PDES benchmark, on discrete_event.calendar ===")
    print("Metric: EVENTS PER SECOND, sequential protocol, one core, no rollback and no GVT.")
    print("HARD gates are integer identities and bit-exact digests, with ONE wall-clock exception")
    print("— the section 3 shape gate, placed at 12x where contention reaches 9.7x and the defect")
    print("it catches reaches 2048x. See the module docstring.\n")
    var failures = 0
    var adv = List[Int]()
    adv.append(0)
    var cold_out = List[Float64]()
    failures += _bench_cold_warm_hot(cold_out, adv)
    print("")
    failures += _bench_fidelity(adv)
    print("")
    var pend = List[Float64]()
    var nsper = List[Float64]()
    failures += _bench_lp_sweep(pend, nsper, adv)
    print("")
    failures += _bench_remote_sweep(adv)
    print("")
    failures += _bench_pending_control(adv)
    print("")
    failures += _bench_log_fit(pend, nsper, adv)
    print("")
    failures += _bench_generator_cost(nsper, adv)
    print("")
    failures += _bench_published_anchor(adv)
    print("")
    failures += _bench_calendar_operation(adv)
    print("")
    failures += _bench_trace_mode(adv)
    print("")
    if adv[0] > 0:
        print(
            "NOTE", adv[0], "wall-clock advisory breach(es). Not gate failures. On a quiet machine",
            "these are worth investigating; under contention they are expected.",
        )
    print(
        "CONTEXT REQUIRED: a Mojo process cannot read the system load average, and every absolute",
        "rate above is a LOWER bound that depends on it. Capture `uptime` immediately before and",
    )
    print(
        "         after this run and quote it beside any figure taken from it. The cold reading is",
        "one per process: K cold readings need K launches, and K must be stated.",
    )
    if failures == 0:
        print("BENCH_GATE phold PASS")
    else:
        print("BENCH_GATE phold FAIL " + String(failures))
        raise Error("bench_phold: " + String(failures) + " gate failure(s)")
