"""bench_llmk.mojo — timing and cost-shape gate for the decode-loop primitives.

Hand-written, not generated. No library is named `llmk` at the top level, so nothing can collide
with this filename, and the generator only writes — it never unlinks.

Three kernels, and they are not equally interesting
-----------------------------------------------------
1. `residual_add_flat` — a plain elementwise add over a whole flat buffer. There is no shape claim
   here beyond "linear in n, and correct": it is one add per element, nothing more. The gate is the
   same flat-cost-per-cell shape every other elementwise kernel in this plane is held to.

2. `greedy_argmax_flat` — the one kernel here with a real correctness story. `llm_sampling`'s frozen
   `greedy_token_id` is a per-candidate comparison, not a full argmax, and its own docstring takes
   `max_logit` as something the caller already knows. `greedy_argmax_flat` supplies the two passes
   that make it one: a bare max-scan (no frozen kernel computes a reduction-max, and there is no
   sampling decision in finding one), then the frozen per-candidate formula, called once per
   vocabulary entry exactly as published. Ties resolve to the FIRST matching id — `numpy.argmax`'s
   own convention — so this is asserted directly with a deliberately tied input, not merely assumed
   from reading the loop.

3. `kv_cache_append_flat` — and this is the one with the unflattering finding. Read plainly: the
   function allocates a brand-new `List` sized `cache_len + n_new` and copies BOTH the existing
   cache (every element of it) and the new values into it, on every single call. That is a real
   `O(cache_len + n_new)` cost per call, not an amortized append. It is measured directly below by
   holding `n_new` fixed and raising `cache_len`: cost per NEWLY appended element grows with
   `cache_len`, because the call is dominated by re-copying a cache that did not change. This is not
   a bug and it does not affect correctness — the output is the right buffer, in the right order,
   every time — but a caller who appends to a cache many times in a hot loop pays quadratic total
   copy cost across the whole sequence, not the O(1)-amortized cost an append usually implies. That
   is disclosed here as a measured property, not smoothed into a "fast enough" number.

   `qwen3_generate.mojo`'s decode loop WAS that caller (twice per layer per step, K then V, every
   step, against the same cache) and no longer is: it now calls `llmk.generate`'s internal (leading-
   underscore) `_kv_cache_append_into_flat` against a buffer `_kv_cache_reserve_flat` pre-sizes once,
   up front, to the loop's own known maximum length. Section 4 below measures THAT path, holding
   `n_new` fixed and raising the existing-cache size exactly like section 3 does for the unchanged
   function — the point being the direct side-by-side: same measurement methodology, opposite cost
   shape, because this path never re-copies existing content.

Gate
----
Fails on the properties, not on absolute nanoseconds, which vary by machine:
  * residual_add_flat must agree with a direct scalar loop over the same buffers
  * residual_add_flat: ns per cell must not grow more than 3x across a 64x increase in buffer size
  * greedy_argmax_flat must agree with a reference max-scan, at the start, middle and end of a row
  * greedy_argmax_flat: an exact tie must resolve to the FIRST matching index
  * greedy_argmax_flat: ns per cell must not grow more than 3x across a 37x increase in vocabulary
  * kv_cache_append_flat must agree with direct list concatenation, cache ++ new_vals, in order
  * kv_cache_append_flat: ns per TOTAL copied element (cache_len + n_new) must stay roughly flat —
    the copy itself is bandwidth-bound, not degrading per byte moved
  * kv_cache_append_flat: ns per NEWLY APPENDED element must clearly GROW with cache_len — the
    positive confirmation of the O(cache_len + n_new)-per-call finding above. A run where it does
    NOT grow would mean the implementation changed and this docstring (and the published page) is
    now wrong, which is exactly why this is gated rather than merely printed.
  * _kv_cache_append_into_flat must agree with direct list concatenation, cache ++ new_vals, in order
  * _kv_cache_append_into_flat: ns per NEWLY APPENDED element must stay roughly FLAT as the existing
    cache grows — the inverse of kv_cache_append_flat's own finding above, and the positive proof the
    quadratic-total-copy cost is gone from the path the decode loop actually calls now.
Absolute numbers are printed for tracking.
"""
from std.time import perf_counter_ns

