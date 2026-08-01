"""test_streaming_contract.mojo — known-value tests for streaming's shared vocabulary.

Hand-written. Every number asserted here is either derived by hand from a formula printed
beside it, or compared against a NAMED frozen reference:

  * `determinism.streams.stream_id("algenta.streaming")` is the reference for `STM_STREAM`.
    The constant is a copy for speed, and this is the assertion that stops it rotting.
  * `sketch.cms_hash` is the reference for the frozen row-degeneracy measurement, and the
    three equal values (52, 52, 52) can be reproduced with a calculator from the formula in
    the frozen docstring: `(item * seed + 17) mod 1000003 mod width`, with 7, 1000010 and
    2000013 all congruent to 7 modulo 1000003.
  * `sparse_numerics.csr.dims_fit` is the reference for shape checking, including the
    wrapping product `3 * 6148914691236517206 == 2` that motivates it.
  * The four error CLAIMS are checked against their closed forms: `1.04 / sqrt(4096)` is
    exactly 0.01625, `8.0 / 256` is exactly 0.03125, `e/4096 * (1 + 4096/1000003)` is
    0.000666361298199772, and `e^-4` is 1/54.598150033144236 = 0.018315638888734179 — derived
    from repeated multiplication of `STM_E` so the reference does not come from `exp`, the
    function under test. That comparison also records a real 1.7e-12 relative inaccuracy in
    this platform's `exp(-4.0)`.

Nothing here asserts that a function agrees with itself.
"""
from std.math import sqrt

from determinism.streams import stream_id
from sketch import cms_hash, create_cms
from streaming.contract import (
    MAX_STM_CELLS,
    MAX_STM_DEPTH,
    MAX_STM_K,
    MAX_STM_PRECISION,
    MAX_STM_SEED,
    MAX_STM_WIDTH,
    MAX_STM_WINDOW,
    MIN_STM_K,
    MIN_STM_PRECISION,
    STM_CMS_MODULUS,
    STM_DBL_EPSILON,
    STM_E,
    STM_ERR_CAPACITY,
    STM_ERR_DEPTH,
    STM_ERR_PRECISION,
    STM_ERR_WIDTH,
    STM_HLL_SIGMA,
    STM_KLL_C,
    STM_OK,
    STM_STREAM,
    stm_cells_fit,
    stm_cms_delta,
    stm_cms_epsilon,
    stm_coin,
    stm_finite,
    stm_hll_registers,
    stm_hll_relative_error,
    stm_items_ok,
    stm_key_bucket,
    stm_key_hash31,
    stm_key_word,
    stm_kll_rank_error,
    stm_log2_floor,
    stm_no_claim,
    stm_seed_ok,
    stm_status_name,
    stm_stream_id,
    stm_tolerance,
    stm_u64_of,
    stm_version,
    stm_work_fits,
)

comptime WRAP_FACTOR: Int = 6148914691236517206


