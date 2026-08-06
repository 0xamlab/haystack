"""test_query_aggregate_late.mojo — the late-materialized radix engine.

Hand-written. `query.aggregate_late` removes the radix payload round-trip: it
never scatters the key (the FNV hash of a single key's eight normalized bytes is
injective, so the hash IS the identity), never stores a validity mask, and fuses
the counting pass away so the source columns are read exactly once. Everything
that could go wrong with that is a correctness claim, so every block below is an
EXACT comparison, not a tolerance.

What each block protects, in order:

  * THE INJECTIVITY the whole design rests on: distinct normalized key bits
    must produce distinct `fnv_fold` hashes. If this ever stopped holding, two
    different keys would silently merge into one group. Checked over the exact
    adversarial set the plane cares about (-0.0 vs +0.0 vs NaN payloads vs
    infinities) plus a large generated sweep.
  * FUSED == SERIAL, bit for bit, order included. The radix layout folds each
    group's rows in ascending global row order, so the engine owes bit-equality
    to the one-worker fold — not merely tolerance. Compared on keys, values,
    presence AND counts, by BIT PATTERN, because `NaN != NaN` and
    `-0.0 == 0.0` would let a float comparison pass a path that lost a NaN
    payload or a zero's sign.
  * THE NaN POLICY, inherited rather than restated: a NaN value counts, poisons
    sum/mean, and contributes to NO extremum; a group whose values are ALL NaN
    still reports an extremum (the canonical quiet NaN) with presence true; a
    NaN KEY is in-domain and all NaN keys form ONE group. This is the #459
    defect's blast radius, so it is checked against the serial fold and against
    the shipped radix engine independently.
  * THE APPLICABILITY TABLE. `fused_late_applicable` must be true for exactly
    the shapes this engine may claim and false everywhere else — width != 1
    (the injectivity proof stops at a fixed-length fold), any null, too few
    rows, a malformed request, a route the shipped planner sends to CODED or
    BANDED (stealing those would be a routing regression dressed as an
    optimization), and a footprint larger than the engine being replaced.
    Every refusal must still ANSWER, identically, by delegation.
  * THE OVERFLOW REFUSAL. Segment capacity is sized from a probe of the batch
    HEAD; a heavy key hiding in the TAIL makes that estimate too small. The
    engine must notice (the occupancy test runs before every store, because an
    out-of-range store in Mojo is an uncatchable process kill), refuse the whole
    call, and return the shipped engine's exact answer. Constructed here so the
    path is actually taken, not merely present.
  * THE SKEW MEASUREMENT and THE BYTE MODEL: `fused_partition_peak` must see a
    heavy key as a heavy partition, the capacity must grow with it, and the
    fused arena must price smaller than the payload it replaces on the real H2O
    shapes.
  * CLUSTERED and REVERSE-CLUSTERED key layouts, an ODD worker count, and a
    worker count above the row count — the shapes that leave (worker,
    partition) segments empty or ragged.

Data comes from a fixed-seed LCG in this file, so a failure reproduces.
"""
from std.memory import bitcast

from columnar.array import Float64Array, float64_from_list, float64_with_nulls
from columnar.batch import RecordBatch, schema_of
from columnar.hash_index import FNV_OFFSET_BASIS, fnv_fold, normalize_bits
from numeric.contract import (
    AGG_AVG,
    AGG_COUNT,
    AGG_MAX,
    AGG_MIN,
    AGG_STD,
    AGG_SUM,
    AGG_VAR,
)
from query.aggregate import (
    ManyGroupedResult,
    group_by_many,
    group_by_many_parallel,
    group_by_many_radix,
)
from query.aggregate_late import (
    fused_late_applicable,
    fused_partition_peak,
    fused_scratch_bytes,
    fused_scratch_bytes_for,
    fused_segment_capacity,
    fused_segment_capacity_for,
    group_by_many_late,
    group_by_many_radix_fused,
    shipped_scratch_bytes,
)

comptime ROWS: Int = 200_000
comptime WORKERS: Int = 8
comptime KEYS: Int = 40_000
"""Distinct keys. Must exceed `RADIX_MIN_GROUPS` (16384) or `plan_many_route`
sends the batch to BANDED and the engine correctly refuses it — which would make
every comparison below vacuous."""


