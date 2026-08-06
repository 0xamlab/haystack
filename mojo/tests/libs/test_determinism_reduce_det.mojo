"""test_determinism_reduce_det.mojo — hand-written tests for the fixed-shape reductions.

Hand-written, never machine-emitted.

The deliverable this suite exists to prove is INVARIANCE, and every invariance assertion
uses `==` on Float64. That is deliberate and it is the point of the module: a tolerance
would accept exactly the association-order drift the fixed tree removes, so a tolerant
test here would be a test of nothing.

The suite is also its own control. Before asserting that the tree is chunk-invariant it
asserts that the sequential baseline on the SAME data is NOT — otherwise "all chunkings
agree" could be true because the data is too benign to distinguish them.

Reference values (independently computed in Python with `decimal.Decimal` for the exact
column, and cross-checked against a Python transcription of the same tree):

    data = [1e16] + N x 1.0
    N        exact                sequential   tree
    2^10     10000000000001024    1e16         10000000000001024   (exactly rounded)
    2^16     10000000000065536    1e16         10000000000065536
    2^20     10000000001048576    1e16         10000000001048576

    [1.0, 1e100, 1.0, -1e100], exact 2.0
    sequential 0.0   kahan 0.0   tree 0.0   neumaier 2.0
"""
from determinism.reduce_det import (
    COUNTER_CAPACITY,
    DET_EMPTY,
    DET_ERR_CHUNK,
    DET_ERR_COUNT,
    DET_ERR_NON_FINITE,
    DET_ERR_OVERFLOW,
    DET_ERR_PAIR_LENGTH,
    DET_OK,
    MAX_TREE_LEVELS,
    det_dot,
    det_kahan_sum,
    det_mean,
    det_naive_sum,
    det_naive_sum_chunked,
    det_neumaier_sum,
    det_status_name,
    det_sum,
    det_sum_chunked,
    det_sum_opcode,
    det_sum_squares,
    det_tree_depth,
    reduction_shape_id,
)
from numeric.contract import AGG_SUM


def big_then_ones(n_ones: Int) -> List[Float64]:
    """`[1e16] + n_ones x 1.0` — the classic case where a sequential sum loses every 1.0.

    1e16 lies in [2^53, 2^54) so its ulp is 2.0, and `1e16 + 1.0` rounds to 1e16. A
    left-to-right sum therefore discards all `n_ones` terms; a tree sums them among
    themselves first, where they are exact.
    """
    var out = List[Float64]()
    out.append(1e16)
    for _ in range(n_ones):
        out.append(1.0)
    return out^


def cancelling() -> List[Float64]:
    """`[1.0, 1e100, 1.0, -1e100]` — exact sum 2.0. Kahan's known limit."""
    var out = List[Float64]()
    out.append(1.0)
    out.append(1e100)
    out.append(1.0)
    out.append(-1e100)
    return out^