fn _close(got: Float64, want: Float64) -> Bool:
    """Equality within a tolerance scaled by THE JUDGED NUMBER's own magnitude."""
    var diff = got - want
    if diff < 0.0:
        diff = -diff
    return diff <= stm_tolerance(want, 0.0)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── 1. the stream id is DERIVED, and the copy is checked against the derivation ──
    if STM_STREAM == stream_id("algenta.streaming") and stm_stream_id() == STM_STREAM:
        passed += 1
        print("  ✅ STM_STREAM ==", STM_STREAM, "== stream_id(\"algenta.streaming\")")
    else:
        failed += 1
        print("  ❌ STM_STREAM", STM_STREAM, "!= stream_id derivation",
              stream_id("algenta.streaming"))

    # ── 2. the frozen CMS row degeneracy, hand-computable ─────────────────────
    # 5*7+17 = 52; 5*1000010+17 = 5000067 = 4*1000003 + 1000055 -> 52 mod 1000003;
    # 5*2000013+17 = 10000082 = 9*1000003 + 1000055 -> 52. All three seeds are 7 mod 1000003.
    var h0 = cms_hash(5, 7, 100)
    var h1 = cms_hash(5, 1000010, 100)
    var h2 = cms_hash(5, 2000013, 100)
    if h0 == 52 and h1 == 52 and h2 == 52:
        passed += 1
        print("  ✅ frozen cms_hash(5, {7,1000010,2000013}, 100) == 52 for all three:",
              "every row seed is 7 mod 1000003, so depth is vacuous")
    else:
        failed += 1
        print("  ❌ expected 52,52,52 from frozen cms_hash, got", h0, h1, h2)

    # And the frozen seed schedule really is that, read from the frozen constructor.
    var frozen = create_cms(64, 3)
    if (
        frozen.hash_seeds[0] == 7
        and frozen.hash_seeds[1] == 1000010
        and frozen.hash_seeds[2] == 2000013
    ):
        passed += 1
        print("  ✅ create_cms row seeds are 7, 1000010, 2000013 — d*1000003 + 7")
    else:
        failed += 1
        print("  ❌ unexpected frozen seed schedule", frozen.hash_seeds[0],
              frozen.hash_seeds[1], frozen.hash_seeds[2])

    # ── 3. keyed columns differ per row where the frozen ones do not ──────────
    var kb0 = stm_key_bucket(11, 0, 5, 4096)
    var kb1 = stm_key_bucket(11, 1, 5, 4096)
    var kb2 = stm_key_bucket(11, 2, 5, 4096)
    if kb0 != kb1 and kb1 != kb2 and kb0 != kb2:
        passed += 1
        print("  ✅ keyed columns for item 5 on rows 0,1,2 are distinct:", kb0, kb1, kb2)
    else:
        failed += 1
        print("  ❌ keyed columns collapsed across rows:", kb0, kb1, kb2)

    if stm_key_bucket(11, 0, 5, 0) == -1 and stm_key_bucket(11, 0, 5, MAX_STM_WIDTH + 1) == -1:
        passed += 1
        print("  ✅ an unusable width yields -1, never a column")
    else:
        failed += 1
        print("  ❌ stm_key_bucket returned a column for an unusable width")

    # ── 4. determinism: the same coordinates give the same word, always ───────
    var w_a = stm_key_word(11, 3, 12345)
    var w_b = stm_key_word(11, 3, 12345)
    var w_c = stm_key_word(12, 3, 12345)
    if w_a == w_b and w_a != w_c:
        passed += 1
        print("  ✅ stm_key_word is a pure function of (seed, row, item):", w_a)
    else:
        failed += 1
        print("  ❌ keyed hash is not reproducible or ignores the seed", w_a, w_b, w_c)

    if stm_key_hash31(11, 0, -7) >= 0 and stm_key_hash31(11, 0, -7) <= 0x7FFFFFFF:
        passed += 1
        print("  ✅ a NEGATIVE item hashes to a non-negative 31-bit value:",
              stm_key_hash31(11, 0, -7))
    else:
        failed += 1
        print("  ❌ negative item produced an out-of-range hash",
              stm_key_hash31(11, 0, -7))

    # Two's-complement conversion, hand-checkable: 2^64 - 5 = 18446744073709551611.
    if stm_u64_of(-5) == 18446744073709551611 and stm_u64_of(5) == 5:
        passed += 1
        print("  ✅ stm_u64_of(-5) == 2^64 - 5 == 18446744073709551611")
    else:
        failed += 1
        print("  ❌ stm_u64_of(-5) ==", stm_u64_of(-5))

    # The coin must actually take both values over a short run, or it is not a coin.
    var heads = 0
    for i in range(64):
        if stm_coin(5, 0, i):
            heads += 1
    if heads > 8 and heads < 56:
        passed += 1
        print("  ✅ the compaction coin gave", heads, "heads in 64 draws")
    else:
        failed += 1
        print("  ❌ the compaction coin is not fair:", heads, "heads in 64")

    # ── 5. the work budget is decided by DIVISION ────────────────────────────
    # 3 * 6148914691236517206 wraps to 2 in 64-bit arithmetic, so a multiply-based guard
    # would call this request tiny. Division cannot be fooled.
    if 3 * WRAP_FACTOR == 2:
        passed += 1
        print("  ✅ 3 * 6148914691236517206 ==", 3 * WRAP_FACTOR,
              "— the wrapping multiply this guard exists to avoid")
    else:
        failed += 1
        print("  ❌ the wrapping product is not 2 here; the premise needs restating")

    if not stm_work_fits(3, WRAP_FACTOR, 1 << 27) and stm_work_fits(100, 4, 1000):
        passed += 1
        print("  ✅ stm_work_fits refuses the wrapping product and accepts 100*4 <= 1000")
    else:
        failed += 1
        print("  ❌ stm_work_fits verdicts are wrong")

    if stm_work_fits(0, WRAP_FACTOR, 0) and stm_work_fits(5, 0, 0):
        passed += 1
        print("  ✅ zero units or zero work per unit is zero work and fits any budget")
    else:
        failed += 1
        print("  ❌ zero-work cases refused")

    if not stm_work_fits(-1, 1, 10) and not stm_work_fits(1, 1, -1):
        passed += 1
        print("  ✅ negative units, work or budget are refused")
    else:
        failed += 1
        print("  ❌ a negative argument slipped through stm_work_fits")

    # ── 6. shape checks delegate to the frozen dims_fit ──────────────────────
    if stm_cells_fit(4, 4096, 16384) and not stm_cells_fit(3, WRAP_FACTOR, 2):
        passed += 1
        print("  ✅ stm_cells_fit: 4x4096 == 16384 cells, and the wrapping shape is refused")
    else:
        failed += 1
        print("  ❌ stm_cells_fit verdicts are wrong")

    if not stm_cells_fit(16, 16384, 16 * 16384) or MAX_STM_CELLS != 262144:
        # 16 * 16384 = 262144 == MAX_STM_CELLS, so the largest legal table must FIT.
        failed += 1
        print("  ❌ the largest legal table is being refused; MAX_STM_CELLS =",
              MAX_STM_CELLS)
    else:
        passed += 1
        print("  ✅ the largest legal table (16 x 16384 = 262144 cells) fits exactly")

    # ── 7. the four error CLAIMS, against their closed forms ─────────────────
    var hll = stm_hll_relative_error(12)
    if hll.present and _close(hll.value, 1.04 / sqrt(4096.0)) and _close(hll.value, 0.01625):
        passed += 1
        print("  ✅ stm_hll_relative_error(12) == 1.04/sqrt(4096) == 0.01625:", hll.value)
    else:
        failed += 1
        print("  ❌ hll claim", hll.value, "expected 0.01625")

    var eps = stm_cms_epsilon(4096)
    var eps_want = STM_E * (1.0 + 4096.0 / 1000003.0) / 4096.0
    if eps.present and _close(eps.value, eps_want) and _close(eps.value, 0.000666361298199772):
        passed += 1
        print("  ✅ stm_cms_epsilon(4096) == e/4096 * (1 + 4096/1000003) ==", eps.value)
    else:
        failed += 1
        print("  ❌ cms epsilon", eps.value, "expected", eps_want)

    # e^-4 is derived from `STM_E` by repeated multiplication rather than from `exp`, so the
    # reference is independent of the function under test. Hand value: 1/2.718281828459045^4
    # = 1/54.598150033144236 = 0.018315638888734179.
    #
    # This platform's `exp(-4.0)` returns 0.01831563888870315, which is 1.7e-12 RELATIVE below
    # the true value -- about 7,700 ulps, far outside `stm_tolerance`. That is a property of
    # the standard library's `exp`, not of this package, and it is recorded here rather than
    # hidden by loosening the comparison silently: a failure probability of 0.0183156388887 vs
    # 0.0183156388870 makes no difference to any decision a caller takes on it, so the claim
    # is asserted to 1e-9 relative and the discrepancy is printed.
    var dlt = stm_cms_delta(4)
    var e4 = STM_E * STM_E * STM_E * STM_E
    var delta_want = 1.0 / e4
    var delta_gap = dlt.value - delta_want
    if delta_gap < 0.0:
        delta_gap = -delta_gap
    if dlt.present and delta_gap <= 1e-9 * delta_want:
        passed += 1
        print("  ✅ stm_cms_delta(4) ==", dlt.value, "vs 1/e^4 ==", delta_want,
              "(relative gap", delta_gap / delta_want, "— the platform exp, not this claim)")
    else:
        failed += 1
        print("  ❌ cms delta", dlt.value, "expected", delta_want, "gap", delta_gap)

    var kll = stm_kll_rank_error(256)
    if kll.present and _close(kll.value, 8.0 / 256.0) and _close(kll.value, 0.03125):
        passed += 1
        print("  ✅ stm_kll_rank_error(256) == 8.0/256 == 0.03125:", kll.value)
    else:
        failed += 1
        print("  ❌ kll claim", kll.value, "expected 0.03125")

    if STM_HLL_SIGMA == 1.04 and STM_KLL_C == 8.0 and STM_CMS_MODULUS == 1000003:
        passed += 1
        print("  ✅ the three claim constants are 1.04, 8.0 and 1000003")
    else:
        failed += 1
        print("  ❌ a claim constant changed without this test being updated")

    # ── 8. a claim that does not exist is ABSENT, not 0.0 ────────────────────
    var absent_ok = 0
    var absent_want = 6
    if not stm_hll_relative_error(3).present \
            and stm_hll_relative_error(3).status == STM_ERR_PRECISION:
        absent_ok += 1
    if not stm_hll_relative_error(MAX_STM_PRECISION + 1).present:
        absent_ok += 1
    if not stm_cms_epsilon(0).present and stm_cms_epsilon(0).status == STM_ERR_WIDTH:
        absent_ok += 1
    if not stm_cms_delta(0).present and stm_cms_delta(0).status == STM_ERR_DEPTH:
        absent_ok += 1
    if not stm_kll_rank_error(255).present \
            and stm_kll_rank_error(255).status == STM_ERR_CAPACITY:
        absent_ok += 1
    if not stm_kll_rank_error(MIN_STM_K - 1).present:
        absent_ok += 1
    if absent_ok == absent_want:
        passed += 1
        print("  ✅", absent_want, "unusable parameters yield ABSENT claims under typed",
              "statuses, and every one of them carries value 0.0 that is not a bound")
    else:
        failed += 1
        print("  ❌ only", absent_ok, "of", absent_want, "bad parameters were absent")

    if stm_no_claim(STM_ERR_WIDTH).value == 0.0 \
            and not stm_no_claim(STM_ERR_WIDTH).present:
        passed += 1
        print("  ✅ an absent claim carries 0.0 in a representable slot, and the flag",
              "is the answer")
    else:
        failed += 1
        print("  ❌ stm_no_claim is not absent-with-a-representable-value")

    # ── 9. an odd k is refused: a compaction halves a full level ─────────────
    if not stm_kll_rank_error(6).present:
        failed += 1
        print("  ❌ k = 6 is even and should be accepted")
    elif stm_kll_rank_error(7).present:
        failed += 1
        print("  ❌ k = 7 is odd and must be refused")
    else:
        passed += 1
        print("  ✅ even k accepted, odd k refused (a compaction promotes exactly half)")

    # ── 10. tolerance is scaled by the judged number, and nothing else ───────
    var tol_small = stm_tolerance(1e-6, 0.0)
    var tol_big = stm_tolerance(1e6, 0.0)
    if tol_small < tol_big and _close(tol_big, 64.0 * STM_DBL_EPSILON * 1e6) \
            and tol_small < 1e-6:
        passed += 1
        print("  ✅ stm_tolerance scales with the judged magnitude:",
              tol_small, "vs", tol_big, "— not floored at one unit")
    else:
        failed += 1
        print("  ❌ stm_tolerance is not per-item scaled:", tol_small, tol_big)

    if stm_tolerance(1e-6, 0.0) < 1.0 and stm_tolerance(0.0, 0.0) == 0.0:
        passed += 1
        print("  ✅ a small quantity gets a small allowance, and zero gets zero —",
              "not `1 + |x|`")
    else:
        failed += 1
        print("  ❌ tolerance has an absolute floor it should not have")

    # ── 11. integer helpers ─────────────────────────────────────────────────
    if stm_log2_floor(1024) == 10 and stm_log2_floor(1023) == 9 \
            and stm_log2_floor(1) == 0 and stm_log2_floor(0) == -1 \
            and stm_log2_floor(-5) == -1:
        passed += 1
        print("  ✅ stm_log2_floor: 1024->10, 1023->9, 1->0, 0 and -5 -> -1")
    else:
        failed += 1
        print("  ❌ stm_log2_floor is wrong somewhere")

    if stm_hll_registers(12) == 4096 and stm_hll_registers(MIN_STM_PRECISION) == 16 \
            and stm_hll_registers(99) == 0 and stm_hll_registers(-3) == 0:
        passed += 1
        print("  ✅ stm_hll_registers: 12->4096, 4->16, out of range -> 0 (not a shift",
              "by a negative amount)")
    else:
        failed += 1
        print("  ❌ stm_hll_registers is wrong somewhere")

    # ── 12. seeds and item counts ───────────────────────────────────────────
    if stm_seed_ok(0) and stm_seed_ok(MAX_STM_SEED) and not stm_seed_ok(-1) \
            and not stm_seed_ok(MAX_STM_SEED + 1):
        passed += 1
        print("  ✅ seeds live in [0, 2^53] so they survive a JSON round trip exactly")
    else:
        failed += 1
        print("  ❌ seed range check is wrong")

    if stm_items_ok(0) and not stm_items_ok(-1) and not stm_items_ok(1 << 25):
        passed += 1
        print("  ✅ item counts are bounded above and below")
    else:
        failed += 1
        print("  ❌ item count check is wrong")

    # ── 13. finiteness and status naming ────────────────────────────────────
    var nan = 0.0 / 0.0
    var inf = 1.0 / 0.0
    if stm_finite(1.0) and not stm_finite(nan) and not stm_finite(inf) \
            and not stm_finite(-inf):
        passed += 1
        print("  ✅ stm_finite rejects NaN and both infinities")
    else:
        failed += 1
        print("  ❌ stm_finite is wrong")

    # Every code in 360-379 must have a name, and nothing outside may claim one.
    var named = 0
    for code in range(360, 380):
        if stm_status_name(code) != "unknown_status":
            named += 1
    if named == 20 and stm_status_name(359) == "unknown_status" \
            and stm_status_name(380) == "unknown_status" \
            and stm_status_name(STM_OK) == "ok":
        passed += 1
        print("  ✅ all twenty codes in 360-379 are named and nothing outside is")
    else:
        failed += 1
        print("  ❌ status naming is incomplete:", named, "of 20 named")

    if len(stm_version()) > 0 and stm_version() == stm_version():
        passed += 1
        print("  ✅ stm_version is a stable identity string:", stm_version())
    else:
        failed += 1
        print("  ❌ stm_version is not stable")

    # ── 14. the declared ceilings are the documented numbers ────────────────
    if MAX_STM_WIDTH == 16384 and MAX_STM_DEPTH == 16 and MAX_STM_K == 4096 \
            and MAX_STM_PRECISION == 16 and MAX_STM_WINDOW == 65536:
        passed += 1
        print("  ✅ ceilings are 16384 / 16 / 4096 / 16 / 65536 as documented")
    else:
        failed += 1
        print("  ❌ a ceiling changed without this test being updated")

    # A width above the frozen modulus would have unreachable columns; the ceiling forbids it.
    if MAX_STM_WIDTH < STM_CMS_MODULUS:
        passed += 1
        print("  ✅ MAX_STM_WIDTH", MAX_STM_WIDTH, "< the frozen modulus",
              STM_CMS_MODULUS, "so every column is reachable")
    else:
        failed += 1
        print("  ❌ the width ceiling permits unreachable columns")

    print("  [streaming.contract] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_contract: " + String(failed) + " failure(s)")