def _bits(x: Float64) -> UInt64:
    return bitcast[DType.uint64](x)


def _lcg(mut state: UInt64) -> UInt64:
    state = state * 6364136223846793005 + 1442695040888963407
    return state


def _ints(var xs: List[Int]) -> List[Int]:
    return xs^


def _one(v: Int) -> List[Int]:
    var out = List[Int]()
    out.append(v)
    return out^


def _identical(
    mut failed: Int, label: String, a: ManyGroupedResult, b: ManyGroupedResult, n_aggs: Int
) -> Bool:
    """Bit-for-bit on shape, order, keys, values, presence and counts."""
    if a.n_groups() != b.n_groups():
        failed += 1
        print(
            "  ❌ [" + label + "] n_groups " + String(a.n_groups())
            + " != " + String(b.n_groups())
        )
        return False
    for g in range(a.n_groups()):
        var ka = a.key_at(g)
        var kb = b.key_at(g)
        if len(ka) != len(kb):
            failed += 1
            print("  ❌ [" + label + "] key width differs at group " + String(g))
            return False
        for c in range(len(ka)):
            if _bits(ka[c]) != _bits(kb[c]):
                failed += 1
                print(
                    "  ❌ [" + label + "] key BITS differ at group " + String(g)
                    + ": " + String(ka[c]) + " vs " + String(kb[c])
                )
                return False
        for j in range(n_aggs):
            if a.present_at(g, j) != b.present_at(g, j):
                failed += 1
                print(
                    "  ❌ [" + label + "] presence differs at group " + String(g)
                    + " agg " + String(j)
                )
                return False
            if _bits(a.value_at(g, j)) != _bits(b.value_at(g, j)):
                failed += 1
                print(
                    "  ❌ [" + label + "] value BITS differ at group " + String(g)
                    + " agg " + String(j) + ": " + String(a.value_at(g, j))
                    + " vs " + String(b.value_at(g, j))
                )
                return False
            if _bits(a.count_at(g, j)) != _bits(b.count_at(g, j)):
                failed += 1
                print(
                    "  ❌ [" + label + "] count differs at group " + String(g)
                    + " agg " + String(j)
                )
                return False
    return True


def _cmp(
    mut passed: Int,
    mut failed: Int,
    label: String,
    batch: RecordBatch,
    kc: List[Int],
    vc: List[Int],
    ops: List[Int],
    workers: Int,
    expect_applicable: Bool,
):
    """The full comparison battery for one batch/request.

    Holds on EVERY batch, applicable or not:
      fused == radix  — applicable: this engine; refused: it IS the radix call.
      fused == serial — the bit-equal-to-one-worker promise.
      late  == routed — `group_by_many_late` substitutes only where the planner
                        would have run radix, and this engine is bit-identical
                        to radix, so the routed answer cannot move a bit.
    """
    var n_aggs = len(vc)
    var applicable = fused_late_applicable(batch, kc, vc, ops, workers)
    if applicable != expect_applicable:
        failed += 1
        print(
            "  ❌ [" + label + "] applicable=" + String(applicable)
            + " want " + String(expect_applicable)
        )
    else:
        passed += 1
    var fused = group_by_many_radix_fused(batch, kc, vc, ops, workers)
    var radix = group_by_many_radix(batch, kc, vc, ops, workers)
    var serial = group_by_many_parallel(batch, kc, vc, ops, 1)
    var routed = group_by_many(batch, kc, vc, ops)
    var late = group_by_many_late(batch, kc, vc, ops)
    if _identical(failed, label + " fused==radix", fused, radix, n_aggs):
        passed += 1
    if _identical(failed, label + " fused==serial", fused, serial, n_aggs):
        passed += 1
    if _identical(failed, label + " late==routed", late, routed, n_aggs):
        passed += 1