def main() raises:
    var failures = 0
    var checks = 0

    # ── the shape identity is stable and is what the manifest will record ─────
    checks += 1
    if reduction_shape_id() != String("det-pairwise-aligned-blocks/v1"):
        print("  ❌ reduction_shape_id drifted:", reduction_shape_id())
        failures += 1

    checks += 1
    if det_sum_opcode() != AGG_SUM:
        print("  ❌ det_sum_opcode is not numeric.contract's AGG_SUM")
        failures += 1

    # ── tree depth: pure function of n, and inside the counter bound ──────────
    var depth_n = List[Int]()
    var depth_want = List[Int]()
    depth_n.append(0); depth_want.append(0)
    depth_n.append(1); depth_want.append(0)
    depth_n.append(2); depth_want.append(1)
    depth_n.append(3); depth_want.append(2)
    depth_n.append(4); depth_want.append(2)
    depth_n.append(7); depth_want.append(3)
    depth_n.append(8); depth_want.append(3)
    depth_n.append(1000); depth_want.append(10)
    for i in range(len(depth_n)):
        checks += 1
        if det_tree_depth(depth_n[i]) != depth_want[i]:
            print("  ❌ det_tree_depth(", depth_n[i], ")=", det_tree_depth(depth_n[i]),
                  "want", depth_want[i])
            failures += 1
    checks += 1
    if det_tree_depth(1 << 40) >= MAX_TREE_LEVELS:
        print("  ❌ counter bound MAX_TREE_LEVELS is not a bound")
        failures += 1
    # The reserved capacity has to cover TWO blocks per level plus one transient entry,
    # because a counter fed an interval that does not start at a block boundary carries a
    # ragged block on each side. A capacity of exactly MAX_TREE_LEVELS would silently
    # reallocate on an unaligned chunk, which is a performance claim quietly becoming false.
    checks += 1
    if COUNTER_CAPACITY < 2 * MAX_TREE_LEVELS + 1:
        print("  ❌ COUNTER_CAPACITY", COUNTER_CAPACITY,
              "does not cover two blocks per level plus a transient entry")
        failures += 1

    # ── known values on small exact data ─────────────────────────────────────
    var small = List[Float64]()
    small.append(1.0)
    small.append(2.0)
    small.append(3.0)
    small.append(4.0)
    small.append(5.0)
    checks += 1
    var s5 = det_sum(small, 5)
    if not (s5.present and s5.status == DET_OK and s5.value == 15.0 and s5.n == 5):
        print("  ❌ det_sum small got", s5.value, det_status_name(s5.status))
        failures += 1
    checks += 1
    var m5 = det_mean(small, 5)
    if not (m5.present and m5.value == 3.0):
        print("  ❌ det_mean small got", m5.value)
        failures += 1
    checks += 1
    var q5 = det_sum_squares(small, 5)
    if not (q5.present and q5.value == 55.0):
        print("  ❌ det_sum_squares small got", q5.value)
        failures += 1
    checks += 1
    var d5 = det_dot(small, small, 5)
    if not (d5.present and d5.value == 55.0):
        print("  ❌ det_dot(a,a) got", d5.value)
        failures += 1
    # sum_squares and dot(a,a) must agree bit-for-bit, as the docstring claims.
    checks += 1
    if q5.value != d5.value:
        print("  ❌ det_sum_squares != det_dot(a,a):", q5.value, d5.value)
        failures += 1

    # ── rule 4: absence, never zero, never under a success status ─────────────
    var empty = List[Float64]()
    checks += 1
    var sum0 = det_sum(empty, 0)
    if not (sum0.present and sum0.status == DET_OK and sum0.value == 0.0):
        print("  ❌ sum of nothing must be 0 and present")
        failures += 1
    checks += 1
    var mean0 = det_mean(empty, 0)
    if mean0.present or mean0.status != DET_EMPTY:
        print("  ❌ mean of nothing must be absent under DET_EMPTY, got",
              det_status_name(mean0.status))
        failures += 1
    checks += 1
    if mean0.status == DET_OK:
        print("  ❌ an absent mean must not carry a success status")
        failures += 1

    # ── rule 1: every count guarded. n > len(a) must be REFUSED, not indexed ──
    # If any of these indexed, the process would die here rather than fail a check.
    checks += 1
    var over = det_sum(small, 25)
    if over.present or over.status != DET_ERR_COUNT:
        print("  ❌ det_sum(len=5, n=25) not refused:", det_status_name(over.status))
        failures += 1
    checks += 1
    if det_mean(small, 6).status != DET_ERR_COUNT:
        print("  ❌ det_mean count guard")
        failures += 1
    checks += 1
    if det_sum_squares(small, 6).status != DET_ERR_COUNT:
        print("  ❌ det_sum_squares count guard")
        failures += 1
    checks += 1
    if det_naive_sum(small, 6).status != DET_ERR_COUNT:
        print("  ❌ det_naive_sum count guard")
        failures += 1
    checks += 1
    if det_kahan_sum(small, 6).status != DET_ERR_COUNT:
        print("  ❌ det_kahan_sum count guard")
        failures += 1
    checks += 1
    if det_neumaier_sum(small, 6).status != DET_ERR_COUNT:
        print("  ❌ det_neumaier_sum count guard")
        failures += 1
    checks += 1
    if det_sum(small, -1).status != DET_ERR_COUNT:
        print("  ❌ negative count guard")
        failures += 1
    checks += 1
    if det_sum_chunked(small, 25, 2).status != DET_ERR_COUNT:
        print("  ❌ det_sum_chunked count guard")
        failures += 1
    checks += 1
    if det_naive_sum_chunked(small, 25, 2).status != DET_ERR_COUNT:
        print("  ❌ det_naive_sum_chunked count guard")
        failures += 1

    # dot: the count must fit BOTH lists, and the shorter one is the hazard.
    var pair_short = List[Float64]()
    pair_short.append(1.0)
    pair_short.append(1.0)
    checks += 1
    var dp = det_dot(small, pair_short, 5)
    if dp.present or dp.status != DET_ERR_PAIR_LENGTH:
        print("  ❌ det_dot(len 5, len 2, n=5) not refused:", det_status_name(dp.status))
        failures += 1
    checks += 1
    var dp2 = det_dot(pair_short, small, 5)
    if dp2.status != DET_ERR_PAIR_LENGTH:
        print("  ❌ det_dot short first argument not refused")
        failures += 1
    checks += 1
    if det_dot(small, small, -1).status != DET_ERR_COUNT:
        print("  ❌ det_dot negative count")
        failures += 1

    # chunk size below one would loop forever; it must be refused.
    checks += 1
    if det_sum_chunked(small, 5, 0).status != DET_ERR_CHUNK:
        print("  ❌ chunk=0 not refused")
        failures += 1
    checks += 1
    if det_sum_chunked(small, 5, -3).status != DET_ERR_CHUNK:
        print("  ❌ chunk=-3 not refused")
        failures += 1
    checks += 1
    if det_naive_sum_chunked(small, 5, 0).status != DET_ERR_CHUNK:
        print("  ❌ naive chunk=0 not refused")
        failures += 1

    # ── non-finite input is refused, so `==` stays a usable assertion ─────────
    var withnan = List[Float64]()
    withnan.append(1.0)
    withnan.append(Float64("nan"))
    withnan.append(2.0)
    checks += 1
    var rn = det_sum(withnan, 3)
    if rn.present or rn.status != DET_ERR_NON_FINITE:
        print("  ❌ nan not refused:", det_status_name(rn.status))
        failures += 1
    checks += 1
    if det_dot(withnan, withnan, 3).status != DET_ERR_NON_FINITE:
        print("  ❌ det_dot nan not refused")
        failures += 1
    var withinf = List[Float64]()
    withinf.append(Float64("inf"))
    withinf.append(1.0)
    checks += 1
    if det_sum(withinf, 2).status != DET_ERR_NON_FINITE:
        print("  ❌ inf not refused")
        failures += 1
    # A nan BEYOND the declared count must not be looked at.
    checks += 1
    var tail_ok = det_sum(withnan, 1)
    if not (tail_ok.present and tail_ok.value == 1.0):
        print("  ❌ a nan past n must be ignored, got", det_status_name(tail_ok.status))
        failures += 1

    # ── a finite input whose sum overflows has no representable answer ────────
    var huge = List[Float64]()
    huge.append(1.7e308)
    huge.append(1.7e308)
    checks += 1
    var ov = det_sum(huge, 2)
    if ov.present or ov.status != DET_ERR_OVERFLOW:
        print("  ❌ overflow must be absent, got", det_status_name(ov.status),
              "value", ov.value)
        failures += 1

    # ── THE CONTROL: the sequential baseline is order-dependent ──────────────
    # If this passes trivially the invariance test below proves nothing.
    var data10 = big_then_ones(1 << 10)
    var n10 = len(data10)
    var naive_whole = det_naive_sum(data10, n10)
    checks += 1
    if naive_whole.value != 1e16:
        print("  ❌ expected the sequential sum to lose every 1.0, got", naive_whole.value)
        failures += 1
    var naive_chunks = List[Int]()
    naive_chunks.append(1)
    naive_chunks.append(2)
    naive_chunks.append(3)
    naive_chunks.append(7)
    naive_chunks.append(64)
    naive_chunks.append(257)
    var distinct_naive = 0
    var seen = List[Float64]()
    for i in range(len(naive_chunks)):
        var got = det_naive_sum_chunked(data10, n10, naive_chunks[i])
        var novel = True
        for j in range(len(seen)):
            if seen[j] == got.value:
                novel = False
        if novel:
            seen.append(got.value)
            distinct_naive += 1
    checks += 1
    if distinct_naive < 3:
        print("  ❌ the sequential baseline gave only", distinct_naive,
              "distinct answers — the control is not exercising order dependence")
        failures += 1

    # ── THE DELIVERABLE: the tree is invariant under every chunking, with == ─
    var chunk_sizes = List[Int]()
    chunk_sizes.append(1)
    chunk_sizes.append(2)
    chunk_sizes.append(3)
    chunk_sizes.append(7)
    chunk_sizes.append(64)
    chunk_sizes.append(1000)
    chunk_sizes.append(n10 // 2)
    chunk_sizes.append(n10)
    chunk_sizes.append(n10 + 5)
    var tree_whole = det_sum(data10, n10)
    checks += 1
    if not tree_whole.present:
        print("  ❌ tree sum absent:", det_status_name(tree_whole.status))
        failures += 1
    for i in range(len(chunk_sizes)):
        var got = det_sum_chunked(data10, n10, chunk_sizes[i])
        checks += 1
        if got.value != tree_whole.value:
            print("  ❌ chunk", chunk_sizes[i], "gave", got.value,
                  "whole gave", tree_whole.value)
            failures += 1
    # ... and it is the exactly-rounded answer for this family.
    checks += 1
    if tree_whole.value != 1.0000000000001024e16:
        print("  ❌ tree sum of [1e16]+2^10x1.0 got", tree_whole.value,
              "want 1.0000000000001024e16")
        failures += 1

    # Same at 2^16 and 2^20, where the sequential error is 65536 and 1048576.
    var data16 = big_then_ones(1 << 16)
    var t16 = det_sum(data16, len(data16))
    checks += 1
    if t16.value != 1.0000000000065536e16:
        print("  ❌ 2^16 tree sum got", t16.value)
        failures += 1
    checks += 1
    if det_naive_sum(data16, len(data16)).value != 1e16:
        print("  ❌ 2^16 sequential sum was expected to lose every term")
        failures += 1
    var half16 = det_sum_chunked(data16, len(data16), len(data16) // 2)
    var odd16 = det_sum_chunked(data16, len(data16), 3)
    checks += 1
    if not (half16.value == t16.value and odd16.value == t16.value):
        print("  ❌ 2^16 invariance:", t16.value, half16.value, odd16.value)
        failures += 1

    var data20 = big_then_ones(1 << 20)
    var t20 = det_sum(data20, len(data20))
    checks += 1
    if t20.value != 1.0000000001048576e16:
        print("  ❌ 2^20 tree sum got", t20.value)
        failures += 1
    checks += 1
    if det_sum_chunked(data20, len(data20), 4096).value != t20.value:
        print("  ❌ 2^20 invariance under 4096-element chunks")
        failures += 1
    checks += 1
    if det_sum_chunked(data20, len(data20), 1).value != t20.value:
        print("  ❌ 2^20 invariance under 1-element chunks")
        failures += 1

    # ── invariance is not special to that family: it must hold on ragged data ─
    var ragged = List[Float64]()
    for i in range(1037):
        # Wide magnitudes and alternating signs, so association order matters.
        var sign = 1.0 if (i % 3) == 0 else -1.0
        ragged.append(sign * Float64(i + 1) * 1e-7 * Float64((i % 17) + 1))
        if i % 101 == 0:
            ragged.append(1e9)
    var rn_len = len(ragged)
    var rag_whole = det_sum(ragged, rn_len)
    var rag_bad = 0
    for c in range(1, 40):
        if det_sum_chunked(ragged, rn_len, c).value != rag_whole.value:
            rag_bad += 1
    for c in range(40, rn_len + 3, 37):
        if det_sum_chunked(ragged, rn_len, c).value != rag_whole.value:
            rag_bad += 1
    checks += 1
    if rag_bad != 0:
        print("  ❌ ragged data: ", rag_bad, "chunk sizes disagreed with the whole")
        failures += 1
    # And the sequential baseline on the SAME ragged data does disagree.
    var rag_naive_distinct = 0
    var rag_seen = List[Float64]()
    for c in range(1, 40):
        var g = det_naive_sum_chunked(ragged, rn_len, c).value
        var novel2 = True
        for j in range(len(rag_seen)):
            if rag_seen[j] == g:
                novel2 = False
        if novel2:
            rag_seen.append(g)
            rag_naive_distinct += 1
    checks += 1
    if rag_naive_distinct < 2:
        print("  ❌ ragged control: sequential gave", rag_naive_distinct, "answers")
        failures += 1

    # ── mean and dot inherit the invariance ──────────────────────────────────
    var mean_whole = det_mean(ragged, rn_len)
    var mean_ok = True
    for c in range(1, 25):
        var chunked_sum = det_sum_chunked(ragged, rn_len, c)
        if chunked_sum.value / Float64(rn_len) != mean_whole.value:
            mean_ok = False
    checks += 1
    if not mean_ok:
        print("  ❌ det_mean is not invariant under chunking of its sum")
        failures += 1

    # ── compensated summation: precise about what it does and does not give ──
    var canc = cancelling()
    checks += 1
    if det_naive_sum(canc, 4).value != 0.0:
        print("  ❌ expected sequential 0.0 on the cancelling array, got",
              det_naive_sum(canc, 4).value)
        failures += 1
    checks += 1
    if det_kahan_sum(canc, 4).value != 0.0:
        print("  ❌ expected the frozen kahan_sum to return 0.0 here (its documented",
              "limit), got", det_kahan_sum(canc, 4).value)
        failures += 1
    checks += 1
    if det_neumaier_sum(canc, 4).value != 2.0:
        print("  ❌ Neumaier must recover the exact 2.0, got",
              det_neumaier_sum(canc, 4).value)
        failures += 1
    # The tree does NOT fix this case, and claiming otherwise would be the defect
    # this project keeps finding. Assert the honest value.
    checks += 1
    if det_sum(canc, 4).value != 0.0:
        print("  ❌ the tree was expected to give 0.0 on the cancelling array, got",
              det_sum(canc, 4).value)
        failures += 1
    # Neumaier is NOT chunk-invariant. Measured: whole 2.0, chunks of 1/2/3 all 0.0.
    var neu_whole = det_neumaier_sum(canc, 4).value
    var neu_split = 0.0
    neu_split += det_neumaier_sum(canc, 2).value
    var back = List[Float64]()
    back.append(canc[2])
    back.append(canc[3])
    neu_split += det_neumaier_sum(back, 2).value
    checks += 1
    if neu_split == neu_whole:
        print("  ❌ Neumaier was expected NOT to be chunk-invariant here; the docstring",
              "claim that only det_sum is reproducible would be wrong")
        failures += 1

    # Kahan on the [1e16] + ones family DOES recover it — an honest statement of
    # where the frozen kernel is already sufficient.
    checks += 1
    if det_kahan_sum(data10, n10).value != tree_whole.value:
        print("  ❌ kahan on [1e16]+2^10 ones:", det_kahan_sum(data10, n10).value,
              "tree:", tree_whole.value)
        failures += 1

    # ── status names are total ────────────────────────────────────────────────
    var codes = List[Int]()
    codes.append(DET_OK)
    codes.append(DET_ERR_COUNT)
    codes.append(DET_ERR_PAIR_LENGTH)
    codes.append(DET_ERR_CHUNK)
    codes.append(DET_EMPTY)
    codes.append(DET_ERR_NON_FINITE)
    codes.append(DET_ERR_OVERFLOW)
    for i in range(len(codes)):
        checks += 1
        if det_status_name(codes[i]) == String("unknown_status"):
            print("  ❌ status", codes[i], "has no name")
            failures += 1
    checks += 1
    if det_status_name(-999) != String("unknown_status"):
        print("  ❌ an unallocated code must not get a name")
        failures += 1

    # One ✅ per check that did not fail, so the A-Z harness reports a real count
    # rather than 0/0. `checks` is derived from the ❌ sites, never hardcoded.
    for _ in range(checks - failures):
        print("  ✅ reduce_det check")
    print("  [determinism.reduce_det] Passed:", checks - failures, "Failed:", failures)
    if failures != 0:
        raise Error("test_determinism_reduce_det failed")
