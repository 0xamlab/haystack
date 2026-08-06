"""test_llmk_generate.mojo — the two decode-loop primitives `qwen3_generate.mojo` calls per step:
KV-cache growth and full-vocabulary greedy argmax.

Hand-written, same idiom as `test_llmk_residual.mojo`. The correctness claims worth testing:
KV-cache append actually concatenates in order and refuses a caller's wrong length claim (the same
uncatchable-abort risk `llmk.residual` guards against, rule 1); greedy argmax finds the real maximum
regardless of where it sits, breaks ties by first-index (matching `numpy.argmax`), and refuses a
shape mismatch rather than reading past the real buffer.

Also covers `_kv_cache_append_into_flat` / `_kv_cache_reserve_flat` -- the internal, reserved-
capacity replacement `qwen3_generate.mojo`'s decode hot loop actually calls now (see
`llmk/generate.mojo`'s module docstring for why `kv_cache_append_flat` above stays unchanged and is
no longer that caller). The claim worth testing there is two-sided: bit-identical to
`cache ++ new_vals`, exactly like the O(cache_len + n_new) function above, PLUS the inverse of that
function's own cost shape -- cost per newly-appended element must stay FLAT as the existing cache
grows, not grow with it, since this path never re-copies existing content.
"""
from llmk.contract import (
    LLMK_ERR_CACHE_CAPACITY,
    LLMK_ERR_CACHE_LENGTH,
    LLMK_ERR_EMPTY_DIM,
    LLMK_ERR_LOGITS_LENGTH,
    LLMK_ERR_NEW_LENGTH,
    LLMK_OK,
)
from llmk.generate import (
    _kv_cache_append_into_flat,
    _kv_cache_reserve_flat,
    greedy_argmax_flat,
    kv_cache_append_flat,
)
from std.time import perf_counter_ns