from llmk.contract import LLMK_OK
from llmk.generate import (
    _kv_cache_append_into_flat,
    _kv_cache_reserve_flat,
    greedy_argmax_flat,
    kv_cache_append_flat,
)
from llmk.residual import residual_add_flat


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def _pseudo(n: Int, seed: Int) -> List[Float64]:
    """Deterministic values in roughly [-1, 1], so runs are comparable across machines."""
    var o = List[Float64](capacity=n)
    var s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        o.append(Float64(s % 2000 - 1000) / 1000.0)
    return o^


def _ref_argmax(v: List[Float64], n: Int) -> Int:
    """Reference argmax: a bare linear scan, first-index-wins on a tie."""
    var best_i = 0
    var best_v = v[0]
    for i in range(1, n):
        if v[i] > best_v:
            best_v = v[i]
            best_i = i
    return best_i


def main() raises:
    var failures = 0
    print("=== llmk timing and cost-shape gate ===")

    # ── 1. residual_add_flat ────────────────────────────────────────────────────
    print("")
    print("[llmk.residual] correctness against a direct scalar loop")
    var ca = _pseudo(4096, 21)
    var cb = _pseudo(4096, 22)
    var cref = List[Float64](capacity=4096)
    for i in range(4096):
        cref.append(ca[i] + cb[i])
    var cres = residual_add_flat(ca, cb, 4096)
    var cdrift = 0.0
    for i in range(4096):
        var dd = _abs(cres.out[i] - cref[i])
        if dd > cdrift:
            cdrift = dd
    if cres.status == LLMK_OK and cdrift == 0.0:
        print("   correctness: bit-identical to a direct scalar loop over 4,096 cells")
    else:
        failures += 1
        print("   FAIL: residual_add_flat diverged from the scalar reference by", cdrift)

    print("")
    print("[llmk.residual] cost per cell across rising buffer size")
    print("   cells        total ns      ns/cell")
    var rsizes = List[Int]()
    rsizes.append(1 << 14)
    rsizes.append(1 << 17)
    rsizes.append(1 << 20)
    var r_first = 0.0
    var r_last = 0.0
    var r_reps = 20
    for si in range(len(rsizes)):
        var n = rsizes[si]
        var ra = _pseudo(n, 31 + si)
        var rb = _pseudo(n, 731 + si)
        var _warm = residual_add_flat(ra, rb, n)
        var t0 = perf_counter_ns()
        for _r in range(r_reps):
            var out = residual_add_flat(ra, rb, n)
            if out.status != LLMK_OK:
                failures += 1
                print("   FAIL: status", out.status, "at n =", n)
        var ns = _ns_since(t0) / Float64(r_reps)
        var per = ns / Float64(n)
        if si == 0:
            r_first = per
        r_last = per
        print("  ", n, "   ", ns, "   ", per)
    var r_growth = r_last / r_first if r_first > 0.0 else 0.0
    print("   ns/cell growth across a 64x larger buffer:", r_growth, "x  (gate: <= 3x)")
    if r_growth > 3.0:
        failures += 1
        print("   FAIL: an elementwise add should not cost more per cell as it grows —", r_growth, "x")

    # ── 2. greedy_argmax_flat ────────────────────────────────────────────────────
    print("")
    print("[llmk.generate] greedy_argmax_flat correctness — start, middle, end, negatives, tie")

    var a_mid = List[Float64]()
    a_mid.append(1.0)
    a_mid.append(9.0)
    a_mid.append(3.0)
    var r_mid = greedy_argmax_flat(a_mid, 3)
    var mid_ok = r_mid.status == LLMK_OK and r_mid.token_id == _ref_argmax(a_mid, 3)

    var a_start = List[Float64]()
    a_start.append(9.0)
    a_start.append(1.0)
    a_start.append(3.0)
    var start_ok = greedy_argmax_flat(a_start, 3).token_id == _ref_argmax(a_start, 3)

    var a_end = List[Float64]()
    a_end.append(1.0)
    a_end.append(3.0)
    a_end.append(9.0)
    var end_ok = greedy_argmax_flat(a_end, 3).token_id == _ref_argmax(a_end, 3)

    var a_neg = List[Float64]()
    a_neg.append(-5.0)
    a_neg.append(-1.0)
    a_neg.append(-9.0)
    var neg_ok = greedy_argmax_flat(a_neg, 3).token_id == _ref_argmax(a_neg, 3)

    if mid_ok and start_ok and end_ok and neg_ok:
        print("   correctness: agrees with a reference max-scan at the start, middle, end, and on")
        print("   all-negative logits (a real model produces these routinely)")
    else:
        failures += 1
        print("   FAIL: greedy_argmax_flat disagreed with the reference scan — mid", mid_ok,
              "start", start_ok, "end", end_ok, "neg", neg_ok)

    # Deliberate tie: two positions share the row's maximum. numpy.argmax's own convention is
    # first-index-wins, and that is the property asserted here, not merely read from the source.
    var a_tie = List[Float64]()
    a_tie.append(2.0)
    a_tie.append(7.0)
    a_tie.append(7.0)
    a_tie.append(1.0)
    var r_tie = greedy_argmax_flat(a_tie, 4)
    if r_tie.status == LLMK_OK and r_tie.token_id == 1:
        print("   correctness: an exact tie (index 1 == index 2, both 7.0) resolves to the FIRST")
        print("   matching id (1), matching numpy.argmax's own tie-break convention")
    else:
        failures += 1
        print("   FAIL: tie-break did not resolve to the first matching index — got", r_tie.token_id)

    print("")
    print("[llmk.generate] greedy_argmax_flat cost per cell across rising vocabulary")
    print("   vocab        total ns      ns/cell")
    var vsizes = List[Int]()
    vsizes.append(4096)
    vsizes.append(32768)
    vsizes.append(151936)  # a real Qwen3-0.6B-Base vocabulary width
    var v_first = 0.0
    var v_last = 0.0
    var v_reps = 20
    for vi in range(len(vsizes)):
        var vn = vsizes[vi]
        var logits = _pseudo(vn, 41 + vi)
        var _vwarm = greedy_argmax_flat(logits, vn)
        var vt0 = perf_counter_ns()
        for _r in range(v_reps):
            var vout = greedy_argmax_flat(logits, vn)
            if vout.status != LLMK_OK:
                failures += 1
                print("   FAIL: status", vout.status, "at vocab =", vn)
        var vns = _ns_since(vt0) / Float64(v_reps)
        var vper = vns / Float64(vn)
        if vi == 0:
            v_first = vper
        v_last = vper
        print("  ", vn, "   ", vns, "   ", vper)
    var v_growth = v_last / v_first if v_first > 0.0 else 0.0
    print("   ns/cell growth across a 37x wider vocabulary:", v_growth, "x  (gate: <= 3x)")
    if v_growth > 3.0:
        failures += 1
        print("   FAIL: a full-vocabulary argmax should not cost more per cell as it grows —",
              v_growth, "x")

    # ── 3. kv_cache_append_flat ──────────────────────────────────────────────────
    print("")
    print("[llmk.generate] kv_cache_append_flat correctness against direct concatenation")
    var base_cache = _pseudo(6000, 51)
    var base_new = _pseudo(128, 52)
    var kref = List[Float64](capacity=6128)
    for i in range(6000):
        kref.append(base_cache[i])
    for i in range(128):
        kref.append(base_new[i])
    var kres = kv_cache_append_flat(base_cache, base_new, 6000, 128)
    var kdrift = 0.0
    for i in range(6128):
        var dd = _abs(kres.out[i] - kref[i])
        if dd > kdrift:
            kdrift = dd
    if kres.status == LLMK_OK and kres.n == 6128 and kdrift == 0.0:
        print("   correctness: bit-identical to cache ++ new_vals, in order, 6,000 + 128 = 6,128")
    else:
        failures += 1
        print("   FAIL: kv_cache_append_flat diverged from direct concatenation by", kdrift)

    print("")
    print("[llmk.generate] kv_cache_append_flat cost as the EXISTING cache grows, n_new fixed at 128")
    print("   (one layer's worth of a decode step's freshly-projected K or V row, head_dim=128)")
    print("   cache_len    total ns      ns/appended-cell    ns/total-copied-cell")
    var clens = List[Int]()
    clens.append(512)
    clens.append(8192)
    clens.append(131072)
    var n_new = 128
    var new_vals = _pseudo(n_new, 61)
    var per_new_first = 0.0
    var per_new_last = 0.0
    var per_total_first = 0.0
    var per_total_last = 0.0
    # A single call at the smallest cache_len finishes in well under this host's clock
    # resolution (observed ~1us granularity on `perf_counter_ns` here), which would quantize to
    # 0 or 1 tick and make the ratio below meaningless. REPS amortizes that away: total elapsed
    # time across REPS calls is what is measured, then divided back down to a per-call figure.
    var reps = 200
    for ci in range(len(clens)):
        var cache_len = clens[ci]
        var existing = _pseudo(cache_len, 900 + ci)
        var _kwarm = kv_cache_append_flat(existing, new_vals, cache_len, n_new)
        var kt0 = perf_counter_ns()
        for _r in range(reps):
            var kout = kv_cache_append_flat(existing, new_vals, cache_len, n_new)
            if kout.status != LLMK_OK or kout.n != cache_len + n_new:
                failures += 1
                print("   FAIL: status", kout.status, "n", kout.n, "at cache_len =", cache_len)
        var kns = _ns_since(kt0) / Float64(reps)
        var per_new = kns / Float64(n_new)
        var per_total = kns / Float64(cache_len + n_new)
        if ci == 0:
            per_new_first = per_new
            per_total_first = per_total
        per_new_last = per_new
        per_total_last = per_total
        print("  ", cache_len, "   ", kns, "   ", per_new, "   ", per_total)

    var new_growth = per_new_last / per_new_first if per_new_first > 0.0 else 0.0
    var total_growth = per_total_last / per_total_first if per_total_first > 0.0 else 0.0
    print("")
    print("   ns/appended-cell growth across a 256x larger existing cache:", new_growth, "x")
    print("   ns/total-copied-cell growth across the same range:", total_growth, "x  (gate: <= 3x)")

    if total_growth > 3.0:
        failures += 1
        print("   FAIL: ns per TOTAL byte moved grew", total_growth,
              "x — the copy itself is degrading per element, not just doing more of it")

    # The positive, load-bearing assertion: cost per NEWLY appended element must clearly GROW as
    # the existing cache grows, because every call re-copies the whole existing cache. A flat number
    # here would mean the implementation stopped doing what its own source does, and the finding
    # below (and the published page) would be wrong.
    if new_growth < 20.0:
        failures += 1
        print("   FAIL: ns per appended element did not grow with cache_len (got", new_growth,
              "x across a 256x larger cache) — kv_cache_append_flat may no longer be doing a full")
        print("   copy on every call, which would make the finding below false")
    else:
        print("   CONFIRMED: cost per newly appended element grows with the size of the EXISTING")
        print("   cache, because kv_cache_append_flat allocates a fresh List and copies the whole")
        print("   existing cache into it on every call — not an amortized append. This does not")
        print("   affect correctness (the output above is bit-identical to a direct concatenation),")
        print("   but a caller appending to the same cache many times over a long decode pays")
        print("   quadratic TOTAL copy cost across the sequence, not the O(1)-amortized cost an")
        print("   append usually implies. A caller who cares about that should know it before")
        print("   calling this repeatedly in a hot loop.")

    # ── 4. _kv_cache_append_into_flat — the fixed path the decode loop actually calls now ──────
    print("")
    print("[llmk.generate] _kv_cache_append_into_flat correctness against direct concatenation")
    var i_base_cache = _pseudo(6000, 71)
    var i_base_new = _pseudo(128, 72)
    var i_ref = List[Float64](capacity=6128)
    for i in range(6000):
        i_ref.append(i_base_cache[i])
    for i in range(128):
        i_ref.append(i_base_new[i])
    var i_buf = _kv_cache_reserve_flat(6128)
    var i_seed_status = _kv_cache_append_into_flat(i_buf, i_base_cache, 0, 6000)
    var i_grow_status = _kv_cache_append_into_flat(i_buf, i_base_new, 6000, 128)
    var i_drift = 0.0
    for i in range(6128):
        var dd = _abs(i_buf[i] - i_ref[i])
        if dd > i_drift:
            i_drift = dd
    if i_seed_status == LLMK_OK and i_grow_status == LLMK_OK and i_drift == 0.0:
        print("   correctness: bit-identical to cache ++ new_vals, in order, 6,000 + 128 = 6,128")
    else:
        failures += 1
        print("   FAIL: _kv_cache_append_into_flat diverged from direct concatenation by", i_drift)

    print("")
    print("[llmk.generate] _kv_cache_append_into_flat cost as the EXISTING cache grows, n_new fixed")
    print("   at 128 -- same shape section 3 measures, opposite claim: this must stay FLAT")
    print("   cache_len    total ns      ns/appended-cell")
    var i_clens = List[Int]()
    i_clens.append(512)
    i_clens.append(8192)
    i_clens.append(131072)
    var i_n_new = 128
    var i_new_vals = _pseudo(i_n_new, 81)
    var i_per_new_first = 0.0
    var i_per_new_last = 0.0
    var i_reps = 200
    for ci in range(len(i_clens)):
        var cache_len = i_clens[ci]
        var i_reserved = _kv_cache_reserve_flat(cache_len + i_n_new)
        var _i_seed = _kv_cache_append_into_flat(i_reserved, _pseudo(cache_len, 900 + ci), 0, cache_len)
        var _i_warm = _kv_cache_append_into_flat(i_reserved, i_new_vals, cache_len, i_n_new)
        var it0 = perf_counter_ns()
        for _r in range(i_reps):
            var i_status = _kv_cache_append_into_flat(i_reserved, i_new_vals, cache_len, i_n_new)
            if i_status != LLMK_OK:
                failures += 1
                print("   FAIL: status", i_status, "at cache_len =", cache_len)
        var i_ns = _ns_since(it0) / Float64(i_reps)
        var i_per_new = i_ns / Float64(i_n_new)
        if ci == 0:
            i_per_new_first = i_per_new
        i_per_new_last = i_per_new
        print("  ", cache_len, "   ", i_ns, "   ", i_per_new)

    var i_growth = i_per_new_last / i_per_new_first if i_per_new_first > 0.0 else 0.0
    print("")
    print("   ns/appended-cell growth across a 256x larger existing cache:", i_growth, "x  (gate: <= 3x)")
    if i_growth > 3.0:
        failures += 1
        print("   FAIL: ns per newly appended element grew", i_growth,
              "x with the existing cache -- the reserved-capacity path is re-copying existing")
        print("   content again, which would make this fix's whole premise false")
    else:
        print("   CONFIRMED: cost per newly appended element stays flat as the existing cache grows,")
        print("   the exact inverse of kv_cache_append_flat's own measured shape above -- this path")
        print("   writes only the", i_n_new, "new elements at their final offset, zero re-copy of the")
        print("   existing cache, zero reallocation once _kv_cache_reserve_flat has sized the buffer.")

    print("")
    if failures == 0:
        print("✅ llmk gate: all properties hold")
    else:
        print("❌ llmk gate:", failures, "property failure(s)")