def main() raises:
    var passed = 0
    var failed = 0
    print("=== query.aggregate_late — late-materialized radix ===")

    # ── 1. the injectivity the design rests on ───────────────────────────────
    var probes = List[Float64]()
    probes.append(0.0)
    probes.append(-0.0)
    probes.append(1.0)
    probes.append(-1.0)
    probes.append(Float64(1.0) / Float64(0.0))
    probes.append(Float64(-1.0) / Float64(0.0))
    probes.append(Float64(0.0) / Float64(0.0))
    probes.append(-(Float64(0.0) / Float64(0.0)))
    probes.append(5e-324)
    probes.append(1.7976931348623157e308)
    var st: UInt64 = 0x243F6A8885A308D3
    for _ in range(4000):
        probes.append(bitcast[DType.float64](_lcg(st)))
    # distinct NORMALIZED bits must give distinct hashes; equal normalized bits
    # (the -0.0/+0.0 and NaN-payload collapses) must give equal hashes.
    var inj_ok = True
    for i in range(len(probes)):
        var bi = normalize_bits(probes[i])
        var hi = fnv_fold(FNV_OFFSET_BASIS, bi)
        for j in range(i + 1, len(probes)):
            var bj = normalize_bits(probes[j])
            var hj = fnv_fold(FNV_OFFSET_BASIS, bj)
            if (bi == bj) != (hi == hj):
                inj_ok = False
                print(
                    "  ❌ [injectivity] bits equal=" + String(bi == bj)
                    + " but hash equal=" + String(hi == hj)
                )
                break
        if not inj_ok:
            break
    if inj_ok:
        passed += 1
        print(
            "  ✅ hash equality == normalized-key equality over "
            + String(len(probes)) + " keys (the hash may replace the key)"
        )
    else:
        failed += 1

    # ── 1b. a PINNED pair whose hashes agree in the low 32 bits and in the top
    #       RADIX_BITS — same partition, so a narrowed identity would merge them.
    #
    # Found by exhausting 8e6 random finite doubles (seed 20260801) for a pair
    # matching on bits 0..31 and 60..63 of the FNV hash:
    #   0x3c4903670dd45a26 -> 0x0f6c047b05eeb7ad
    #   0x9484baaa807a58ca -> 0x016c101305eeb7ad
    # The 64-bit hashes DIFFER, so the engine must keep them apart. It exists
    # because narrowing the scattered identity to 32 bits is the obvious next
    # "optimization" here, and a uniformly random 40k-key fixture will not
    # collide often enough to notice: the first version of this suite passed
    # with the identity truncated to 32 bits.
    var col_a = bitcast[DType.float64](UInt64(0x3C4903670DD45A26))
    var col_b = bitcast[DType.float64](UInt64(0x9484BAAA807A58CA))
    var xk = List[Float64](capacity=ROWS)
    var xv = List[Float64](capacity=ROWS)
    var s1: UInt64 = 0xBE5466CF34E90C6C
    for i in range(ROWS):
        var m = i % 97
        if m == 0:
            xk.append(col_a)
        elif m == 1:
            xk.append(col_b)
        else:
            xk.append(Float64(Int(_lcg(s1) % UInt64(KEYS))))
        xv.append(Float64(i % 691) - 345.0)
    var xnames = List[String]()
    xnames.append("k")
    xnames.append("v")
    var xcols = List[Float64Array]()
    xcols.append(float64_from_list(xk^))
    xcols.append(float64_from_list(xv^))
    var xbatch = RecordBatch(schema_of(xnames^), xcols^, ROWS)
    var xkc = _one(0)
    var xvc = _one(1)
    var xop = _one(AGG_SUM)
    _cmp(passed, failed, "hash-collision-pair", xbatch, xkc, xvc, xop, WORKERS, True)
    var xres = group_by_many_radix_fused(xbatch, xkc, xvc, xop, WORKERS)
    var saw_a = False
    var saw_b = False
    for g in range(xres.n_groups()):
        var kb2 = _bits(xres.key_at(g)[0])
        if kb2 == UInt64(0x3C4903670DD45A26):
            saw_a = True
        if kb2 == UInt64(0x9484BAAA807A58CA):
            saw_b = True
    if saw_a and saw_b:
        passed += 1
        print(
            "  \u2705 the low-32-colliding, same-partition key pair stays TWO groups"
            " (the scattered identity is the full 64-bit hash)"
        )
    else:
        failed += 1
        print(
            "  \u274c a low-32-bit hash collision merged two distinct keys:"
            " saw_a=" + String(saw_a) + " saw_b=" + String(saw_b)
        )

    # ── 2. the byte model and the skew measurement ───────────────────────────
    var fb = fused_scratch_bytes(10_000_000, 2, 16)
    var sb = shipped_scratch_bytes(10_000_000, 1, 2)
    if fb < sb:
        passed += 1
        print(
            "  ✅ q3 shape: fused arena " + String(fb // 1048576)
            + " MiB < shipped payload " + String(sb // 1048576) + " MiB"
        )
    else:
        failed += 1
        print("  ❌ q3 shape: fused arena is not smaller than the shipped payload")
    var fb5 = fused_scratch_bytes(10_000_000, 3, 16)
    var sb5 = shipped_scratch_bytes(10_000_000, 1, 3)
    if fb5 < sb5:
        passed += 1
        print(
            "  ✅ q5 shape: fused arena " + String(fb5 // 1048576)
            + " MiB < shipped payload " + String(sb5 // 1048576) + " MiB"
        )
    else:
        failed += 1
        print("  ❌ q5 shape: fused arena is not smaller than the shipped payload")
    # capacity must GROW with measured skew, and never shrink below the uniform
    # binomial bound.
    var uni = fused_segment_capacity(10_000_000, 16)
    var skewed = fused_segment_capacity_for(10_000_000, 16, 40000, 65536)
    var unskewed = fused_segment_capacity_for(10_000_000, 16, 0, 65536)
    if skewed > uni and unskewed == uni:
        passed += 1
        print(
            "  ✅ capacity tracks skew: uniform=" + String(uni)
            + "  peak-40000/65536=" + String(skewed)
        )
    else:
        failed += 1
        print(
            "  ❌ capacity does not track skew: uniform=" + String(uni)
            + " skewed=" + String(skewed) + " unskewed=" + String(unskewed)
        )

    # ── 3. the main batch: high cardinality, adversarial values ──────────────
    var nan_a = Float64(0.0) / Float64(0.0)
    var nan_b = -(Float64(0.0) / Float64(0.0))
    var inf_p = Float64(1.0) / Float64(0.0)
    var inf_n = Float64(-1.0) / Float64(0.0)

    var keys = List[Float64](capacity=ROWS)
    var va = List[Float64](capacity=ROWS)
    var vb = List[Float64](capacity=ROWS)
    var s2: UInt64 = 0x13198A2E03707344
    for i in range(ROWS):
        var m = i % 601
        if m == 0:
            keys.append(nan_a)  # NaN keys: ONE group, whatever the payload
        elif m == 1:
            keys.append(nan_b)
        elif m == 2:
            keys.append(-0.0)  # collapses into the +0.0 group
        elif m == 3:
            keys.append(0.0)
        elif m == 4:
            keys.append(inf_p)
        elif m == 5:
            keys.append(inf_n)
        elif m == 6:
            keys.append(-7.5)  # the ALL-NaN-values group
        else:
            keys.append(Float64(Int(_lcg(s2) % UInt64(KEYS))))
        if m == 6:
            va.append(nan_a if (i % 2) == 0 else nan_b)
            vb.append(nan_b)
        elif m == 7:
            va.append(-0.0)
            vb.append(0.0)
        elif m == 8:
            va.append(inf_p)
            vb.append(inf_n)
        elif (i % 53) == 11:
            va.append(nan_a)  # NaN inside otherwise-live groups
            vb.append(Float64(i % 71) - 35.0)
        else:
            va.append(Float64(Int(_lcg(s2) % 2000)) - 1000.0)
            vb.append(Float64(i % 37) * 0.125)

    var mnames = List[String]()
    mnames.append("k")
    mnames.append("a")
    mnames.append("b")
    var mcols = List[Float64Array]()
    mcols.append(float64_from_list(keys^))
    mcols.append(float64_from_list(va^))
    mcols.append(float64_from_list(vb^))
    var main_batch = RecordBatch(schema_of(mnames^), mcols^, ROWS)
    var k0 = _one(0)

    # Every opcode crosses the new plumbing, in TWO calls of four aggregates.
    # One call of eight is refused by the footprint rule at 200k rows — a
    # ten-word record over a small band costs more slack than the shipped
    # payload's fixed 32 bytes/row — and a refused call would make this battery
    # test delegation instead of the engine.
    var vc_a = List[Int]()
    var op_a = List[Int]()
    vc_a.append(1)
    op_a.append(AGG_MIN)
    vc_a.append(1)
    op_a.append(AGG_MAX)
    vc_a.append(1)
    op_a.append(AGG_SUM)
    vc_a.append(1)
    op_a.append(AGG_AVG)
    _cmp(passed, failed, "ops-min/max/sum/avg", main_batch, k0, vc_a, op_a, WORKERS, True)
    var vc_b = List[Int]()
    var op_b = List[Int]()
    vc_b.append(1)
    op_b.append(AGG_COUNT)
    vc_b.append(2)
    op_b.append(AGG_MIN)
    vc_b.append(2)
    op_b.append(AGG_VAR)
    vc_b.append(2)
    op_b.append(AGG_STD)
    _cmp(passed, failed, "ops-count/min/var/std", main_batch, k0, vc_b, op_b, WORKERS, True)

    # the NaN policy, read out explicitly rather than only compared
    var vc_mm = List[Int]()
    var op_mm = List[Int]()
    vc_mm.append(1)
    op_mm.append(AGG_MIN)
    vc_mm.append(1)
    op_mm.append(AGG_MAX)
    vc_mm.append(1)
    op_mm.append(AGG_COUNT)
    var mm = group_by_many_radix_fused(main_batch, k0, vc_mm, op_mm, WORKERS)
    var nan_group = -1
    var nankey_group = -1
    for g in range(mm.n_groups()):
        var kv = mm.key_at(g)[0]
        if kv == -7.5:
            nan_group = g
        if kv != kv:
            nankey_group = g
    var policy_ok = True
    if nan_group < 0:
        policy_ok = False
        print("  ❌ [nan-policy] the all-NaN-values group is missing")
    else:
        # all values NaN: min/max are the canonical quiet NaN, PRESENT, and the
        # rows still COUNT.
        if not mm.present_at(nan_group, 0) or not mm.present_at(nan_group, 1):
            policy_ok = False
            print("  ❌ [nan-policy] an all-NaN group must still answer min/max")
        var vmin = mm.value_at(nan_group, 0)
        var vmax = mm.value_at(nan_group, 1)
        if vmin == vmin or vmax == vmax:
            policy_ok = False
            print("  ❌ [nan-policy] an all-NaN group's extremum must be NaN")
        if _bits(vmin) != _bits(vmax):
            policy_ok = False
            print("  ❌ [nan-policy] all-NaN min/max must share the CANONICAL NaN bits")
        if mm.value_at(nan_group, 2) <= 0.0:
            policy_ok = False
            print("  ❌ [nan-policy] NaN values must still count")
    if nankey_group < 0:
        policy_ok = False
        print("  ❌ [nan-policy] NaN keys must form a group")
    else:
        var nk = 0
        for g in range(mm.n_groups()):
            if mm.key_at(g)[0] != mm.key_at(g)[0]:
                nk += 1
        if nk != 1:
            policy_ok = False
            print("  ❌ [nan-policy] NaN keys formed " + String(nk) + " groups, want 1")
    # a group with SOME NaN values must still report an extremum over the live ones
    var live_ok = False
    for g in range(mm.n_groups()):
        var kv = mm.key_at(g)[0]
        if kv == kv and kv != -7.5 and mm.present_at(g, 0):
            var lo = mm.value_at(g, 0)
            if lo == lo:
                live_ok = True
                break
    if not live_ok:
        policy_ok = False
        print("  ❌ [nan-policy] no group reported a live extremum")
    if policy_ok:
        passed += 1
        print(
            "  ✅ NaN policy: no extremum from a NaN, all-NaN -> canonical NaN present,"
            " NaN keys are ONE group, NaN values still count"
        )
    else:
        failed += 1

    # ── 4. clustered / reverse-clustered / ragged shapes ─────────────────────
    var ck = List[Float64](capacity=ROWS)
    var cv = List[Float64](capacity=ROWS)
    # Two rows per key, ascending: perfectly clustered, and the 65536-row probe
    # window still sees 32768 distinct keys — above RADIX_MIN_GROUPS, so the
    # planner routes RADIX and the fused engine is the thing under test.
    for i in range(ROWS):
        ck.append(Float64(i // 2))
        cv.append(Float64(i % 977) * 0.5)
    var cnames = List[String]()
    cnames.append("k")
    cnames.append("v")
    var ccols = List[Float64Array]()
    ccols.append(float64_from_list(ck^))
    ccols.append(float64_from_list(cv^))
    var cbatch = RecordBatch(schema_of(cnames^), ccols^, ROWS)
    var vc_s = _one(1)
    var op_sum = _one(AGG_SUM)
    _cmp(passed, failed, "clustered", cbatch, k0, vc_s, op_sum, WORKERS, True)

    var rk = List[Float64](capacity=ROWS)
    var rv = List[Float64](capacity=ROWS)
    for i in range(ROWS):
        rk.append(Float64((ROWS - 1 - i) // 2))
        rv.append(Float64(i % 883) * 0.25)
    var rnames = List[String]()
    rnames.append("k")
    rnames.append("v")
    var rcols = List[Float64Array]()
    rcols.append(float64_from_list(rk^))
    rcols.append(float64_from_list(rv^))
    var rbatch = RecordBatch(schema_of(rnames^), rcols^, ROWS)
    _cmp(passed, failed, "reverse-clustered", rbatch, k0, vc_s, op_sum, WORKERS, True)
    # an ODD worker count leaves a ragged last band
    _cmp(passed, failed, "odd-workers", rbatch, k0, vc_s, op_sum, 7, True)
    _cmp(passed, failed, "one-worker", rbatch, k0, vc_s, op_sum, 1, False)

    # ── 5. the OVERFLOW refusal, actually taken ──────────────────────────────
    # The capacity probe reads the HEAD. Put 40% of the rows on ONE key in the
    # TAIL: the probe cannot see it, the estimate is too small, a band lands
    # wholly inside one partition, the occupancy test fires, and the call must
    # be refused and answered by the shipped engine — exactly.
    var ok_head = ROWS * 6 // 10
    var hk = List[Float64](capacity=ROWS)
    var hv = List[Float64](capacity=ROWS)
    var s3: UInt64 = 0xA4093822299F31D0
    for i in range(ROWS):
        if i < ok_head:
            hk.append(Float64(Int(_lcg(s3) % UInt64(KEYS))))
        else:
            hk.append(123456.0)  # one key, 40% of the rows, all in the tail
        hv.append(Float64(i % 599) - 299.0)
    var hnames = List[String]()
    hnames.append("k")
    hnames.append("v")
    var hcols = List[Float64Array]()
    hcols.append(float64_from_list(hk^))
    hcols.append(float64_from_list(hv^))
    var hbatch = RecordBatch(schema_of(hnames^), hcols^, ROWS)
    var head_peak = fused_partition_peak(hbatch, 0, 65536)
    var tail_peak = fused_partition_peak(hbatch, 0, ROWS)
    if tail_peak > head_peak * 2:
        passed += 1
        print(
            "  ✅ the probe under-reads a tail-hidden heavy key: head peak="
            + String(head_peak) + " whole-batch peak=" + String(tail_peak)
        )
    else:
        failed += 1
        print(
            "  ❌ the overflow fixture is not skewed as intended: head="
            + String(head_peak) + " whole=" + String(tail_peak)
        )
    # applicable (it looks uniform from the head) and yet must still be right
    _cmp(passed, failed, "tail-heavy", hbatch, k0, vc_s, op_sum, WORKERS, True)

    # ── 6. the applicability table, and every refusal still answering ────────
    # width 2: the injectivity proof stops at a fixed-length fold
    var w2 = List[Int]()
    w2.append(0)
    w2.append(1)
    _cmp(passed, failed, "width-2", main_batch, w2, _one(2), _one(AGG_SUM), WORKERS, False)

    # NULL values
    var nv = List[Float64](capacity=ROWS)
    var nm = List[Bool](capacity=ROWS)
    var nk2 = List[Float64](capacity=ROWS)
    var s4: UInt64 = 0x082EFA98EC4E6C89
    for i in range(ROWS):
        nk2.append(Float64(Int(_lcg(s4) % UInt64(KEYS))))
        nv.append(Float64(i % 313) - 156.0)
        nm.append((i % 9) != 0)
    var nnames = List[String]()
    nnames.append("k")
    nnames.append("v")
    var ncols = List[Float64Array]()
    ncols.append(float64_from_list(nk2^))
    ncols.append(float64_with_nulls(nv^, nm))
    var nbatch = RecordBatch(schema_of(nnames^), ncols^, ROWS)
    _cmp(passed, failed, "null-values", nbatch, k0, _one(1), _one(AGG_AVG), WORKERS, False)

    # NULL keys — and the null-key tally must survive the delegation
    var kv2 = List[Float64](capacity=ROWS)
    var km = List[Bool](capacity=ROWS)
    var kvv = List[Float64](capacity=ROWS)
    var s5: UInt64 = 0x452821E638D01377
    for i in range(ROWS):
        kv2.append(Float64(Int(_lcg(s5) % UInt64(KEYS))))
        km.append((i % 13) != 0)
        kvv.append(Float64(i % 211) * 0.75)
    var knames = List[String]()
    knames.append("k")
    knames.append("v")
    var kcols = List[Float64Array]()
    kcols.append(float64_with_nulls(kv2^, km))
    kcols.append(float64_from_list(kvv^))
    var kbatch = RecordBatch(schema_of(knames^), kcols^, ROWS)
    _cmp(passed, failed, "null-keys", kbatch, k0, _one(1), _one(AGG_SUM), WORKERS, False)
    var nkres = group_by_many_radix_fused(kbatch, k0, _one(1), _one(AGG_SUM), WORKERS)
    var nkser = group_by_many_parallel(kbatch, k0, _one(1), _one(AGG_SUM), 1)
    if nkres.null_key_rows == nkser.null_key_rows and nkres.null_key_rows > 0:
        passed += 1
        print(
            "  ✅ the null-key tally survives the refusal: "
            + String(nkres.null_key_rows) + " rows"
        )
    else:
        failed += 1
        print(
            "  ❌ null-key tally " + String(nkres.null_key_rows)
            + " != serial " + String(nkser.null_key_rows)
        )

    # LOW cardinality: the planner sends this to CODED / BANDED and the engine
    # must not steal it. Stealing a CODED question is a several-fold regression.
    var lk = List[Float64](capacity=ROWS)
    var lv = List[Float64](capacity=ROWS)
    for i in range(ROWS):
        lk.append(Float64(i % 100))
        lv.append(Float64(i % 419) * 0.5)
    var lnames = List[String]()
    lnames.append("k")
    lnames.append("v")
    var lcols = List[Float64Array]()
    lcols.append(float64_from_list(lk^))
    lcols.append(float64_from_list(lv^))
    var lbatch = RecordBatch(schema_of(lnames^), lcols^, ROWS)
    _cmp(passed, failed, "low-card", lbatch, k0, _one(1), _one(AGG_SUM), WORKERS, False)

    # too few rows
    var tk = List[Float64](capacity=4000)
    var tv = List[Float64](capacity=4000)
    for i in range(4000):
        tk.append(Float64(i % 997))
        tv.append(Float64(i) * 0.5)
    var tnames = List[String]()
    tnames.append("k")
    tnames.append("v")
    var tcols = List[Float64Array]()
    tcols.append(float64_from_list(tk^))
    tcols.append(float64_from_list(tv^))
    var tbatch = RecordBatch(schema_of(tnames^), tcols^, 4000)
    _cmp(passed, failed, "small", tbatch, k0, _one(1), _one(AGG_SUM), WORKERS, False)

    # malformed request: opcodes and value columns must pair by position
    var bad_ops = List[Int]()
    bad_ops.append(AGG_SUM)
    bad_ops.append(AGG_SUM)
    if fused_late_applicable(main_batch, k0, _one(1), bad_ops, WORKERS):
        failed += 1
        print("  ❌ took a request whose opcodes do not pair with its value columns")
    else:
        passed += 1
    var mf = group_by_many_radix_fused(main_batch, k0, _one(1), bad_ops, WORKERS)
    if mf.n_groups() == 0:
        passed += 1
        print("  ✅ a malformed request returns the shipped EMPTY result")
    else:
        failed += 1
        print("  ❌ a malformed request returned " + String(mf.n_groups()) + " groups")

    # zero key columns is the whole-batch case the shipped path owns
    var no_keys = List[Int]()
    if fused_late_applicable(main_batch, no_keys, _one(1), _one(AGG_SUM), WORKERS):
        failed += 1
        print("  ❌ took a request with zero key columns")
    else:
        passed += 1
        print("  ✅ zero key columns stays on the shipped width-0 path")

    print("  [query.aggregate_late] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_query_aggregate_late: " + String(failed) + " failure(s)")