def _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── kv_cache_append_flat: basic growth, in order ────────────────────────────
    var cache = List[Float64]()
    for i in range(6):
        cache.append(Float64(i))
    var new_vals = List[Float64]()
    for i in range(3):
        new_vals.append(Float64(100 + i))
    var grown = kv_cache_append_flat(cache, new_vals, 6, 3)
    var ok = grown.status == LLMK_OK and grown.n == 9
    for i in range(6):
        if _abs(grown.out[i] - Float64(i)) > 1e-12:
            ok = False
    for i in range(3):
        if _abs(grown.out[6 + i] - Float64(100 + i)) > 1e-12:
            ok = False
    if ok:
        passed += 1
        print("  ✅ kv_cache_append_flat: cache ++ new_vals, in order, length 6+3=9")
    else:
        failed += 1
        print("  ❌ kv_cache_append_flat produced the wrong buffer")

    # ── kv_cache_append_flat: growing an empty cache (prefill's own first step) ──
    var empty_cache = List[Float64]()
    var first_step = List[Float64]()
    for i in range(4):
        first_step.append(Float64(i) * 2.0)
    var from_empty = kv_cache_append_flat(empty_cache, first_step, 0, 4)
    if from_empty.status == LLMK_OK and from_empty.n == 4:
        passed += 1
        print("  ✅ appending to an empty (prefill's own) cache works, n=0 -> n=4")
    else:
        failed += 1
        print("  ❌ appending to an empty cache failed:", from_empty.status)

    # ── kv_cache_append_flat: refusals ──────────────────────────────────────────
    var short_cache = List[Float64]()
    short_cache.append(1.0)
    if kv_cache_append_flat(short_cache, new_vals, 6, 3).status == LLMK_ERR_CACHE_LENGTH:
        passed += 1
        print("  ✅ a caller's wrong cache_len claim is refused, not read past the real buffer")
    else:
        failed += 1
        print("  ❌ a mismatched cache_len was accepted -- this WOULD abort the worker")

    var short_new = List[Float64]()
    short_new.append(1.0)
    if kv_cache_append_flat(cache, short_new, 6, 3).status == LLMK_ERR_NEW_LENGTH:
        passed += 1
        print("  ✅ a caller's wrong n_new claim is refused, not read past the real buffer")
    else:
        failed += 1
        print("  ❌ a mismatched n_new was accepted -- this WOULD abort the worker")

    if kv_cache_append_flat(cache, new_vals, 6, 0).status == LLMK_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ n_new=0 is refused (a decode step always adds at least one token)")
    else:
        failed += 1
        print("  ❌ n_new=0 was not refused")

    # ── _kv_cache_append_into_flat: bit-identical to cache ++ new_vals ──────────
    var reserved = _kv_cache_reserve_flat(20)
    var seed_status = _kv_cache_append_into_flat(reserved, cache, 0, 6)
    var grow_status = _kv_cache_append_into_flat(reserved, new_vals, 6, 3)
    var into_ok = seed_status == LLMK_OK and grow_status == LLMK_OK
    for i in range(6):
        if _abs(reserved[i] - Float64(i)) > 1e-12:
            into_ok = False
    for i in range(3):
        if _abs(reserved[6 + i] - Float64(100 + i)) > 1e-12:
            into_ok = False
    if into_ok:
        passed += 1
        print("  ✅ _kv_cache_append_into_flat: reserved-buffer writes match cache ++ new_vals exactly")
    else:
        failed += 1
        print("  ❌ _kv_cache_append_into_flat produced the wrong buffer")

    # ── _kv_cache_append_into_flat: refuses capacity overrun rather than reading/writing past the
    # reserved buffer (the in-place analogue of kv_cache_append_flat's LLMK_ERR_CACHE_LENGTH check
    # -- there is no "cache_len mismatch" here since cache_len is just an offset, but writing past
    # the reserved length is the same uncatchable-abort risk rule 1 warns about) ──
    var tight = _kv_cache_reserve_flat(8)
    if _kv_cache_append_into_flat(tight, new_vals, 6, 3) == LLMK_ERR_CACHE_CAPACITY:
        passed += 1
        print("  ✅ writing past the reserved capacity is refused, not written out of bounds")
    else:
        failed += 1
        print("  ❌ a capacity overrun was accepted -- this WOULD write past the reserved buffer")

    if _kv_cache_append_into_flat(reserved, short_new, 6, 3) == LLMK_ERR_NEW_LENGTH:
        passed += 1
        print("  ✅ _kv_cache_append_into_flat also refuses a wrong n_new claim")
    else:
        failed += 1
        print("  ❌ _kv_cache_append_into_flat accepted a mismatched n_new claim")

    if len(_kv_cache_reserve_flat(0)) == 0 and len(_kv_cache_reserve_flat(-1)) == 0:
        passed += 1
        print("  ✅ _kv_cache_reserve_flat refuses a non-positive size (empty list, not a crash)")
    else:
        failed += 1
        print("  ❌ _kv_cache_reserve_flat accepted a non-positive size")

    # ── _kv_cache_append_into_flat: cost per NEWLY appended element stays FLAT as the existing
    # cache grows -- the exact inverse of kv_cache_append_flat's own documented O(cache_len + n_new)
    # cost, and the positive proof the quadratic-total-copy bug is gone from this path. Same
    # methodology bench_llmk.mojo uses for the O(cache_len + n_new) function: REPS amortizes away
    # clock-resolution noise on a single call. ──
    var n_new_probe = 128
    var probe_vals = List[Float64]()
    for i in range(n_new_probe):
        probe_vals.append(Float64(i))
    var probe_reps = 200

    var small_cap = 2048
    var small_buf = _kv_cache_reserve_flat(small_cap + n_new_probe)
    var _small_warm = _kv_cache_append_into_flat(small_buf, probe_vals, small_cap - n_new_probe, n_new_probe)
    var small_t0 = perf_counter_ns()
    for _r in range(probe_reps):
        _ = _kv_cache_append_into_flat(small_buf, probe_vals, small_cap - n_new_probe, n_new_probe)
    var small_ns = Float64(Int(perf_counter_ns() - small_t0)) / Float64(probe_reps)
    var small_per = small_ns / Float64(n_new_probe)

    var big_cap = 2048 + 131072
    var big_buf = _kv_cache_reserve_flat(big_cap + n_new_probe)
    var _big_warm = _kv_cache_append_into_flat(big_buf, probe_vals, big_cap - n_new_probe, n_new_probe)
    var big_t0 = perf_counter_ns()
    for _r in range(probe_reps):
        _ = _kv_cache_append_into_flat(big_buf, probe_vals, big_cap - n_new_probe, n_new_probe)
    var big_ns = Float64(Int(perf_counter_ns() - big_t0)) / Float64(probe_reps)
    var big_per = big_ns / Float64(n_new_probe)

    var flat_growth = big_per / small_per if small_per > 0.0 else 0.0
    var cache_size_growth = Float64(big_cap) / Float64(small_cap)
    print("  [cost shape] ns/appended-cell at existing-cache-size", small_cap, "->", small_per)
    print("  [cost shape] ns/appended-cell at existing-cache-size", big_cap, "->", big_per,
          "(", cache_size_growth, "x larger existing cache )")
    print("  [cost shape] growth:", flat_growth, "x  (gate: <= 3x -- flat, not the O(cache_len) growth")
    print("  kv_cache_append_flat itself still shows)")
    if flat_growth <= 3.0:
        passed += 1
        print("  ✅ cost per newly-appended element stays flat as the existing cache grows",
              cache_size_growth, "x -- no re-copy of existing content, unlike kv_cache_append_flat")
    else:
        failed += 1
        print("  ❌ cost per newly-appended element grew", flat_growth,
              "x with the existing cache -- the in-place path is copying existing content again")

    # ── greedy_argmax_flat: max in the middle, at the start, at the end ─────────
    var mid = List[Float64]()
    mid.append(1.0)
    mid.append(9.0)
    mid.append(3.0)
    var r_mid = greedy_argmax_flat(mid, 3)
    if r_mid.status == LLMK_OK and r_mid.token_id == 1 and r_mid.logit == 9.0:
        passed += 1
        print("  ✅ argmax finds id 1 when the max sits in the middle")
    else:
        failed += 1
        print("  ❌ argmax got", r_mid.token_id, "expected 1")

    var at_start = List[Float64]()
    at_start.append(9.0)
    at_start.append(1.0)
    at_start.append(3.0)
    if greedy_argmax_flat(at_start, 3).token_id == 0:
        passed += 1
        print("  ✅ argmax finds id 0 when the max sits at the start")
    else:
        failed += 1
        print("  ❌ argmax at the start failed")

    var at_end = List[Float64]()
    at_end.append(1.0)
    at_end.append(3.0)
    at_end.append(9.0)
    if greedy_argmax_flat(at_end, 3).token_id == 2:
        passed += 1
        print("  ✅ argmax finds id 2 when the max sits at the end")
    else:
        failed += 1
        print("  ❌ argmax at the end failed")

    # ── greedy_argmax_flat: negative logits (a real model produces these routinely) ──
    var negs = List[Float64]()
    negs.append(-5.0)
    negs.append(-1.0)
    negs.append(-9.0)
    if greedy_argmax_flat(negs, 3).token_id == 1:
        passed += 1
        print("  ✅ argmax handles all-negative logits correctly (-1.0 beats -5.0 and -9.0)")
    else:
        failed += 1
        print("  ❌ all-negative argmax failed")

    # ── greedy_argmax_flat: exact tie resolves to the FIRST index, like numpy.argmax ──
    var tied = List[Float64]()
    tied.append(2.0)
    tied.append(7.0)
    tied.append(7.0)
    tied.append(1.0)
    if greedy_argmax_flat(tied, 4).token_id == 1:
        passed += 1
        print("  ✅ an exact tie resolves to the first matching id (numpy.argmax's own convention)")
    else:
        failed += 1
        print("  ❌ tie-breaking did not pick the first index")

    # ── greedy_argmax_flat: refusals ────────────────────────────────────────────
    var three = List[Float64]()
    three.append(1.0)
    three.append(2.0)
    three.append(3.0)
    if greedy_argmax_flat(three, 5).status == LLMK_ERR_LOGITS_LENGTH:
        passed += 1
        print("  ✅ n=5 against a 3-element logits row is refused, not read past the end")
    else:
        failed += 1
        print("  ❌ a mismatched logits length was accepted -- this WOULD abort the worker")

    if greedy_argmax_flat(three, 0).status == LLMK_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ n=0 is refused rather than returning a fabricated argmax")
    else:
        failed += 1
        print("  ❌ n=0 was not refused")

    # ── the exact shape a real decode step calls this at: one full 151936-wide vocab row ──
    var vocab_n = 151936
    var big_logits = List[Float64](capacity=vocab_n)
    for i in range(vocab_n):
        big_logits.append(Float64(i) * -0.0001)
    big_logits[12095] = 50.0  # a real Qwen3-0.6B-Base "Paris" id, from the forward-pass phase
    var big = greedy_argmax_flat(big_logits, vocab_n)
    if big.status == LLMK_OK and big.token_id == 12095:
        passed += 1
        print("  ✅ a real decode-step-shaped call (151936-wide vocab row) finds the planted max")
    else:
        failed += 1
        print("  ❌ the vocab-width call failed:", big.status, big.token_id)

    print("  [llmk.generate] Passed:", passed, "Failed:", failed)
